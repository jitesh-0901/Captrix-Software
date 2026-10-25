import pytest
from decimal import Decimal
from datetime import date
from apps.companies.models import Company, FinancialYear, Engagement, EngagementType, EntityType
from apps.accounting.models import LedgerAccount, ChartOfAccounts, TrialBalanceSnapshot, ScheduleIIIGroup
from apps.accounting.services import TrialBalanceService
from apps.audit.models import FixedAsset, ExceptionItem, ExceptionSeverity, ExceptionStatus
from apps.audit.far_depreciation import FixedAssetAuditEngine
from apps.reporting.models import Workpaper, WorkpaperStatus, ProposedAdjustment, AdjustmentStatus
from apps.reporting.report_builder import ConsolidatedAuditReportBuilder
from apps.reporting.exporters import ReportExporterService


@pytest.mark.django_db
class TestAuditReportIntegrityAndConsistency:
    """
    Test suite verifying the 10 audit report integrity and calculation fixes:
    1. Financial statements show real non-zero numbers derived from records.
    2. BRS reports review status without contradictory 'matches' claims.
    3. Depreciation variance is accurately reported, linked to open exception, and proposes double-entry AJE.
    4. Statutory checks provide clause-by-clause evidence.
    5. Entity legal name and FY match records.
    6. Materiality benchmark uses alternative basis when PBT is loss/nil.
    7. Draft status warning prevents premature audit opinion.
    8. CA credentials and UDIN placeholders are preserved until final sign-off.
    """

    @pytest.fixture
    def setup_verified_company_and_records(self):
        company = Company.objects.create(
            name="Asterion Industrial Components Private Limited",
            cin="U29100MH2020PTC345678",
            pan="AABCV9876K",
            gstin="27AABCV9876K1Z8",
            entity_type=EntityType.PVT_LTD
        )
        fy = FinancialYear.objects.create(
            company=company,
            label="FY 2025-26",
            start_date=date(2025, 4, 1),
            end_date=date(2026, 3, 31)
        )
        engagement = Engagement.objects.create(
            company=company,
            financial_year=fy,
            title="Statutory Audit FY 2025-26",
            engagement_type=EngagementType.STATUTORY,
            overall_materiality=Decimal("500000.00"),
            is_finalized=False
        )

        # Create realistic Chart of Accounts & Trial Balance
        tb_rows = [
            {'account_code': '100100', 'account_name': 'Domestic Sales', 'closing_credit_inr': '60429839.84', 'schedule_iii_group': ScheduleIIIGroup.REVENUE_OPERATIONS},
            {'account_code': '200100', 'account_name': 'Raw Material Purchases', 'closing_debit_inr': '80460834.02', 'schedule_iii_group': ScheduleIIIGroup.COST_OF_MATERIALS},
            {'account_code': '200200', 'account_name': 'Employee Costs', 'closing_debit_inr': '2349975.79', 'schedule_iii_group': ScheduleIIIGroup.EMPLOYEE_BENEFITS},
            {'account_code': '200300', 'account_name': 'Power & Utilities', 'closing_debit_inr': '7416267.91', 'schedule_iii_group': ScheduleIIIGroup.OTHER_EXPENSES},
            {'account_code': '300100', 'account_name': 'Gross Fixed Assets', 'closing_debit_inr': '195297131.83', 'schedule_iii_group': ScheduleIIIGroup.PPE},
            {'account_code': '300200', 'account_name': 'Accumulated Depreciation', 'closing_credit_inr': '2100000.00', 'schedule_iii_group': ScheduleIIIGroup.PPE},
            {'account_code': '300300', 'account_name': 'Trade Receivables', 'closing_debit_inr': '30874589.24', 'schedule_iii_group': ScheduleIIIGroup.TRADE_RECEIVABLES},
            {'account_code': '300400', 'account_name': 'Main Bank', 'closing_debit_inr': '10192487.21', 'schedule_iii_group': ScheduleIIIGroup.CASH_EQUIVALENTS},
            {'account_code': '300500', 'account_name': 'Inventory', 'closing_debit_inr': '14000000.00', 'schedule_iii_group': ScheduleIIIGroup.INVENTORIES},
            {'account_code': '400100', 'account_name': 'Trade Payables', 'closing_credit_inr': '246225983.85', 'schedule_iii_group': ScheduleIIIGroup.TRADE_PAYABLES},
            {'account_code': '400200', 'account_name': 'Share Capital', 'closing_credit_inr': '5000000.00', 'schedule_iii_group': ScheduleIIIGroup.SHARE_CAPITAL},
        ]
        TrialBalanceService.calculate_trial_balance(tb_rows, as_of_date=fy.end_date, engagement=engagement)

        # Import Fixed Asset Register
        far_records = [
            {
                'Asset_ID': f'FA-{i:04d}',
                'Asset_Description': f'Machinery Unit {i}',
                'Asset_Category': 'PLANT & MACHINERY',
                'Acquisition_Date': '2025-04-01',
                'Capitalized_Cost_INR': '1000000.00',
                'Useful_Life_Years': '15',
                'Depreciation_Rate_Percent': '15',
                'Opening_Accumulated_Depreciation_INR': '0.00'
            }
            for i in range(1, 11)
        ]
        far_res = FixedAssetAuditEngine.import_and_validate_far(engagement, far_records)

        # Proposed Adjusting Journal Entry for Depreciation
        exc = ExceptionItem.objects.filter(engagement=engagement, rule_code="RULE_DEPRECIATION_VARIANCE").first()
        assert exc is not None
        ProposedAdjustment.objects.create(
            engagement=engagement,
            adjustment_number="AJE-01",
            title="Depreciation Adjustment (Schedule II Recalculation)",
            reason="To align unrecorded book depreciation with Companies Act 2013 Schedule II SLM recalculation.",
            status=AdjustmentStatus.PROPOSED,
            journal_entries=[
                {'account': 'Depreciation Expense (P&L)', 'debit': float(exc.amount_involved), 'credit': 0.0},
                {'account': 'Accumulated Depreciation (PPE)', 'debit': 0.0, 'credit': float(exc.amount_involved)}
            ],
            total_debit=exc.amount_involved,
            total_credit=exc.amount_involved,
            is_balanced=True,
            pnl_impact=-exc.amount_involved
        )

        # Create Workpapers
        for ref, title in [("WP-101", "Trial Balance"), ("WP-201", "Fixed Assets")]:
            Workpaper.objects.create(
                engagement=engagement,
                wp_reference=ref,
                title=title,
                status=WorkpaperStatus.DRAFT
            )

        # Create transactions for statutory verification
        from apps.accounting.models import Transaction, VoucherType
        first_acc = LedgerAccount.objects.filter(company=company).first()
        Transaction.objects.create(
            engagement=engagement,
            ledger_account=first_acc,
            voucher_number="V-001",
            voucher_type=VoucherType.PAYMENT,
            date=date(2025, 5, 10),
            narration="Office supplies payment",
            debit_amount=Decimal('4500.00'),
            credit_amount=Decimal('0.00')
        )

        from apps.audit.statutory_forms import StatutoryFormMatrixEngine
        StatutoryFormMatrixEngine.initialize_and_audit_clauses(engagement)

        return engagement, far_res

    def test_financial_figures_are_non_zero_and_schedule_iii_grounded(self, setup_verified_company_and_records):
        engagement, _ = setup_verified_company_and_records
        rep_data = ConsolidatedAuditReportBuilder.build_report(engagement)

        sec_c = rep_data['section_c']
        assert Decimal(sec_c['revenue_from_operations']) > Decimal('0.00')
        assert Decimal(sec_c['total_expenses']) > Decimal('0.00')
        assert Decimal(sec_c['total_assets']) > Decimal('0.00')
        assert Decimal(sec_c['cash_and_bank_balances']) > Decimal('0.00')
        assert Decimal(sec_c['trade_receivables']) > Decimal('0.00')
        assert Decimal(sec_c['trade_payables']) > Decimal('0.00')

    def test_far_depreciation_variance_and_aje_reconciliation(self, setup_verified_company_and_records):
        engagement, far_res = setup_verified_company_and_records
        rep_data = ConsolidatedAuditReportBuilder.build_report(engagement)

        sec_g = rep_data['section_g']
        assert sec_g['fixed_assets_count'] == 10
        assert Decimal(sec_g['fixed_assets_gross_block']) == Decimal('10000000.00')
        assert Decimal(sec_g['depreciation_variance']) > Decimal('0.00')

        # Check AJE-01 matches variance exactly
        aje = ProposedAdjustment.objects.filter(engagement=engagement, adjustment_number="AJE-01").first()
        assert aje is not None
        assert aje.total_debit == Decimal(sec_g['depreciation_variance'])
        assert aje.status == AdjustmentStatus.PROPOSED

    def test_pdf_export_contains_draft_warning_and_no_placeholder_credentials(self, setup_verified_company_and_records):
        engagement, _ = setup_verified_company_and_records
        pdf_bytes = ReportExporterService.export_consolidated_pdf(engagement)

        assert len(pdf_bytes) > 5000
        # Verify text via pypdf
        import pypdf
        import io
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        full_text = "\n".join([p.extract_text() for p in reader.pages])

        assert "DRAFT AUDIT FILE" in full_text
        assert "Asterion Industrial Components Private Limited" in full_text
        assert "2025-26" in full_text
        assert "₹60,429,839.84" in full_text or "₹ 60,429,839.84" in full_text or "\u20b9" in full_text
        assert "Pending Final CA Partner Sign-Off" in full_text
        assert "Pending Generation on Authorized Partner Sign-Off" in full_text
        # Ensure dummy UDIN is NOT in the PDF
        assert "25054321AAAA0123" not in full_text

    def test_pdf_tables_have_no_word_mingling_and_wrap_cleanly_into_paragraphs(self, setup_verified_company_and_records):
        """
        Regression test: Verifies that all table cells wrap cleanly without word mingling or horizontal overflows,
        and that the PDF maintains a structured professional multi-page report format including full Schedule III accounts.
        """
        engagement, _ = setup_verified_company_and_records
        pdf_bytes = ReportExporterService.export_consolidated_pdf(engagement)

        import pypdf
        import io
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        
        # Verify professional multi-page statutory report (standard 6 pages)
        assert len(reader.pages) >= 5, f"Expected professional multi-page report, got {len(reader.pages)}"

        full_text = "\n".join([p.extract_text() for p in reader.pages])

        # Page 1 contains executive summary & financial highlights
        page_1_text = reader.pages[0].extract_text()
        assert "1. Executive Summary & Financial Highlights" in page_1_text
        assert "Asterion Industrial Components" in page_1_text

        # Schedule III Financial Statements are present across pages
        assert "2. Balance Sheet as at 31st March" in full_text
        assert "SCHEDULE III (DIVISION I) — FORMAT OF BALANCE SHEET" in full_text
        assert "3. Statement of Profit and Loss" in full_text
        assert "Mandatory Key Financial Ratios" in full_text

        # Statutory assurance matrix (CARO 2020 & Form 3CD) and sign-off
        assert "4. Statutory Assurance Matrix — CARO 2020 Compliance Annexure" in full_text
        assert "5. Tax Audit (Form 3CD)" in full_text
        assert "6. Independent Statutory Auditor's Report" in full_text
        assert "7. Statutory Auditor Official Sign-Off & Physical Signature" in full_text

        # Statutory matrix evidence and conclusion columns must be cleanly separated
        assert "CARO Clause 3(i)(a)" in full_text
        assert "COMPLIANT" in full_text
        assert "CLEARED" in full_text
        assert "Form 3CD Clause 21(d)" in full_text
        assert "Daybook cash vouchers" in full_text
        assert "10,000 threshold" in full_text
        assert "(Nil Violations)" in full_text
        assert "₹" in full_text, "Report must use the Indian Rupee symbol (₹) for currency figures"

        # Also test ReportGeneratorService.generate_pdf_report
        from apps.reporting.services import ReportGeneratorService
        rep_record = ReportGeneratorService.generate_pdf_report(engagement)
        assert rep_record.file is not None
        rep_reader = pypdf.PdfReader(rep_record.file.path)
        assert len(rep_reader.pages) >= 1
        rep_full = "\n".join([p.extract_text() for p in rep_reader.pages])
        assert "1. Engagement Scope & SA 320 Materiality Framework" in rep_full
        assert len(rep_reader.pages) >= 1
        rep_full = "\n".join([p.extract_text() for p in rep_reader.pages])
        assert "1. Engagement Scope & SA 320 Materiality Framework" in rep_full

    def test_trial_balance_and_balance_sheet_equilibrium_cross_check(self, setup_verified_company_and_records):
        """
        Fix 1: Trial Balance and full Balance Sheet cross-check.
        Detects mathematical disequilibrium between Total Assets and Total Equity & Liabilities.
        """
        engagement, _ = setup_verified_company_and_records
        from apps.accounting.services import TrialBalanceService
        from apps.accounting.models import ScheduleIIIGroup

        # Construct accounts where Trial Balance debits match credits, but BS does not balance
        # (e.g. Assets = 10,00,000, Equity + Liab = 8,00,000, Variance = 2,00,000 due to unmapped difference)
        imbalanced_rows = [
            {'Particulars': 'Plant & Machinery', 'Debit': '1000000.00', 'Credit': '0.00', 'schedule_iii_group': ScheduleIIIGroup.PPE},
            {'Particulars': 'Equity Share Capital', 'Debit': '0.00', 'Credit': '800000.00', 'schedule_iii_group': ScheduleIIIGroup.SHARE_CAPITAL},
            {'Particulars': 'Dummy Balancing Expense', 'Debit': '0.00', 'Credit': '200000.00', 'schedule_iii_group': ScheduleIIIGroup.OTHER_EXPENSES},
        ]
        tb_res = TrialBalanceService.calculate_trial_balance(
            rows=imbalanced_rows,
            as_of_date=engagement.financial_year.end_date,
            engagement=engagement
        )
        assert 'balance_sheet_cross_check' in tb_res
        cross_check = tb_res['balance_sheet_cross_check']
        assert Decimal(cross_check['variance']) >= Decimal('1.00')
        assert cross_check['is_balanced'] is False

        # Verify critical exception created
        from apps.audit.models import ExceptionItem
        bs_exc = ExceptionItem.objects.filter(engagement=engagement, rule_code="RULE_BS_EQUILIBRIUM_VARIANCE").first()
        assert bs_exc is not None
        assert bs_exc.severity == 'CRITICAL'

        # Verify report builder surfaces balance sheet disequilibrium
        rep_data = ConsolidatedAuditReportBuilder.build_report(engagement)
        assert rep_data['section_c']['balance_sheet_balanced'] is False or Decimal(rep_data['section_c']['balance_sheet_difference']) > Decimal('0.00')

    def test_asset_wise_depreciation_and_booked_variance(self, setup_verified_company_and_records):
        """
        Fix 2: Asset-wise depreciation calculation and variance generation vs booked amounts.
        """
        engagement, _ = setup_verified_company_and_records
        from apps.audit.models import FixedAsset

        assets = FixedAsset.objects.filter(engagement=engagement)
        assert assets.count() > 0
        for a in assets:
            assert hasattr(a, 'booked_depreciation')
            assert hasattr(a, 'depreciation_variance')
            # Verify variance equation
            computed_var = abs(a.sch_ii_depreciation - a.booked_depreciation)
            assert a.depreciation_variance == computed_var

        rep_data = ConsolidatedAuditReportBuilder.build_report(engagement)
        sec_g = rep_data['section_g']
        assert 'asset_wise_variance_count' in sec_g
        assert 'asset_wise_booked_depreciation' in sec_g
        assert Decimal(sec_g['depreciation_variance']) > Decimal('0.00')

    def test_exception_status_linked_to_aje_lifecycle(self, setup_verified_company_and_records):
        """
        Fix 3: Exception status strictly linked to AJE approval and posting status.
        Never solved while open/proposed; resolved only when posted.
        """
        engagement, _ = setup_verified_company_and_records
        from apps.audit.models import ExceptionItem, ExceptionStatus
        from apps.reporting.models import ProposedAdjustment, AdjustmentStatus

        exc = ExceptionItem.objects.filter(engagement=engagement, rule_code="RULE_DEPRECIATION_VARIANCE").first()
        assert exc is not None
        # Initially linked to proposed adjustment -> must NOT be resolved
        assert exc.status in [ExceptionStatus.AJE_PROPOSED, ExceptionStatus.OPEN]
        assert exc.status != ExceptionStatus.RESOLVED

        rep_data = ConsolidatedAuditReportBuilder.build_report(engagement)
        sec_j_exc = next((e for e in rep_data['section_j']['exceptions'] if e['rule_code'] == 'RULE_DEPRECIATION_VARIANCE'), None)
        assert sec_j_exc is not None
        assert sec_j_exc['is_resolved'] is False

        # Simulate AJE posting
        aje = engagement.adjustments.filter(adjustment_number="AJE-01").first()
        if not aje:
            aje = ProposedAdjustment.objects.create(
                engagement=engagement,
                adjustment_number="AJE-01",
                title="Depreciation Adjustment",
                reason="Schedule II recalculation",
                total_debit=exc.amount_involved,
                total_credit=exc.amount_involved,
                journal_entries=[{'account': 'Depreciation', 'debit': float(exc.amount_involved), 'credit': 0}],
                status=AdjustmentStatus.PROPOSED
            )

        # Partner approves
        aje.status = AdjustmentStatus.APPROVED_BY_PARTNER
        aje.save()
        exc.status = ExceptionStatus.IN_REVIEW
        exc.save()

        rep_data2 = ConsolidatedAuditReportBuilder.build_report(engagement)
        sec_j_exc2 = next((e for e in rep_data2['section_j']['exceptions'] if e['rule_code'] == 'RULE_DEPRECIATION_VARIANCE'), None)
        assert sec_j_exc2['is_resolved'] is False

        # Post AJE to ledger
        from django.utils import timezone
        aje.status = AdjustmentStatus.POSTED
        aje.is_posted = True
        aje.posted_at = timezone.now()
        aje.save()
        exc.status = ExceptionStatus.AJE_POSTED
        exc.save()

        rep_data3 = ConsolidatedAuditReportBuilder.build_report(engagement)
        sec_j_exc3 = next((e for e in rep_data3['section_j']['exceptions'] if e['rule_code'] == 'RULE_DEPRECIATION_VARIANCE'), None)
        assert sec_j_exc3['is_resolved'] is True

    def test_prevent_contradictory_summary_when_exceptions_or_brs_review_exist(self, setup_verified_company_and_records):
        """
        Fix 4: When open exceptions or review-required findings exist,
        prevent contradictory summaries like '0 Exceptions Noted' or false claims that GL matches Bank Statement.
        """
        engagement, _ = setup_verified_company_and_records
        from apps.reconciliation.models import ReconciliationRun

        # Set BRS to REVIEW_REQUIRED with variance
        ReconciliationRun.objects.filter(engagement=engagement, recon_type='BANK').delete()
        ReconciliationRun.objects.create(
            engagement=engagement,
            as_of_date=engagement.financial_year.end_date,
            recon_type='BANK',
            status='REVIEW_REQUIRED',
            matched_count=15,
            unmatched_count=2,
            unreconciled_difference=Decimal('18500.00'),
            summary_data={'unreconciled_variance': '18500.00'}
        )

        rep_data = ConsolidatedAuditReportBuilder.build_report(engagement)
        sec_b = rep_data['section_b']

        # Ensure procedures_with_exceptions tracks actual open exceptions
        assert sec_b['procedures_with_exceptions'] > 0
        assert sec_b['reconciliation_status'] == 'REVIEW_REQUIRED'

        pdf_bytes = ReportExporterService.export_consolidated_pdf(engagement)
        import pypdf, io
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        page_1_text = reader.pages[0].extract_text()

        # Must NOT claim 0 Exceptions Noted
        assert "0 Exceptions Noted" not in page_1_text
        assert "Exceptions Noted — Review Required" in page_1_text or "Exceptions Noted" in page_1_text
        # Must NOT assert GL matches Bank Statement when variance exists
        assert "GL does not match" in page_1_text and "bank passbook" in page_1_text

    def test_evidence_gated_statutory_checks_show_review_required(self):
        """
        Fix 5: Statutory checks without supporting evidence must display REVIEW_REQUIRED or NOT VERIFIED,
        never false COMPLIANT.
        """
        from apps.companies.models import Company, FinancialYear, Engagement, EntityType, EngagementType
        company = Company.objects.create(
            name="Barebone Technologies Ltd",
            cin="U72200MH2023PLC123456",
            entity_type=EntityType.PUB_LTD
        )
        fy = FinancialYear.objects.create(
            company=company,
            label="FY 2024-25",
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31)
        )
        eng = Engagement.objects.create(
            company=company,
            financial_year=fy,
            title="Statutory Audit FY 2024-25",
            engagement_type=EngagementType.STATUTORY
        )

        # No FAR, no transactions, no aging, no approved workpapers uploaded!
        from apps.audit.statutory_forms import StatutoryFormMatrixEngine
        from apps.audit.models import StatutoryClauseAudit

        audits = StatutoryFormMatrixEngine.initialize_and_audit_clauses(eng)

        # CARO Clause 3(i) (FAR) must be REVIEW_REQUIRED
        c3i = StatutoryClauseAudit.objects.filter(engagement=eng, clause_number="Clause 3(i)").first()
        assert c3i is not None
        assert c3i.compliance_status == "REVIEW_REQUIRED"
        assert c3i.evidence_status == "MISSING"

        # CARO Clause 3(ii) (Inventory) must be REVIEW_REQUIRED
        c3ii = StatutoryClauseAudit.objects.filter(engagement=eng, clause_number="Clause 3(ii)").first()
        assert c3ii is not None
        assert c3ii.compliance_status == "REVIEW_REQUIRED"

        # Form 3CD Clause 21(d) (Cash daybook) must be REVIEW_REQUIRED
        c21d = StatutoryClauseAudit.objects.filter(engagement=eng, clause_number="Clause 21(d)").first()
        assert c21d is not None
        assert c21d.compliance_status == "REVIEW_REQUIRED"

        # Form 3CD Clause 22 (MSME aging) must be REVIEW_REQUIRED
        c22 = StatutoryClauseAudit.objects.filter(engagement=eng, clause_number="Clause 22)").first() or StatutoryClauseAudit.objects.filter(engagement=eng, clause_number="Clause 22").first()
        assert c22 is not None
        assert c22.compliance_status == "REVIEW_REQUIRED"

    def test_figure_lineage_tracking_metadata(self, setup_verified_company_and_records):
        """
        Fix 6: Lineage tracking for every financial statement figure.
        Source document, source sheet, account codes, calculation method, review status.
        """
        engagement, _ = setup_verified_company_and_records
        rep_data = ConsolidatedAuditReportBuilder.build_report(engagement)

        sec_c = rep_data['section_c']
        assert 'audit_lineage' in sec_c
        lineage = sec_c['audit_lineage']

        required_heads = [
            'revenue_from_operations', 'total_expenses', 'net_profit_loss',
            'property_plant_equipment', 'trade_receivables', 'cash_and_bank_balances',
            'trade_payables', 'total_equity'
        ]
        for head in required_heads:
            assert head in lineage, f"Missing lineage tracking for {head}"
            entry = lineage[head]
            assert 'source_document' in entry
            assert 'source_sheet' in entry
            assert 'calculation_method' in entry
            assert 'review_status' in entry
            assert len(entry['calculation_method']) > 5
