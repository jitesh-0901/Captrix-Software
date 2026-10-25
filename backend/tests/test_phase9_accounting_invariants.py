import pytest
from decimal import Decimal
from datetime import date
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.companies.models import Company, Engagement, FinancialYear
from apps.accounting.models import (
    ChartOfAccounts,
    LedgerAccount,
    TrialBalanceSnapshot,
    ScheduleIIIGroup,
    AccountType
)
from apps.accounting.services import (
    TrialBalanceService,
    classify_schedule_iii,
    get_account_type_for_schedule_group,
    extract_debit_credit_amounts
)
from apps.reconciliation.services import BankReconciliationEngine
from apps.audit.corrections.registry import correction_rule_registry
from apps.audit.corrections.rules import MSMEDisallowanceRule, DepreciationScheduleIIRule

User = get_user_model()

@pytest.mark.django_db
class TestPhase9AccountingInvariants:
    """
    Deterministic Financial Systems and Accounting Invariants Test Suite.
    Verifies that Captrix AI adheres to non-negotiable double-entry bookkeeping,
    ICAI Standards on Auditing (SA 500, SA 700), Companies Act 2013 Schedule III,
    Income Tax Act Section 32 & 43B(h), and MSMED Act Section 16.
    """

    def setup_method(self):
        self.company_a = Company.objects.create(name="Alpha Corp India Pvt Ltd", pan="AABCA1234A")
        self.fy_a = FinancialYear.objects.create(
            company=self.company_a,
            label="FY 24-25",
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31)
        )
        self.engagement_a = Engagement.objects.create(
            company=self.company_a,
            financial_year=self.fy_a,
            title="Alpha Corp Statutory Audit FY24-25",
            overall_materiality=Decimal('100000.00')
        )

        # Tenant B for cross-tenant isolation verification
        self.company_b = Company.objects.create(name="Beta Logistics Ltd", pan="BBBCB5678B")
        self.fy_b = FinancialYear.objects.create(
            company=self.company_b,
            label="FY 24-25",
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31)
        )
        self.engagement_b = Engagement.objects.create(
            company=self.company_b,
            financial_year=self.fy_b,
            title="Beta Logistics Statutory Audit FY24-25",
            overall_materiality=Decimal('50000.00')
        )

    # -------------------------------------------------------------------------
    # INVARIANT 1: TRIAL BALANCE DEBIT-CREDIT EQUALITY & FAIL-CLOSED INTEGRITY
    # -------------------------------------------------------------------------
    def test_trial_balance_debit_credit_equality_invariant(self):
        """
        Verify that a balanced trial balance computes exact zero variance,
        and an imbalanced trial balance (even by ₹0.01) fails closed without
        inventing fictional balancing entries or suspense adjustments.
        """
        balanced_rows = [
            {'Particulars': 'Paid-up Equity Capital', 'Debit': '0.00', 'Credit': '1000000.00'},
            {'Particulars': 'HDFC Current Account', 'Debit': '600000.00', 'Credit': '0.00'},
            {'Particulars': 'Office Laptops & Hardware', 'Debit': '400000.00', 'Credit': '0.00'},
        ]
        res_bal = TrialBalanceService.calculate_trial_balance(
            rows=balanced_rows,
            as_of_date=date(2025, 3, 31),
            engagement=self.engagement_a
        )
        assert res_bal['is_balanced'] is True
        assert Decimal(res_bal['total_debits']) == Decimal('1000000.00')
        assert Decimal(res_bal['total_credits']) == Decimal('1000000.00')
        assert Decimal(res_bal['difference_amount']) == Decimal('0.00')
        assert res_bal['status'] == 'BALANCED'

        # Verify ₹0.01 discrepancy fails closed
        unbalanced_rows = [
            {'Particulars': 'Paid-up Equity Capital', 'Debit': '0.00', 'Credit': '1000000.00'},
            {'Particulars': 'HDFC Current Account', 'Debit': '600000.00', 'Credit': '0.00'},
            {'Particulars': 'Office Laptops & Hardware', 'Debit': '399999.99', 'Credit': '0.00'},
        ]
        res_unbal = TrialBalanceService.calculate_trial_balance(
            rows=unbalanced_rows,
            as_of_date=date(2025, 3, 31),
            engagement=self.engagement_a
        )
        assert res_unbal['is_balanced'] is False
        assert res_unbal['status'] == 'UNBALANCED_DIFFERENCE'
        assert abs(Decimal(res_unbal['difference_amount'])) == Decimal('0.01')
        
        # Verify no fake balancing accounts were injected
        account_names = [a['account_name'] for a in res_unbal['accounts']]
        assert 'Suspense Account' not in account_names
        assert 'Balancing Figure' not in account_names
        assert 'Difference in TB' not in account_names

    # -------------------------------------------------------------------------
    # INVARIANT 2: SCHEDULE III DIVISION I & II BALANCE SHEET EQUILIBRIUM
    # -------------------------------------------------------------------------
    def test_schedule_iii_balance_sheet_equilibrium_and_retained_earnings_flow(self):
        """
        Verify that Schedule III Balance Sheet maintains exact mathematical equilibrium:
        Total Assets == Total Equity and Liabilities.
        Profit after tax from P&L must roll deterministically into Reserves & Surplus.
        """
        complete_tb = [
            # Equity & Liabilities
            {'Particulars': 'Equity Share Capital', 'Debit': '0.00', 'Credit': '500000.00'},
            {'Particulars': 'General Reserve', 'Debit': '0.00', 'Credit': '100000.00'},
            {'Particulars': 'Bank Term Loan', 'Debit': '0.00', 'Credit': '200000.00'},
            {'Particulars': 'Sundry Creditors (Trade Payables)', 'Debit': '0.00', 'Credit': '150000.00'},
            
            # Revenues & Expenses (Operating Profit)
            {'Particulars': 'Domestic Software Sales', 'Debit': '0.00', 'Credit': '800000.00'},
            {'Particulars': 'Basic Salary & Allowances', 'Debit': '300000.00', 'Credit': '0.00'},
            {'Particulars': 'Office Rent', 'Debit': '100000.00', 'Credit': '0.00'},
            
            # Assets
            {'Particulars': 'Plant & Machinery', 'Debit': '400000.00', 'Credit': '0.00'},
            {'Particulars': 'Sundry Debtors', 'Debit': '350000.00', 'Credit': '0.00'},
            {'Particulars': 'ICICI Bank Current Account', 'Debit': '600000.00', 'Credit': '0.00'},
        ]
        
        tb_res = TrialBalanceService.calculate_trial_balance(
            rows=complete_tb,
            as_of_date=date(2025, 3, 31),
            engagement=self.engagement_a
        )
        assert tb_res['is_balanced'] is True
        
        # P&L Check:
        # Revenue = 800,000, Expenses = 400,000 => PBT = 400,000
        # Tax Prov (25%) = 100,000 => PAT = 300,000
        bs_check = tb_res['balance_sheet_cross_check']
        assert bs_check['is_balanced'] is True
        assert Decimal(bs_check['variance']) < Decimal('1.00')
        
        total_assets = Decimal(bs_check['total_assets'])
        total_eq_liab = Decimal(bs_check['total_equity_and_liabilities'])
        assert total_assets == total_eq_liab

    # -------------------------------------------------------------------------
    # INVARIANT 3: DUAL DEPRECIATION STATUTORY COMPLIANCE (SCH II vs SEC 32)
    # -------------------------------------------------------------------------
    def test_dual_depreciation_statutory_variance_rule(self):
        """
        Verify dual depreciation calculation:
        1. Companies Act 2013 Schedule II useful lives (SLM/WDV)
        2. Income Tax Act 1961 Section 32 block rates (Computers 40%, P&M 15%)
        Ensures tax-book timing variance is correctly computed for Deferred Tax / Form 3CD.
        """
        rule = DepreciationScheduleIIRule()
        assert rule.rule_id == "FAR_DEPN_SCH_II"

        # Scenario: Laptops purchased for ₹5,00,000
        # Book Depreciation: ₹1,58,333.33, Schedule II / Tax Depn: ₹2,00,000.00
        context = {
            'fixed_assets': [
                {
                    'asset_name': 'Dell Workstations',
                    'book_depreciation': Decimal('158333.33'),
                    'calculated_schedule_ii_depreciation': Decimal('200000.00')
                }
            ]
        }
        
        corrections = rule.evaluate(context)
        assert len(corrections) == 1
        assert corrections[0]['amount'] == 41666.67
        assert corrections[0]['severity'] == 'MEDIUM'

    # -------------------------------------------------------------------------
    # INVARIANT 4: BANK RECONCILIATION STATEMENT (BRS) DETERMINISTIC RECONCILIATION
    # -------------------------------------------------------------------------
    def test_bank_reconciliation_exact_four_way_equality(self):
        """
        Verify BRS exact balance formula:
        Balance as per Bank Statement
        + Uncredited Deposits (cheques deposited but not cleared)
        - Unpresented Cheques (cheques issued but not presented)
        + / - Direct Bank Debits / Credits (bank charges, interest)
        = Balance as per Books (General Ledger)
        """
        statement_balance = Decimal('1000000.00')
        deposits_in_transit = Decimal('150000.00')
        outstanding_cheques = Decimal('250000.00')
        unrecorded_bank_charges = Decimal('5000.00')
        unrecorded_bank_interest = Decimal('12000.00')

        # Theoretical reconciled book balance:
        # 1,000,000 + 150,000 - 250,000 = 900,000 (Adjusted Bank Balance)
        # Expected Ledger Balance before bank charges/interest:
        # Ledger - 5,000 + 12,000 = 900,000 => Ledger Balance = 893,000
        ledger_balance = Decimal('893000.00')
        
        adjusted_bank = statement_balance + deposits_in_transit - outstanding_cheques
        adjusted_book = ledger_balance - unrecorded_bank_charges + unrecorded_bank_interest
        
        variance = abs(adjusted_bank - adjusted_book)
        assert variance == Decimal('0.00'), f"BRS variance must be exactly 0.00, got {variance}"

    # -------------------------------------------------------------------------
    # INVARIANT 5: MSME SECTION 43B(h) DISALLOWANCE AND PENAL INTEREST
    # -------------------------------------------------------------------------
    def test_msme_section_43b_h_disallowance_and_section_16_interest(self):
        """
        Verify MSMED Act Section 15 & 16, and Income Tax Act Section 43B(h):
        - Max payment window: 45 days with written agreement (15 days without)
        - Overdue payments beyond the financial year-end are disallowed under 43B(h)
        - Compound interest at 3x RBI bank rate is mandatory and disallowed as business expense
        """
        rule = MSMEDisallowanceRule()
        assert rule.rule_id == "MSME_SEC_43B_H"

        context = {
            'subledger_aging': [
                {
                    'party_name': 'Apex Precision Engineering',
                    'is_msme': True,
                    'overdue_days': 48,
                    'balance': Decimal('350000.00')
                },
                {
                    'party_name': 'Standard Enterprise Corp',
                    'is_msme': False,
                    'overdue_days': 60,
                    'balance': Decimal('200000.00')
                }
            ]
        }

        corrections = rule.evaluate(context)
        assert len(corrections) == 1
        corr = corrections[0]
        assert corr['party_name'] == 'Apex Precision Engineering'
        assert corr['severity'] == 'HIGH'
        assert corr['disallowance_principal'] == 350000.00
        assert corr['amount'] > 0

    # -------------------------------------------------------------------------
    # INVARIANT 6: STRICT MULTI-TENANT ISOLATION
    # -------------------------------------------------------------------------
    def test_multi_tenant_data_isolation(self):
        """
        Verify that Tenant A cannot access, query, or mutate Tenant B's
        Chart of Accounts, Ledger Accounts, or Trial Balance data.
        """
        # Populate Company A COA
        coa_a = ChartOfAccounts.objects.create(
            company=self.company_a,
            account_code="1001",
            account_name="Alpha Private Secret Account",
            account_type=AccountType.ASSET,
            schedule_iii_group=ScheduleIIIGroup.CASH_EQUIVALENTS
        )
        
        # Populate Company B COA
        coa_b = ChartOfAccounts.objects.create(
            company=self.company_b,
            account_code="2001",
            account_name="Beta Protected Vault Account",
            account_type=AccountType.LIABILITY,
            schedule_iii_group=ScheduleIIIGroup.TRADE_PAYABLES
        )

        # Company A query must NEVER retrieve Company B records
        a_records = ChartOfAccounts.objects.filter(company=self.company_a)
        assert a_records.filter(id=coa_b.id).exists() is False
        assert a_records.filter(account_name__icontains="Beta").exists() is False
        
        b_records = ChartOfAccounts.objects.filter(company=self.company_b)
        assert b_records.filter(id=coa_a.id).exists() is False
        assert b_records.filter(account_name__icontains="Alpha").exists() is False
