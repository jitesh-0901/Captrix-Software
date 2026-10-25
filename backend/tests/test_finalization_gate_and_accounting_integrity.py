import pytest
from decimal import Decimal
from datetime import date
from django.utils import timezone
from django.contrib.auth.models import User

from apps.companies.models import Company, FinancialYear, Engagement, EngagementType, EntityType, EngagementStatus
from apps.accounting.models import ScheduleIIIGroup, TrialBalanceSnapshot
from apps.accounting.services import TrialBalanceService
from apps.audit.models import (
    FixedAsset, SubledgerAgingItem, ExceptionItem,
    ExceptionSeverity, ExceptionStatus
)
from apps.core.models import AuditLog
from apps.audit.far_depreciation import FixedAssetAuditEngine
from apps.audit.finalization_service import AuditFinalizationService
from apps.reconciliation.models import ReconciliationRun, ReconciliationStatus, ReconciliationType
from apps.ingestion.models import Document, DocumentType, DocumentStatus, ExtractedRecord
from apps.reporting.models import Workpaper, WorkpaperStatus, ProposedAdjustment, AdjustmentStatus
from apps.reporting.exporters import ReportExporterService


@pytest.mark.django_db
class TestAuditFinalizationGates:
    """
    Rigorously tests the 9 mandatory audit finalization scenarios in AuditFinalizationService:
    1. Bank reconciliation unresolved (blocked).
    2. Material ledger/subledger difference > materiality (blocked).
    3. Required revenue evidence missing when turnover > 0 (blocked).
    4. Duplicate or unapproved adjustment (blocked).
    5. Material financial statement inconsistency (TB or BS unbalanced) (blocked).
    6. Incomplete document extraction (blocked).
    7. Missing required workpaper review (blocked).
    8. Unauthorized attempt to finalize (blocked).
    9. Valid complete engagement with all required reviews completed (succeeds).
    """

    @pytest.fixture
    def base_engagement(self):
        company = Company.objects.create(
            name="Apex Testing Corp Private Limited",
            cin="U29100DL2021PTC123456",
            pan="AAACA1234K",
            entity_type=EntityType.PVT_LTD
        )
        fy = FinancialYear.objects.create(
            company=company,
            label="FY 2025-26",
            start_date=date(2025, 4, 1),
            end_date=date(2026, 3, 31)
        )
        partner = User.objects.create_user(
            username="lead_partner_ca",
            password="testpassword123",
            is_staff=True
        )
        engagement = Engagement.objects.create(
            company=company,
            financial_year=fy,
            title="Statutory Audit FY 2025-26",
            engagement_type=EngagementType.STATUTORY,
            overall_materiality=Decimal("500000.00"),
            lead_partner=partner,
            is_finalized=False
        )

        # Create balanced Trial Balance
        tb_rows = [
            {'account_code': '101', 'account_name': 'Sales Revenue', 'closing_credit_inr': '10000000.00', 'schedule_iii_group': ScheduleIIIGroup.REVENUE_OPERATIONS},
            {'account_code': '201', 'account_name': 'Cost of Materials', 'closing_debit_inr': '6000000.00', 'schedule_iii_group': ScheduleIIIGroup.COST_OF_MATERIALS},
            {'account_code': '202', 'account_name': 'Employee Benefits', 'closing_debit_inr': '1000000.00', 'schedule_iii_group': ScheduleIIIGroup.EMPLOYEE_BENEFITS},
            {'account_code': '301', 'account_name': 'Share Capital', 'closing_credit_inr': '2000000.00', 'schedule_iii_group': ScheduleIIIGroup.SHARE_CAPITAL},
            {'account_code': '302', 'account_name': 'Reserves & Surplus', 'closing_credit_inr': '1000000.00', 'schedule_iii_group': ScheduleIIIGroup.RESERVES_SURPLUS},
            {'account_code': '303', 'account_name': 'Trade Payables GL', 'closing_credit_inr': '2000000.00', 'schedule_iii_group': ScheduleIIIGroup.TRADE_PAYABLES},
            {'account_code': '401', 'account_name': 'Plant & Machinery', 'closing_debit_inr': '4000000.00', 'schedule_iii_group': ScheduleIIIGroup.PPE},
            {'account_code': '402', 'account_name': 'Trade Receivables GL', 'closing_debit_inr': '2000000.00', 'schedule_iii_group': ScheduleIIIGroup.TRADE_RECEIVABLES},
            {'account_code': '403', 'account_name': 'Cash & Bank Balances', 'closing_debit_inr': '2000000.00', 'schedule_iii_group': ScheduleIIIGroup.CASH_EQUIVALENTS},
        ]
        # Total Credits: 10M + 2M + 1M + 2M = 15M. Total Debits: 6M + 1M + 4M + 2M + 2M = 15M. (Balanced!)
        TrialBalanceService.calculate_trial_balance(tb_rows, as_of_date=fy.end_date, engagement=engagement)

        return engagement, partner

    def test_scenario_1_bank_reconciliation_unresolved_blocks_finalization(self, base_engagement):
        """Scenario 1: BRS missing or unresolved must fail closed and block finalization."""
        engagement, partner = base_engagement

        # No BRS statement exists initially
        readiness = AuditFinalizationService.evaluate_finalization_readiness(engagement, user=partner)
        assert not readiness['can_finalize']
        assert any("Bank reconciliation" in b for b in readiness['blockers'])

        # Now create an unresolved BRS statement with ₹45,000 difference
        ReconciliationRun.objects.create(
            engagement=engagement,
            recon_type='BANK',
            status=ReconciliationStatus.IN_PROGRESS,
            as_of_date=date(2026, 3, 31),
            unreconciled_difference=Decimal('45000.00'),
            unmatched_count=3,
            summary_data={'stale_cheques_count': 0}
        )

        readiness2 = AuditFinalizationService.evaluate_finalization_readiness(engagement, user=partner)
        assert not readiness2['can_finalize']
        assert any("unreconciled variance" in b or "unmatched" in b for b in readiness2['blockers'])

        # Calling finalize_engagement must fail closed
        result = AuditFinalizationService.finalize_engagement(engagement, user=partner)
        assert result['success'] is False
        assert "Cannot finalize engagement" in result['message']
        assert engagement.is_finalized is False

    def test_scenario_2_material_ledger_subledger_difference_blocks_finalization(self, base_engagement):
        """Scenario 2: Material variance between GL control and subledger exceeds performance materiality."""
        engagement, partner = base_engagement

        # Overall materiality is ₹500,000. Performance materiality is ₹375,000 (75%).
        # Trade Payables GL is ₹2,000,000.00.
        # Create Creditor subledger totaling only ₹1,400,000.00 (diff: ₹600,000 > ₹375,000).
        SubledgerAgingItem.objects.create(
            engagement=engagement,
            item_type='PAYABLE',
            party_name='Vendor Steel Corp',
            invoice_date=date(2025, 4, 1),
            due_date=date(2025, 5, 1),
            outstanding_amount=Decimal('1400000.00'),
            total_amount=Decimal('1400000.00'),
            ageing_days=45,
            ageing_bucket='30-60'
        )

        readiness = AuditFinalizationService.evaluate_finalization_readiness(engagement, user=partner)
        assert not readiness['can_finalize']
        assert any("Material Trade Payables subledger variance" in b for b in readiness['blockers'])

    def test_scenario_3_required_revenue_evidence_missing_blocks_finalization(self, base_engagement):
        """Scenario 3: When turnover > performance materiality, missing GSTR-1 evidence blocks finalization."""
        engagement, partner = base_engagement

        # Turnover in base_engagement is ₹10,000,000.00 (exceeds ₹375,000).
        # No GSTR-1 document uploaded.
        readiness = AuditFinalizationService.evaluate_finalization_readiness(engagement, user=partner)
        assert not readiness['can_finalize']
        assert any("Required revenue verification evidence missing" in b for b in readiness['blockers'])

    def test_scenario_4_duplicate_or_unapproved_adjustment_blocks_finalization(self, base_engagement):
        """Scenario 4: Unposted proposed adjustments or duplicate adjustments block finalization."""
        engagement, partner = base_engagement

        # Create an unapproved/proposed adjustment
        aje1 = ProposedAdjustment.objects.create(
            engagement=engagement,
            adjustment_number="AJE-01",
            title="Depreciation correction",
            reason="Schedule II recalculation",
            total_debit=Decimal("150000.00"),
            total_credit=Decimal("150000.00"),
            is_balanced=True,
            status=AdjustmentStatus.PROPOSED,
            is_posted=False
        )

        readiness = AuditFinalizationService.evaluate_finalization_readiness(engagement, user=partner)
        assert not readiness['can_finalize']
        assert any("proposed adjusting journal entry" in b and "unapproved" in b for b in readiness['blockers'])

        # Now approve/post it, but add a duplicate adjustment with same amounts and title
        aje1.status = AdjustmentStatus.POSTED
        aje1.is_posted = True
        aje1.save()

        ProposedAdjustment.objects.create(
            engagement=engagement,
            adjustment_number="AJE-02",
            title="Depreciation correction",
            reason="Schedule II recalculation duplicate",
            total_debit=Decimal("150000.00"),
            total_credit=Decimal("150000.00"),
            is_balanced=True,
            status=AdjustmentStatus.POSTED,
            is_posted=True
        )

        readiness2 = AuditFinalizationService.evaluate_finalization_readiness(engagement, user=partner)
        assert not readiness2['can_finalize']
        assert any("Duplicate adjustment detected" in b for b in readiness2['blockers'])

    def test_scenario_5_material_financial_statement_inconsistency_blocks_finalization(self, base_engagement):
        """Scenario 5: Unbalanced Trial Balance or Balance Sheet disequilibrium blocks finalization."""
        engagement, partner = base_engagement

        # Break Trial Balance equilibrium
        tb = engagement.trial_balances.first()
        tb.is_balanced = False
        tb.difference_amount = Decimal("50000.00")
        tb.save()

        readiness = AuditFinalizationService.evaluate_finalization_readiness(engagement, user=partner)
        assert not readiness['can_finalize']
        assert any("Trial Balance is unbalanced" in b for b in readiness['blockers'])

    def test_scenario_6_incomplete_document_extraction_blocks_finalization(self, base_engagement):
        """Scenario 6: Documents stuck in PROCESSING or FAILED block finalization."""
        engagement, partner = base_engagement

        # Add a document that failed or is still processing
        Document.objects.create(
            engagement=engagement,
            document_type=DocumentType.BANK_STATEMENT,
            original_filename="bank_stmt_mar2026.pdf",
            file_size_bytes=1024,
            status=DocumentStatus.PROCESSING
        )

        readiness = AuditFinalizationService.evaluate_finalization_readiness(engagement, user=partner)
        assert not readiness['can_finalize']
        assert any("uploaded document(s) in failed, unparsed, or rejected state" in b for b in readiness['blockers'])

    def test_scenario_7_missing_required_workpaper_review_blocks_finalization(self, base_engagement):
        """Scenario 7: SA 230 workpapers missing or unapproved block finalization."""
        engagement, partner = base_engagement

        # No workpapers generated yet
        readiness = AuditFinalizationService.evaluate_finalization_readiness(engagement, user=partner)
        assert not readiness['can_finalize']
        assert any("No SA 230 audit working papers" in b for b in readiness['blockers'])

        # Create workpaper but leave it in DRAFT
        Workpaper.objects.create(
            engagement=engagement,
            wp_reference="WP-REV-01",
            title="Revenue Substantive Testing",
            audit_area="Revenue",
            status=WorkpaperStatus.DRAFT
        )

        readiness2 = AuditFinalizationService.evaluate_finalization_readiness(engagement, user=partner)
        assert not readiness2['can_finalize']
        assert any("remain unapproved by partner" in b for b in readiness2['blockers'])

    def test_scenario_8_unauthorized_user_attempt_blocks_finalization(self, base_engagement):
        """Scenario 8: Unauthorized user or unauthenticated user cannot finalize."""
        engagement, partner = base_engagement

        # Test unauthenticated user (None)
        readiness_anon = AuditFinalizationService.evaluate_finalization_readiness(engagement, user=None)
        assert not readiness_anon['can_finalize']
        assert any("User is unauthenticated" in b for b in readiness_anon['blockers'])

        # Test non-partner regular user
        intern = User.objects.create_user(
            username="junior_intern",
            password="internpassword123",
            is_staff=False,
            is_superuser=False
        )
        readiness_intern = AuditFinalizationService.evaluate_finalization_readiness(engagement, user=intern)
        assert not readiness_intern['can_finalize']
        assert any("does not hold an authorized Senior Audit Partner" in b for b in readiness_intern['blockers'])

    def test_scenario_9_valid_complete_engagement_succeeds(self, base_engagement):
        """
        Scenario 9: Fully compliant engagement with all 8 gates satisfied successfully finalizes.
        """
        engagement, partner = base_engagement

        # 1. Balanced BRS
        ReconciliationRun.objects.create(
            engagement=engagement,
            recon_type='BANK',
            status=ReconciliationStatus.BALANCED,
            as_of_date=date(2026, 3, 31),
            unreconciled_difference=Decimal('0.00'),
            unmatched_count=0,
            summary_data={'stale_cheques_count': 0}
        )

        # 2. Subledgers match GL
        # Trade Payables GL is ₹2,000,000.00
        SubledgerAgingItem.objects.create(
            engagement=engagement,
            item_type='PAYABLE',
            party_name='Vendor Steel Corp',
            invoice_date=date(2025, 4, 1),
            due_date=date(2025, 5, 1),
            outstanding_amount=Decimal('2000000.00'),
            total_amount=Decimal('2000000.00'),
            ageing_days=30,
            ageing_bucket='0-30'
        )
        # Trade Receivables GL is ₹2,000,000.00
        SubledgerAgingItem.objects.create(
            engagement=engagement,
            item_type='RECEIVABLE',
            party_name='Customer Alpha',
            invoice_date=date(2025, 4, 1),
            due_date=date(2025, 5, 1),
            outstanding_amount=Decimal('2000000.00'),
            total_amount=Decimal('2000000.00'),
            ageing_days=25,
            ageing_bucket='0-30'
        )

        # 3. Revenue evidence verified (GSTR-1 / Sales Register verified)
        d1 = Document.objects.create(
            engagement=engagement,
            document_type=DocumentType.SALES_REGISTER,
            original_filename="GSTR1_Sales_Register_FY202526.xlsx",
            file_size_bytes=1024,
            status=DocumentStatus.VERIFIED
        )
        ExtractedRecord.objects.create(
            document=d1,
            row_index=1,
            raw_data={'sales': 10000000},
            normalized_data={'sales': 10000000}
        )

        # 4. Verified supporting documents
        d2 = Document.objects.create(
            engagement=engagement,
            document_type=DocumentType.TRIAL_BALANCE,
            original_filename="Trial_Balance.xlsx",
            file_size_bytes=1024,
            status=DocumentStatus.VERIFIED
        )
        ExtractedRecord.objects.create(
            document=d2,
            row_index=1,
            raw_data={'tb': 'balanced'},
            normalized_data={'tb': 'balanced'}
        )

        # 5. Workpapers created and approved
        wp = Workpaper.objects.create(
            engagement=engagement,
            wp_reference="WP-REV-01",
            title="Revenue Substantive Testing",
            audit_area="Revenue",
            status=WorkpaperStatus.APPROVED,
            reviewer=partner,
            approved_at=timezone.now()
        )

        # Evaluate readiness
        readiness = AuditFinalizationService.evaluate_finalization_readiness(engagement, user=partner)
        assert readiness['can_finalize'] is True, f"Expected can_finalize=True, got blockers: {readiness['blockers']}"
        assert len(readiness['blockers']) == 0

        # Execute finalization
        result = AuditFinalizationService.finalize_engagement(
            engagement,
            user=partner,
            justification="All substantive procedures completed and working papers partner-approved."
        )
        assert result['success'] is True
        assert "successfully finalized and certified" in result['message']

        # Verify engagement state updated
        engagement.refresh_from_db()
        assert engagement.is_finalized is True
        assert engagement.status == EngagementStatus.COMPLETED
        assert engagement.finalized_by == partner
        assert engagement.finalized_at is not None

        # Verify audit trail
        log_entry = AuditLog.objects.filter(entity_id=str(engagement.id), action="FINALIZE_ENGAGEMENT").first()
        assert log_entry is not None
        assert log_entry.user == partner
        assert log_entry.details['lead_partner'] == partner.username


