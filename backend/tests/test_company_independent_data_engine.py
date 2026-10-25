import pytest
import io
import csv
from decimal import Decimal
from datetime import date, timedelta
from django.utils import timezone
from apps.companies.models import Company, FinancialYear, Engagement, EntityType, EngagementType
from apps.accounting.models import ChartOfAccounts, LedgerAccount, TrialBalanceSnapshot, Transaction
from apps.accounting.services import TrialBalanceService
from apps.reconciliation.models import ReconciliationRun, ReconciliationStatus, ReconciliationItem
from apps.reconciliation.services import BankReconciliationEngine, CrossDocumentReconciliationEngine
from apps.audit.models import FixedAsset, SubledgerAgingItem, ExceptionItem, ExceptionSeverity, ExceptionStatus
from apps.audit.far_depreciation import FixedAssetAuditEngine
from apps.reporting.models import Workpaper, WorkpaperStatus, ProposedAdjustment
from apps.reporting.report_builder import ConsolidatedAuditReportBuilder
from apps.reporting.exporters import ReportExporterService
from apps.reporting.integrity_gate import ReportIntegrityGateService


@pytest.mark.django_db
class TestCompanyIndependentDataEngine:
    """
    Test suite verifying that Captrix parses, normalizes, reconciles, and reports
    data across diverse companies, format variations, and accounting structures
    using 100% deterministic source-backed calculations.
    """

    @pytest.fixture
    def setup_diverse_companies(self):
        # Company A: Zenith Manufacturing (Private Limited)
        comp_a = Company.objects.create(
            name="Zenith Industrial Solutions Private Limited",
            cin="U29200KA2021PTC123456",
            pan="AAACZ1234K",
            entity_type=EntityType.PVT_LTD
        )
        fy_a = FinancialYear.objects.create(
            company=comp_a,
            label="FY 2025-26",
            start_date=date(2025, 4, 1),
            end_date=date(2026, 3, 31),
            is_closed=False
        )
        eng_a = Engagement.objects.create(
            company=comp_a,
            financial_year=fy_a,
            title="Zenith Statutory Audit FY 2025-26",
            engagement_type=EngagementType.STATUTORY
        )

        # Company B: Horizon Software Technologies (Public Limited)
        comp_b = Company.objects.create(
            name="Horizon Cloud Services Limited",
            cin="L72200DL2018PLC654321",
            pan="AABCH5678L",
            entity_type=EntityType.PUB_LTD
        )
        fy_b = FinancialYear.objects.create(
            company=comp_b,
            label="FY 2025-26",
            start_date=date(2025, 4, 1),
            end_date=date(2026, 3, 31),
            is_closed=False
        )
        eng_b = Engagement.objects.create(
            company=comp_b,
            financial_year=fy_b,
            title="Horizon Statutory Audit FY 2025-26",
            engagement_type=EngagementType.STATUTORY
        )

        return {'comp_a': comp_a, 'eng_a': eng_a, 'comp_b': comp_b, 'eng_b': eng_b}

    def test_tenant_isolation_prevents_cross_company_data_leakage(self, setup_diverse_companies):
        """
        Verify complete multi-tenant isolation between Zenith and Horizon.
        """
        eng_a = setup_diverse_companies['eng_a']
        eng_b = setup_diverse_companies['eng_b']

        # Create records for Company A
        coa_a = ChartOfAccounts.objects.create(company=eng_a.company, account_code='100100', account_name='HDFC Bank', account_type='ASSET')
        LedgerAccount.objects.create(company=eng_a.company, coa=coa_a, code='100100', name='HDFC Bank', closing_balance=Decimal('500000.00'))
        Workpaper.objects.create(engagement=eng_a, wp_reference='WP-A-01', title='Zenith Cash & Bank WP', status=WorkpaperStatus.APPROVED)

        # Create records for Company B
        coa_b = ChartOfAccounts.objects.create(company=eng_b.company, account_code='100200', account_name='SBI Bank', account_type='ASSET')
        LedgerAccount.objects.create(company=eng_b.company, coa=coa_b, code='100200', name='SBI Bank', closing_balance=Decimal('1200000.00'))
        Workpaper.objects.create(engagement=eng_b, wp_reference='WP-B-01', title='Horizon Bank WP', status=WorkpaperStatus.PREPARED)

        # Verify Isolation
        assert LedgerAccount.objects.filter(company=eng_a.company).count() == 1
        assert LedgerAccount.objects.filter(company=eng_b.company).count() == 1
        assert LedgerAccount.objects.filter(company=eng_a.company, code='100200').count() == 0
        assert Workpaper.objects.filter(engagement=eng_a).count() == 1
        assert Workpaper.objects.filter(engagement=eng_b).count() == 1

        rep_a = ConsolidatedAuditReportBuilder.build_report(eng_a)
        rep_b = ConsolidatedAuditReportBuilder.build_report(eng_b)
        assert rep_a['company_name'] == "Zenith Industrial Solutions Private Limited"
        assert rep_b['company_name'] == "Horizon Cloud Services Limited"

    def test_fail_closed_unmapped_accounts_block_finalization(self, setup_diverse_companies):
        """
        Verify that an unmapped account is flagged as UNMAPPED/REVIEW_REQUIRED,
        surfaced in Section E, and blocks final audit sign-off.
        """
        eng = setup_diverse_companies['eng_a']
        # Account without ChartOfAccounts mapping
        LedgerAccount.objects.create(
            company=eng.company,
            code='999999',
            name='Suspense / Unidentified Clearing',
            closing_balance=Decimal('45000.00'),
            mapping_status='UNMAPPED',
            is_suspense=True
        )

        rep = ConsolidatedAuditReportBuilder.build_report(eng)
        sec_e = rep['section_e']
        assert sec_e['unmapped_accounts_count'] >= 1
        assert sec_e['unmapped_accounts_alert'] is True

        # Integrity Gate check
        gate_res = ReportIntegrityGateService.evaluate_integrity(eng)
        assert gate_res['is_ready_for_final_issue'] is False
        assert gate_res['opinion_allowed'] is False
        assert len(gate_res['blockers']) > 0

    def test_format_valid_ca_details_never_count_as_external_verification(self, setup_diverse_companies):
        """A plausible membership number/FRN/UDIN must not authorize a final report by itself."""
        eng = setup_diverse_companies['eng_a']
        gate_res = ReportIntegrityGateService.evaluate_integrity(
            eng,
            ca_credentials={
                'membership_no': '542891',
                'firm_reg_no': '124859W',
                'udin': '26542891A1B2C3D4E5',
                'partner_affirmation': True,
                # No trusted verification flags or authorization record are supplied.
            },
        )
        assert gate_res['is_ready_for_final_issue'] is False
        assert gate_res['opinion_allowed'] is False
        assert gate_res['gate_statuses']['credentials_and_signoff_gate']['passed'] is False
        assert any('trusted server-side workflow' in blocker for blocker in gate_res['blockers'])

    def test_brs_stale_cheque_detection_under_ni_act_sec_138(self, setup_diverse_companies):
        """
        Verify that cheques issued >90 days prior to balance sheet date are
        identified as STALE_CHEQUE_UNPRESENTED under NI Act Sec 138 and
        force reconciliation status to REVIEW_REQUIRED.
        """
        eng = setup_diverse_companies['eng_a']
        as_of = eng.financial_year.end_date  # 2026-03-31

        cashbook_items = [
            # Recent cheque (within 30 days) -> Valid timing difference
            {'date': '2026-03-15', 'ref': 'CHQ-001', 'desc': 'Vendor Payment Recent', 'amount': '50000.00', 'type': 'WITHDRAWAL'},
            # Stale cheque (issued in May 2025 -> >300 days old)
            {'date': '2025-05-10', 'ref': 'CHQ-STALE', 'desc': 'Old Vendor Payment', 'amount': '125000.00', 'type': 'WITHDRAWAL'},
        ]
        bank_items = []  # Neither presented

        starting_cash = Decimal('1000000.00')
        # Statement balance = 1000000 + 50000 + 125000 = 1175000
        actual_stmt = Decimal('1175000.00')

        recon = BankReconciliationEngine.execute_reconciliation(
            engagement=eng,
            as_of_date=as_of,
            cashbook_items=cashbook_items,
            bank_items=bank_items,
            starting_cashbook_balance=starting_cash,
            actual_statement_balance=actual_stmt
        )

        assert recon.status == ReconciliationStatus.REVIEW_REQUIRED
        s_data = recon.summary_data
        assert s_data['stale_cheques_count'] == 1
        assert Decimal(s_data['stale_cheques_amount']) == Decimal('125000.00')
        assert s_data['valid_timing_count'] == 1
        assert Decimal(s_data['valid_timing_amount']) == Decimal('50000.00')
        assert "NI Act Sec 138" in s_data['review_required_reason']

    def test_three_way_depreciation_reconciliation_and_dual_statements(self, setup_diverse_companies):
        """
        Verify the three-way depreciation reconciliation:
        TB Booked vs FAR Booked vs Schedule II SLM Recalculated,
        and verify that both unadjusted and proposed-adjusted balance sheets are in 100% equilibrium.
        """
        eng = setup_diverse_companies['eng_b']

        # Setup TB with Share Capital 5M, Cash 20M, PPE 30M, Revenue 15M, Expenses 10M
        coa_cap = ChartOfAccounts.objects.create(company=eng.company, account_code='300100', account_name='Share Capital', account_type='EQUITY', schedule_iii_group='SHARE_CAPITAL')
        coa_ppe = ChartOfAccounts.objects.create(company=eng.company, account_code='150100', account_name='Plant & Machinery', account_type='ASSET', schedule_iii_group='PPE')
        coa_cash = ChartOfAccounts.objects.create(company=eng.company, account_code='100100', account_name='Bank Balance', account_type='ASSET', schedule_iii_group='CASH_EQUIVALENTS')
        coa_rev = ChartOfAccounts.objects.create(company=eng.company, account_code='400100', account_name='Service Turnover', account_type='INCOME', schedule_iii_group='REVENUE_OPERATIONS')
        coa_exp = ChartOfAccounts.objects.create(company=eng.company, account_code='500100', account_name='Staff Costs', account_type='EXPENSE', schedule_iii_group='EMPLOYEE_BENEFITS')

        LedgerAccount.objects.create(company=eng.company, coa=coa_cap, code='300100', name='Share Capital', closing_balance=Decimal('45000000.00'), closing_balance_type='Cr')
        LedgerAccount.objects.create(company=eng.company, coa=coa_ppe, code='150100', name='Plant & Machinery', closing_balance=Decimal('30000000.00'), closing_balance_type='Dr')
        LedgerAccount.objects.create(company=eng.company, coa=coa_cash, code='100100', name='Bank Balance', closing_balance=Decimal('20000000.00'), closing_balance_type='Dr')
        LedgerAccount.objects.create(company=eng.company, coa=coa_rev, code='400100', name='Service Turnover', closing_balance=Decimal('15000000.00'), closing_balance_type='Cr')
        LedgerAccount.objects.create(company=eng.company, coa=coa_exp, code='500100', name='Staff Costs', closing_balance=Decimal('10000000.00'), closing_balance_type='Dr')

        # TB Booked Depreciation is ₹0.00 (Unrecorded)
        TrialBalanceSnapshot.objects.create(
            engagement=eng,
            as_of_date=eng.financial_year.end_date,
            total_debits=Decimal('60000000.00'),
            total_credits=Decimal('60000000.00'),
            difference_amount=Decimal('0.00'),
            is_balanced=True
        )

        # Create Fixed Asset in FAR: Cost 30M, Booked Depn 2.5M, Schedule II Recalculated 3.0M
        FixedAsset.objects.create(
            engagement=eng,
            asset_id="AST-001",
            asset_name="Server Infrastructure",
            category="COMPUTERS & SERVERS",
            acquisition_date=date(2025, 4, 1),
            original_cost=Decimal('30000000.00'),
            useful_life_years=Decimal('5.00'),
            booked_depreciation=Decimal('2500000.00'),
            sch_ii_depreciation=Decimal('3000000.00'),
            depreciation_variance=Decimal('500000.00')
        )

        # Create Proposed Adjusting Journal Entry (AJE-01) for unrecorded depreciation
        ProposedAdjustment.objects.create(
            engagement=eng,
            adjustment_number="AJE-01",
            title="Depreciation Recalculation Adjustment",
            reason="Align book depreciation with Companies Act 2013 Schedule II SLM",
            total_debit=Decimal('3000000.00'),
            total_credit=Decimal('3000000.00'),
            is_posted=False
        )

        rep = ConsolidatedAuditReportBuilder.build_report(eng)
        sec_g = rep['section_g']
        sec_c = rep['section_c']

        # Verify 3-way depreciation values
        assert Decimal(sec_g['tb_depreciation_recorded']) == Decimal('0.00')
        assert Decimal(sec_g['far_depreciation_recorded']) == Decimal('2500000.00')
        assert Decimal(sec_g['schedule_ii_recalculated_depreciation']) == Decimal('3000000.00')
        assert Decimal(sec_g['tb_vs_far_depreciation_variance']) == Decimal('2500000.00')
        assert Decimal(sec_g['far_vs_sch_ii_depreciation_variance']) == Decimal('500000.00')

        # Verify Dual Comparative Statements
        comp_stmts = sec_c['comparative_statements']
        unadj = comp_stmts['unadjusted']
        adj = comp_stmts['proposed_adjusted']

        # Unadjusted: Expenses 10M, Net Profit (PAT) 3.75M, PPE 30M, Total Assets 50M
        assert Decimal(unadj['total_expenses']) == Decimal('10000000.00')
        assert Decimal(unadj['pbt']) == Decimal('3750000.00')
        assert Decimal(unadj['ppe_carrying_amount']) == Decimal('30000000.00')
        assert Decimal(unadj['total_assets']) == Decimal('50000000.00')
        assert unadj['is_balanced'] is True

        # Proposed-Adjusted: Expenses 13M, Net Profit (PAT post 3M AJE) 750k, PPE 27M, Total Assets 47M
        assert Decimal(adj['total_expenses']) == Decimal('13000000.00')
        assert Decimal(adj['pbt']) == Decimal('750000.00')
        assert Decimal(adj['ppe_carrying_amount']) == Decimal('27000000.00')
        assert Decimal(adj['total_assets']) == Decimal('47000000.00')
        # Crucial: Proposed adjusted statement must be in 100% double-entry equilibrium!
        assert adj['is_balanced'] is True

    def test_msme_subledger_to_control_variance_reconciliation(self, setup_diverse_companies):
        """
        Verify subledger-to-control payables reconciliation and Section 43B(h) overdue identification.
        """
        eng = setup_diverse_companies['eng_a']

        # TB Control Account 200200 has ₹2,000,000.00
        coa_ap = ChartOfAccounts.objects.create(company=eng.company, account_code='200200', account_name='Trade Payables Control', account_type='LIABILITY', schedule_iii_group='TRADE_PAYABLES')
        LedgerAccount.objects.create(company=eng.company, coa=coa_ap, code='200200', name='Trade Payables Control', closing_balance=Decimal('2000000.00'), closing_balance_type='Cr')

        # Subledger Aging only has 2 invoices totaling ₹1,200,000.00 (Variance = ₹800,000.00)
        SubledgerAgingItem.objects.create(
            engagement=eng,
            party_name="Precision Tooling MSME",
            invoice_number="INV-MSME-01",
            invoice_date=date(2026, 1, 15),
            due_date=date(2026, 2, 15),
            item_type='PAYABLE',
            outstanding_amount=Decimal('400000.00'),
            is_msme=True,
            is_overdue_43bh=True,
            overdue_days_msme=60
        )
        SubledgerAgingItem.objects.create(
            engagement=eng,
            party_name="Standard Steel Corp",
            invoice_number="INV-STEEL-02",
            invoice_date=date(2026, 3, 1),
            due_date=date(2026, 3, 31),
            item_type='PAYABLE',
            outstanding_amount=Decimal('800000.00'),
            is_msme=False,
            is_overdue_43bh=False,
            overdue_days_msme=0
        )

        rep = ConsolidatedAuditReportBuilder.build_report(eng)
        sec_g = rep['section_g']

        assert Decimal(sec_g['tb_total_trade_payables']) == Decimal('2000000.00')
        assert Decimal(sec_g['subledger_total_trade_payables']) == Decimal('1200000.00')
        assert Decimal(sec_g['subledger_to_control_payables_variance']) == Decimal('800000.00')
        assert "REVIEW_REQUIRED" in sec_g['subledger_reconciliation_status']
        assert "SA 505" in sec_g['subledger_reconciliation_status']
        assert Decimal(sec_g['msme_overdue_section_43bh_total']) == Decimal('400000.00')

    def test_sa_240_compliance_and_missing_evidence_fail_closed(self, setup_diverse_companies):
        """
        Verify that missing compliance evidence displays REVIEW REQUIRED (Evidence Pending)
        and statistical anomaly tests do not claim fraud is absent (SA 240).
        """
        eng = setup_diverse_companies['eng_a']
        pdf_bytes = ReportExporterService.export_consolidated_pdf(eng)

        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))

        # Check Page 4 (CARO 2020) and Page 5 (Form 3CD)
        page_4_text = reader.pages[3].extract_text()
        page_5_text = reader.pages[4].extract_text()

        # Clause 3(i)(b) Physical Verification must NOT say COMPLIANT without evidence
        assert "REVIEW REQUIRED" in page_4_text
        assert "Evidence Pending" in page_4_text

        # Never claim "Nil Fraud Noted"
        assert "Nil Fraud Noted" not in page_4_text
        assert "Nil Fraud Noted" not in page_5_text
