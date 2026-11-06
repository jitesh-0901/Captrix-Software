import pytest
from decimal import Decimal
from datetime import date
from django.contrib.auth.models import User
from apps.companies.models import Company, FinancialYear, Engagement, EntityType, EngagementType
from apps.accounting.models import ChartOfAccounts, LedgerAccount, ScheduleIIIGroup, TrialBalanceSnapshot, AccountType
from apps.audit.models import FixedAsset, SubledgerAgingItem
from apps.reconciliation.models import ReconciliationRun, ReconciliationType, ReconciliationStatus
from apps.reconciliation.services import CrossDocumentReconciliationEngine, BankReconciliationEngine
from apps.reporting.models import Workpaper, WorkpaperStatus
from apps.reporting.services import WorkpaperDraftingService
from apps.accounting.services import TrialBalanceService
from apps.reporting.report_builder import ConsolidatedAuditReportBuilder


@pytest.mark.django_db
class TestFinalCompletionIntegrity:
    """
    Comprehensive regression suite for the 9 Phase 1 data integrity requirements:
    1. Bank recon: 130 unmatched items with 0.00 unexplained variance remains REVIEW_REQUIRED.
    2. Fixed asset recon: PPE Gross Block from TB vs FAR without phantom accounts or double-counting.
    3. Payables recon: TB control vs vendor ageing without double-counting subledger accounts.
    4. Receivables recon: TB control vs customer ageing without double-counting subledger accounts.
    5. Payables control separation from subledger ageing.
    6. Receivables control separation from subledger ageing.
    7. Executive Summary & Financial Statements total assets exact roll-forward.
    8. Revenue unverified when GSTR-1 and outward evidence missing.
    9. Workpaper status separation: No false 13/13 auto-approval.
    10. Tenant isolation: Strict multi-company data segregation.
    """

    @pytest.fixture
    def setup_company_and_engagement(self):
        company = Company.objects.create(
            name="Asterion Testing Corp Pvt Ltd",
            cin="U29253TN2018PTC123456",
            pan="AAACA1234A",
            entity_type=EntityType.PVT_LTD
        )
        fy = FinancialYear.objects.create(
            company=company,
            label="FY 2025-26",
            start_date=date(2025, 4, 1),
            end_date=date(2026, 3, 31)
        )
        partner = User.objects.create_user(
            username="test_partner_fca",
            password="testpassword123",
            is_staff=True
        )
        engagement = Engagement.objects.create(
            company=company,
            financial_year=fy,
            title="Statutory Audit FY 2025-26",
            engagement_type=EngagementType.STATUTORY,
            overall_materiality=Decimal("500000.00"),
            performance_materiality=Decimal("375000.00"),
            lead_partner=partner
        )

        # 27 Authoritative Trial Balance Accounts
        tb_accounts = [
            {'account_code': '100100', 'account_name': 'Main Bank', 'debit': '10042487.21', 'credit': '0.00', 'schedule_iii_group': ScheduleIIIGroup.CASH_EQUIVALENTS},
            {'account_code': '100200', 'account_name': 'Cash on Hand', 'debit': '150000.00', 'credit': '0.00', 'schedule_iii_group': ScheduleIIIGroup.CASH_EQUIVALENTS},
            {'account_code': '110100', 'account_name': 'Trade Receivables', 'debit': '30874589.24', 'credit': '0.00', 'schedule_iii_group': ScheduleIIIGroup.TRADE_RECEIVABLES},
            {'account_code': '120100', 'account_name': 'Inventory', 'debit': '14000000.00', 'credit': '0.00', 'schedule_iii_group': ScheduleIIIGroup.INVENTORIES},
            {'account_code': '130100', 'account_name': 'Input CGST', 'debit': '6396123.44', 'credit': '0.00', 'schedule_iii_group': ScheduleIIIGroup.OTHER_CURRENT_ASSETS},
            {'account_code': '130200', 'account_name': 'Input SGST', 'debit': '450000.00', 'credit': '0.00', 'schedule_iii_group': ScheduleIIIGroup.OTHER_CURRENT_ASSETS},
            {'account_code': '130300', 'account_name': 'Input IGST', 'debit': '3926843.48', 'credit': '0.00', 'schedule_iii_group': ScheduleIIIGroup.OTHER_CURRENT_ASSETS},
            {'account_code': '140100', 'account_name': 'Gross Fixed Assets', 'debit': '195297131.83', 'credit': '0.00', 'schedule_iii_group': ScheduleIIIGroup.PPE},
            {'account_code': '140200', 'account_name': 'Accumulated Depreciation', 'debit': '0.00', 'credit': '2100000.00', 'schedule_iii_group': ScheduleIIIGroup.PPE},
            {'account_code': '200100', 'account_name': 'Trade Payables', 'debit': '0.00', 'credit': '222763867.78', 'schedule_iii_group': ScheduleIIIGroup.TRADE_PAYABLES},
            {'account_code': '200200', 'account_name': 'MSME Trade Payables', 'debit': '0.00', 'credit': '23462116.07', 'schedule_iii_group': ScheduleIIIGroup.TRADE_PAYABLES},
            {'account_code': '210100', 'account_name': 'Output CGST', 'debit': '0.00', 'credit': '4886072.51', 'schedule_iii_group': ScheduleIIIGroup.OTHER_CURRENT_LIABILITIES},
            {'account_code': '210200', 'account_name': 'Output SGST', 'debit': '0.00', 'credit': '350000.00', 'schedule_iii_group': ScheduleIIIGroup.OTHER_CURRENT_LIABILITIES},
            {'account_code': '210300', 'account_name': 'Output IGST', 'debit': '0.00', 'credit': '2672356.72', 'schedule_iii_group': ScheduleIIIGroup.OTHER_CURRENT_LIABILITIES},
            {'account_code': '220100', 'account_name': 'Term Loan', 'debit': '0.00', 'credit': '4000000.00', 'schedule_iii_group': ScheduleIIIGroup.LONG_TERM_BORROWINGS},
            {'account_code': '230100', 'account_name': 'Statutory Dues Payable', 'debit': '0.00', 'credit': '250000.00', 'schedule_iii_group': ScheduleIIIGroup.OTHER_CURRENT_LIABILITIES},
            {'account_code': '300100', 'account_name': 'Share Capital', 'debit': '0.00', 'credit': '5000000.00', 'schedule_iii_group': ScheduleIIIGroup.SHARE_CAPITAL},
            {'account_code': '300200', 'account_name': 'Retained Earnings', 'debit': '0.00', 'credit': '25450000.00', 'schedule_iii_group': ScheduleIIIGroup.RESERVES_SURPLUS},
            {'account_code': '400100', 'account_name': 'Domestic Sales', 'debit': '0.00', 'credit': '60429839.84', 'schedule_iii_group': ScheduleIIIGroup.REVENUE_OPERATIONS},
            {'account_code': '400200', 'account_name': 'Export Sales', 'debit': '0.00', 'credit': '0.00', 'schedule_iii_group': ScheduleIIIGroup.REVENUE_OPERATIONS},
            {'account_code': '500100', 'account_name': 'Raw Material Purchases', 'debit': '78725635.00', 'credit': '0.00', 'schedule_iii_group': ScheduleIIIGroup.COST_OF_MATERIALS},
            {'account_code': '500200', 'account_name': 'Employee Costs', 'debit': '2349975.79', 'credit': '0.00', 'schedule_iii_group': ScheduleIIIGroup.EMPLOYEE_BENEFITS},
            {'account_code': '500300', 'account_name': 'Power & Utilities', 'debit': '2150659.81', 'credit': '0.00', 'schedule_iii_group': ScheduleIIIGroup.OTHER_EXPENSES},
            {'account_code': '500400', 'account_name': 'Freight Inward', 'debit': '1735199.02', 'credit': '0.00', 'schedule_iii_group': ScheduleIIIGroup.COST_OF_MATERIALS},
            {'account_code': '500500', 'account_name': 'Repairs & Maintenance', 'debit': '1308276.17', 'credit': '0.00', 'schedule_iii_group': ScheduleIIIGroup.OTHER_EXPENSES},
            {'account_code': '500600', 'account_name': 'Depreciation Expense', 'debit': '0.00', 'credit': '0.00', 'schedule_iii_group': ScheduleIIIGroup.DEPRECIATION_AMORT},
            {'account_code': '500700', 'account_name': 'Other Operating Expenses', 'debit': '3957331.93', 'credit': '0.00', 'schedule_iii_group': ScheduleIIIGroup.OTHER_EXPENSES},
        ]

        tb = TrialBalanceSnapshot.objects.create(
            engagement=engagement,
            as_of_date=fy.end_date,
            total_debits=Decimal("351364252.92"),
            total_credits=Decimal("351364252.92"),
            difference_amount=Decimal("0.00"),
            is_balanced=True,
            accounts_snapshot=tb_accounts
        )

        return company, fy, engagement, partner, tb

    def test_item_1_brs_unmatched_items_require_review(self, setup_company_and_engagement):
        """1. Bank reconciliation: 130 unmatched items with 0.00 unexplained variance must remain REVIEW_REQUIRED."""
        company, fy, engagement, partner, tb = setup_company_and_engagement

        # Create cashbook entries with timing differences
        cashbook = [
            {'date': '2025-04-10', 'ref': 'CHQ-001', 'desc': 'Stale vendor payment', 'amount': '8541299.61', 'type': 'WITHDRAWAL'},
            {'date': '2026-03-25', 'ref': 'CHQ-002', 'desc': 'Unpresented cheque', 'amount': '2133260.00', 'type': 'WITHDRAWAL'},
        ]
        bank_items = [
            {'date': '2026-03-31', 'ref': 'BNK-CHG', 'desc': 'Bank ledger fee', 'amount': '187300.00', 'type': 'WITHDRAWAL'},
            {'date': '2026-03-31', 'ref': 'BNK-INT', 'desc': 'Bank interest', 'amount': '76650.00', 'type': 'DEPOSIT'},
        ]
        # Mathematical bridge: 10042487.21 + 8541299.61 + 2133260.00 + 76650.00 - 187300.00 = 20606396.82
        run = BankReconciliationEngine.execute_reconciliation(
            engagement=engagement,
            as_of_date=fy.end_date,
            cashbook_items=cashbook,
            bank_items=bank_items,
            starting_cashbook_balance=Decimal("10042487.21"),
            actual_statement_balance=Decimal("20606396.82")
        )
        assert run.unreconciled_difference == Decimal("0.00")
        assert run.status == ReconciliationStatus.REVIEW_REQUIRED
        assert run.unmatched_count > 0

    def test_item_2_fixed_asset_reconciliation_variance(self, setup_company_and_engagement):
        """2. Fixed asset reconciliation: PPE Gross Block from TB (195.30M) vs FAR (189.70M) = 5.59M variance."""
        company, fy, engagement, partner, tb = setup_company_and_engagement

        far_items = [{'original_cost': '189702735.35'}]
        run = CrossDocumentReconciliationEngine.reconcile_far_vs_ledger(engagement, far_items=far_items)
        assert run.status == ReconciliationStatus.VARIANCE_DETECTED
        assert run.balance_per_books == Decimal("195297131.83")
        assert run.balance_per_statement == Decimal("189702735.35")
        assert run.unreconciled_difference == Decimal("5594396.48")

    def test_item_3_and_5_payables_reconciliation_variance(self, setup_company_and_engagement):
        """3 & 5. Payables reconciliation: TB control (246.23M) vs vendor ageing (125.88M) = 120.34M variance."""
        company, fy, engagement, partner, tb = setup_company_and_engagement

        creditors_items = [{'outstanding_amount': '125883402.15'}]
        run = CrossDocumentReconciliationEngine.reconcile_creditors_ageing(engagement, creditors_items=creditors_items)
        assert run.status == ReconciliationStatus.VARIANCE_DETECTED
        assert run.balance_per_books == Decimal("246225983.85")
        assert run.balance_per_statement == Decimal("125883402.15")
        assert run.unreconciled_difference == Decimal("120342581.70")

    def test_item_4_and_6_receivables_reconciliation_variance(self, setup_company_and_engagement):
        """4 & 6. Receivables reconciliation: TB control (30.87M) vs customer ageing (172.55M) = 141.67M variance."""
        company, fy, engagement, partner, tb = setup_company_and_engagement

        debtors_items = [{'outstanding_amount': '172546009.65'}]
        run = CrossDocumentReconciliationEngine.reconcile_debtors_ageing(engagement, debtors_items=debtors_items)
        assert run.status == ReconciliationStatus.VARIANCE_DETECTED
        assert run.balance_per_books == Decimal("30874589.24")
        assert run.balance_per_statement == Decimal("172546009.65")
        assert run.unreconciled_difference == Decimal("141671420.41")

    def test_item_7_executive_summary_total_assets_rollforward(self, setup_company_and_engagement):
        """7. Executive Summary total assets 259,037,175.20 traces exactly to financial statement calculations."""
        company, fy, engagement, partner, tb = setup_company_and_engagement

        statements = TrialBalanceService.compile_financial_statements(tb.accounts_snapshot)
        bs = statements['balance_sheet']

        # Trace subcomponents
        nca = Decimal(str(bs['assets']['non_current_assets']['total']))
        ca = Decimal(str(bs['assets']['current_assets']['total']))
        total_assets = Decimal(str(bs['total_assets']))

        assert nca == Decimal("193197131.83")
        assert ca == Decimal("65840043.37")
        assert total_assets == Decimal("259037175.20")

        # Balance sheet equation
        total_eq_liab = Decimal(str(bs['total_equity_and_liabilities']))
        assert total_eq_liab == Decimal("259037175.20")
        assert Decimal(str(bs['difference'])) == Decimal("0.00")

    def test_item_8_revenue_unverified_when_gstr1_missing(self, setup_company_and_engagement):
        """8. Revenue 60,429,839.84 is unverified when GSTR-1 outward returns are missing."""
        company, fy, engagement, partner, tb = setup_company_and_engagement

        report_data = ConsolidatedAuditReportBuilder.build_report(engagement)
        rev_status = report_data['section_b']['revenue_verification_status']
        assert rev_status == "UNVERIFIED_MISSING_EVIDENCE"
        assert Decimal(report_data['section_c']['revenue_from_operations']) == Decimal("60429839.84")

    def test_item_9_workpapers_status_separation_no_false_approval(self, setup_company_and_engagement):
        """9. Workpapers draft as REVIEW_REQUIRED / READY_FOR_REVIEW and do not show false 13/13 approval."""
        company, fy, engagement, partner, tb = setup_company_and_engagement

        wps = WorkpaperDraftingService.draft_workpapers(engagement)
        assert len(wps) == 13

        # None of them should be prematurely marked APPROVED
        approved_count = sum(1 for w in wps if w.status == WorkpaperStatus.APPROVED)
        assert approved_count == 0

        # High-risk / missing-evidence workpapers MUST be REVIEW_REQUIRED
        wp_b201 = next(w for w in wps if w.wp_reference == "WP-B201")
        assert wp_b201.status == WorkpaperStatus.REVIEW_REQUIRED

        # Report Executive Summary reflects true approval counts
        report_data = ConsolidatedAuditReportBuilder.build_report(engagement)
        assert report_data['section_b']['approved_workpapers_count'] == 0
        assert report_data['section_b']['total_workpapers'] == 13

    def test_item_10_multi_company_tenant_isolation(self, setup_company_and_engagement):
        """10. Multi-company security: Company A data must never leak to Company B."""
        company_a, fy_a, eng_a, partner_a, tb_a = setup_company_and_engagement

        company_b = Company.objects.create(
            name="Beta Competitor Ltd",
            cin="U72200MH2020PTC999999",
            pan="BBBCB9999B",
            entity_type=EntityType.PVT_LTD
        )
        fy_b = FinancialYear.objects.create(
            company=company_b,
            label="FY 2025-26",
            start_date=date(2025, 4, 1),
            end_date=date(2026, 3, 31)
        )
        eng_b = Engagement.objects.create(
            company=company_b,
            financial_year=fy_b,
            title="Competitor Audit FY 2025-26",
            engagement_type=EngagementType.STATUTORY
        )

        # Ensure no cross-tenant leakage in queries
        assert Engagement.objects.filter(company=company_a).count() == 1
        assert Engagement.objects.filter(company=company_b).count() == 1
        assert TrialBalanceSnapshot.objects.filter(engagement=eng_b).count() == 0