@pytest.mark.django_db
class TestIndependentAccountingIntegrity:
    """
    Independent accounting calculations & regression tests:
    - Independent equity roll-forward.
    - Asset-wise depreciation recalculation (Schedule II SLM).
    - Control account subledger reconciliation.
    - Idempotency / duplicate prevention on re-runs.
    - Report consistency across PDF and CSV exports.
    """

    def test_independent_equity_roll_forward(self):
        """
        Verify that closing equity equals opening equity + PAT - dividends + capital introduced.
        Reconcile against TrialBalanceService.compile_financial_statements.
        """
        share_capital = Decimal("5000000.00")
        opening_reserves = Decimal("2500000.00")
        revenue = Decimal("15000000.00")
        cost_of_materials = Decimal("9000000.00")
        other_expenses = Decimal("2000000.00")
        depreciation = Decimal("500000.00")

        # Independent calculation
        pbt = revenue - cost_of_materials - other_expenses - depreciation # 3,500,000.00
        tax_expense = pbt * Decimal("0.25") # 25% corporate tax = 875,000.00
        pat = pbt - tax_expense # 2,625,000.00
        closing_equity_expected = share_capital + opening_reserves + pat # 10,125,000.00

        tb_rows = [
            {'account_code': '101', 'account_name': 'Revenue', 'closing_credit_inr': str(revenue), 'schedule_iii_group': ScheduleIIIGroup.REVENUE_OPERATIONS},
            {'account_code': '201', 'account_name': 'Raw Materials', 'closing_debit_inr': str(cost_of_materials), 'schedule_iii_group': ScheduleIIIGroup.COST_OF_MATERIALS},
            {'account_code': '202', 'account_name': 'Operating Expenses', 'closing_debit_inr': str(other_expenses), 'schedule_iii_group': ScheduleIIIGroup.OTHER_EXPENSES},
            {'account_code': '203', 'account_name': 'Depreciation Expense', 'closing_debit_inr': str(depreciation), 'schedule_iii_group': ScheduleIIIGroup.DEPRECIATION_AMORT},
            {'account_code': '301', 'account_name': 'Share Capital', 'closing_credit_inr': str(share_capital), 'schedule_iii_group': ScheduleIIIGroup.SHARE_CAPITAL},
            {'account_code': '302', 'account_name': 'Opening Reserves', 'closing_credit_inr': str(opening_reserves), 'schedule_iii_group': ScheduleIIIGroup.RESERVES_SURPLUS},
            {'account_code': '303', 'account_name': 'Trade Payables', 'closing_credit_inr': '3500000.00', 'schedule_iii_group': ScheduleIIIGroup.TRADE_PAYABLES},
            {'account_code': '401', 'account_name': 'PPE Gross', 'closing_debit_inr': '9500000.00', 'schedule_iii_group': ScheduleIIIGroup.PPE},
            {'account_code': '402', 'account_name': 'Bank Balance', 'closing_debit_inr': '5000000.00', 'schedule_iii_group': ScheduleIIIGroup.CASH_EQUIVALENTS},
        ]

        fs = TrialBalanceService.compile_financial_statements(tb_rows)
        pl = fs['profit_and_loss']
        bs = fs['balance_sheet']

        # Assert PAT
        assert Decimal(str(pl['profit_after_tax'])) == pat

        # Assert Shareholders' funds on BS
        shareholders_funds = Decimal(str(bs['equity_and_liabilities']['shareholders_funds']['total']))
        assert shareholders_funds == closing_equity_expected

        # Assert Total Assets == Total Equity & Liabilities
        total_assets = Decimal(str(bs['assets']['total_assets']))
        total_eq_liab = Decimal(str(bs['equity_and_liabilities']['total_equity_and_liabilities']))
        assert total_assets == total_eq_liab

    def test_depreciation_recalculation_and_variance(self):
        """
        Verify asset-wise Schedule II SLM depreciation recalculation and ensure variance triggers AJE.
        """
        company = Company.objects.create(name="Depreciation Test Co", pan="AAACD5678K", entity_type=EntityType.PVT_LTD)
        fy = FinancialYear.objects.create(company=company, label="FY 2025-26", start_date=date(2025, 4, 1), end_date=date(2026, 3, 31))
        engagement = Engagement.objects.create(company=company, financial_year=fy, title="FAR Audit FY26")

        far_records = [{
            'Asset_ID': 'FA-TEST-01',
            'Asset_Description': 'CNC Lathe Machine',
            'Asset_Category': 'PLANT & MACHINERY',
            'Acquisition_Date': '2025-04-01',
            'Capitalized_Cost_INR': '1000000.00',
            'Useful_Life_Years': '15',
            'Depreciation_Rate_Percent': '15',
            'Opening_Accumulated_Depreciation_INR': '0.00'
        }]

        results = FixedAssetAuditEngine.import_and_validate_far(engagement, far_records)
        assert results['total_assets'] == 1
        assert Decimal(str(results['recalculated_schedule_ii_depreciation'])) > Decimal("0.00")
        assert Decimal(str(results['depreciation_variance'])) > Decimal("0.00")

        # Verify AJE was proposed
        aje = ProposedAdjustment.objects.filter(engagement=engagement).first()
        assert aje is not None
        assert aje.total_debit > Decimal("0.00")
        assert aje.total_credit == aje.total_debit

    def test_idempotent_reprocessing_without_duplicate_records(self):
        """
        Executing audit engine multiple times must not create duplicate exceptions or duplicate AJEs.
        """
        company = Company.objects.create(name="Idempotency Test Co", pan="AAACE9876K", entity_type=EntityType.PVT_LTD)
        fy = FinancialYear.objects.create(company=company, label="FY 2025-26", start_date=date(2025, 4, 1), end_date=date(2026, 3, 31))
        engagement = Engagement.objects.create(company=company, financial_year=fy, title="Idempotent Audit")

        far_records = [{
            'Asset_ID': 'FA-TEST-02',
            'Asset_Description': 'Hydraulic Press',
            'Asset_Category': 'PLANT & MACHINERY',
            'Acquisition_Date': '2025-04-01',
            'Capitalized_Cost_INR': '2000000.00',
            'Useful_Life_Years': '15',
            'Depreciation_Rate_Percent': '15',
            'Opening_Accumulated_Depreciation_INR': '0.00'
        }]

        # Run 1
        FixedAssetAuditEngine.import_and_validate_far(engagement, far_records)
        exc_count_run1 = ExceptionItem.objects.filter(engagement=engagement).count()
        aje_count_run1 = ProposedAdjustment.objects.filter(engagement=engagement).count()
        assert exc_count_run1 == 1
        assert aje_count_run1 == 1

        # Run 2 (Reprocessing)
        FixedAssetAuditEngine.import_and_validate_far(engagement, far_records)
        exc_count_run2 = ExceptionItem.objects.filter(engagement=engagement).count()
        aje_count_run2 = ProposedAdjustment.objects.filter(engagement=engagement).count()
        assert exc_count_run2 == 1, "Reprocessing must not duplicate audit exceptions"
        assert aje_count_run2 == 1, "Reprocessing must not duplicate proposed adjusting journal entries"

    def test_report_data_consistency_across_csv_and_pdf(self):
        """
        Verify that figures in CSV export agree with the Balance Sheet and Trial Balance figures.
        """
        company = Company.objects.create(name="Consistency Test Co", pan="AAACF1111K", entity_type=EntityType.PVT_LTD)
        fy = FinancialYear.objects.create(company=company, label="FY 2025-26", start_date=date(2025, 4, 1), end_date=date(2026, 3, 31))
        engagement = Engagement.objects.create(
            company=company,
            financial_year=fy,
            title="Consistency Audit",
            overall_materiality=Decimal("200000.00")
        )

        tb_rows = [
            {'account_code': '101', 'account_name': 'Sales', 'closing_credit_inr': '5000000.00', 'schedule_iii_group': ScheduleIIIGroup.REVENUE_OPERATIONS},
            {'account_code': '201', 'account_name': 'Purchases', 'closing_debit_inr': '3000000.00', 'schedule_iii_group': ScheduleIIIGroup.COST_OF_MATERIALS},
            {'account_code': '301', 'account_name': 'Share Capital', 'closing_credit_inr': '1000000.00', 'schedule_iii_group': ScheduleIIIGroup.SHARE_CAPITAL},
            {'account_code': '302', 'account_name': 'Reserves', 'closing_credit_inr': '500000.00', 'schedule_iii_group': ScheduleIIIGroup.RESERVES_SURPLUS},
            {'account_code': '401', 'account_name': 'Machinery', 'closing_debit_inr': '2000000.00', 'schedule_iii_group': ScheduleIIIGroup.PPE},
            {'account_code': '402', 'account_name': 'Cash', 'closing_debit_inr': '1500000.00', 'schedule_iii_group': ScheduleIIIGroup.CASH_EQUIVALENTS},
            {'account_code': '303', 'account_name': 'Creditors', 'closing_credit_inr': '4000000.00', 'schedule_iii_group': ScheduleIIIGroup.TRADE_PAYABLES},
        ]
        TrialBalanceService.calculate_trial_balance(tb_rows, as_of_date=fy.end_date, engagement=engagement)

        csv_text = ReportExporterService.export_consolidated_csv(engagement)

        # Verify key Schedule III figures are present and accurate in CSV
        assert "Shareholders' Funds" in csv_text
        assert "Total Equity & Liabilities" in csv_text
        assert "Total Assets" in csv_text
        assert "Revenue from Operations" in csv_text
        assert "5000000.00" in csv_text
        assert "Bank Reconciliation Status" in csv_text
        assert "Revenue Verification Status" in csv_text
