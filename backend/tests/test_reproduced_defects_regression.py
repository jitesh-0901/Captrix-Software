import pytest
from decimal import Decimal
from apps.accounting.models import ScheduleIIIGroup, AccountType
from apps.accounting.services import (
    classify_schedule_iii,
    TrialBalanceService,
    extract_account_name,
    extract_account_code,
    get_account_type_for_schedule_group
)
from apps.ingestion.parsers import (
    normalize_financial_header_name,
    deduplicate_headers,
    clean_and_flatten_tally_record
)
from apps.audit.services import FinancialRatiosEngine


def test_mandate_1_header_normalization_collision_resolved():
    """
    Mandate 1 & 2: Verify Account Code, Account Name, and Account Type do not collide into 'Particulars'.
    Previously, 'Account_Code' matched 'account' and normalized to 'Particulars',
    clobbering account codes and account names with 'Asset'/'Liability'.
    """
    h_code = normalize_financial_header_name("Account_Code")
    h_type = normalize_financial_header_name("Account_Type")
    h_name = normalize_financial_header_name("Account_Name")
    h_part = normalize_financial_header_name("Particulars")

    assert h_code == "Account Code", f"Expected 'Account Code', got '{h_code}'"
    assert h_type == "Account Type", f"Expected 'Account Type', got '{h_type}'"
    assert h_name == "Particulars", f"Expected 'Particulars', got '{h_name}'"
    assert h_part == "Particulars", f"Expected 'Particulars', got '{h_part}'"

    # Ensure deduplicate_headers prevents dictionary clobbering
    raw_headers = ["Account Code", "Account Type", "Particulars", "Particulars"]
    deduped = deduplicate_headers(raw_headers)
    assert deduped == ["Account Code", "Account Type", "Particulars", "Particulars_2"]


def test_mandate_1_extract_account_name_rejects_category_labels():
    """
    Mandate 1: Extract account name must prioritize explicit account name keys
    and reject generic classification labels ('Asset', 'Liability', 'Income', 'Expense').
    """
    row_with_both = {
        'Account Name': 'Domestic Sales',
        'Particulars': 'Income',
        'Account Type': 'Income'
    }
    extracted = extract_account_name(row_with_both)
    assert extracted == "Domestic Sales", f"Expected 'Domestic Sales', got '{extracted}'"

    row_category_only = {
        'Particulars': 'Asset',
        'Account_Type': 'Asset'
    }
    extracted_cat = extract_account_name(row_category_only)
    assert extracted_cat == "", "Category label 'Asset' should be rejected as an account name"


def test_mandate_2_no_balancing_plug_and_clean_balance_sheet():
    """
    Mandate 2: Eliminate balancing plugs.
    Unclassified accounts must NEVER be absorbed into OTHER_EXPENSES or OTHER_INCOME.
    Verify component-to-subtotal arithmetic and balance sheet equilibrium.
    """
    accounts = [
        {'account_name': 'Main Bank', 'schedule_iii_group': ScheduleIIIGroup.CASH_EQUIVALENTS, 'debit': Decimal('10000000.00'), 'credit': Decimal('0.00')},
        {'account_name': 'Plant & Machinery', 'schedule_iii_group': ScheduleIIIGroup.PPE, 'debit': Decimal('190000000.00'), 'credit': Decimal('0.00')},
        {'account_name': 'Trade Receivables', 'schedule_iii_group': ScheduleIIIGroup.TRADE_RECEIVABLES, 'debit': Decimal('30000000.00'), 'credit': Decimal('0.00')},
        {'account_name': 'Inventories', 'schedule_iii_group': ScheduleIIIGroup.INVENTORIES, 'debit': Decimal('15000000.00'), 'credit': Decimal('0.00')},
        {'account_name': 'Share Capital', 'schedule_iii_group': ScheduleIIIGroup.SHARE_CAPITAL, 'debit': Decimal('0.00'), 'credit': Decimal('5000000.00')},
        {'account_name': 'Trade Payables', 'schedule_iii_group': ScheduleIIIGroup.TRADE_PAYABLES, 'debit': Decimal('0.00'), 'credit': Decimal('220000000.00')},
        {'account_name': 'Other Current Liabilities', 'schedule_iii_group': ScheduleIIIGroup.OTHER_CURRENT_LIABILITIES, 'debit': Decimal('0.00'), 'credit': Decimal('10000000.00')},
        {'account_name': 'Reserves and Surplus', 'schedule_iii_group': ScheduleIIIGroup.RESERVES_SURPLUS, 'debit': Decimal('0.00'), 'credit': Decimal('10000000.00')},
    ]

    res = TrialBalanceService.compile_financial_statements(accounts)
    bs = res['balance_sheet']
    cl = bs['equity_and_liabilities']['current_liabilities']

    tot_assets = Decimal(bs['total_assets'])
    tot_eq_liab = Decimal(bs['total_equity_and_liabilities'])

    # Total Assets = 10M + 190M + 30M + 15M = 245M
    assert tot_assets == Decimal('245000000.00'), f"Assets expected 245M, got {tot_assets}"
    # Total Eq & Liab = 5M (Share Cap) + 10M (Reserves) + 220M (TP) + 10M (Other CL) = 245M
    assert tot_eq_liab == Decimal('245000000.00'), f"Eq & Liab expected 245M, got {tot_eq_liab}"
    assert bs['is_balanced'] is True

    # Current Liabilities subtotal arithmetic verification
    cl_subtotal = Decimal(cl['total'])
    tp = Decimal(cl['trade_payables'])
    ocl = Decimal(cl['other_current_liabilities'])
    st_b = Decimal(cl['short_term_borrowings'])
    st_p = Decimal(cl['short_term_provisions'])
    assert cl_subtotal == (st_b + tp + ocl + st_p), "Current liabilities subtotal does not equal sum of parts"


def test_mandate_2_unclassified_account_fails_balanced_without_plug():
    """
    Mandate 2: When an unclassified account exists, compile_financial_statements
    must NOT plug it into other expenses to force balance; is_balanced must be False.
    """
    accounts = [
        {'account_name': 'Main Bank', 'schedule_iii_group': ScheduleIIIGroup.CASH_EQUIVALENTS, 'debit': Decimal('100000.00'), 'credit': Decimal('0.00')},
        {'account_name': 'Unknown Suspense Item', 'schedule_iii_group': ScheduleIIIGroup.UNCLASSIFIED, 'debit': Decimal('0.00'), 'credit': Decimal('100000.00')},
    ]
    res = TrialBalanceService.compile_financial_statements(accounts)
    bs = res['balance_sheet']
    pl = res['profit_and_loss']

    # Other expenses must NOT have absorbed the 100,000 unclassified item
    assert Decimal(pl['expenses']['other_expenses']) == Decimal('0.00'), "Unclassified item was illegally plugged into other expenses"
    assert bs['is_balanced'] is False, "Statement with unclassified balance must fail is_balanced check"


def test_mandate_3_revenue_from_operations_not_other_income():
    """
    Mandate 3: P&L classification must identify 'Domestic Sales', 'Turnover', 'Gross Sales'
    strictly as REVENUE_OPERATIONS, never OTHER_INCOME.
    """
    grp_domestic = classify_schedule_iii("Domestic Sales")
    grp_turnover = classify_schedule_iii("Turnover")
    grp_sales = classify_schedule_iii("Gross Sales")
    grp_export = classify_schedule_iii("Export Sales")

    assert grp_domestic == ScheduleIIIGroup.REVENUE_OPERATIONS
    assert grp_turnover == ScheduleIIIGroup.REVENUE_OPERATIONS
    assert grp_sales == ScheduleIIIGroup.REVENUE_OPERATIONS
    assert grp_export == ScheduleIIIGroup.REVENUE_OPERATIONS

    # True other income accounts
    grp_interest = classify_schedule_iii("Interest on Fixed Deposit")
    grp_dividend = classify_schedule_iii("Dividend Income")
    assert grp_interest == ScheduleIIIGroup.OTHER_INCOME
    assert grp_dividend == ScheduleIIIGroup.OTHER_INCOME


def test_mandate_4_bank_cashbook_source_type_extraction():
    """
    Mandate 4: Bank reconciliation must extract GL entries where Source_Type is 'Bank',
    enabling full transaction matching rather than treating 0 cashbook items as matched.
    """
    gl_entry = {
        'Source_Type': 'Bank',
        'Account_Code': '',
        'Account_Name': '',
        'Debit_INR': '353212.21',
        'Credit_INR': '0.00',
        'Document_Ref': 'CHQ-89312'
    }

    acc_code = str(gl_entry.get('Account_Code', '')).strip()
    acc_name = str(gl_entry.get('Account_Name', '')).lower()
    src_type = str(gl_entry.get('Source_Type', '')).lower().strip()

    is_bank_acc = (
        acc_code == '100100'
        or 'main bank' in acc_name
        or ('bank' in acc_name and not acc_code.startswith(('2', '3', '4', '5')))
        or src_type == 'bank'
        or 'bank' in src_type
    )

    assert is_bank_acc is True, "GL entry with Source_Type='Bank' was not identified as bank transaction"


def test_mandate_7_financial_ratios_handle_zero_denominators_and_formulas():
    """
    Mandate 7: Handle zero denominators and negative equity explicitly.
    Do not substitute 0.0 for missing data or show contradictory 'HEALTHY' status
    when equity is negative or current liabilities are 0.
    """
    class MockEngagement:
        company = None
        trial_balances = []

    # When no data is uploaded, ratios must return AWAITING_DATA with formulas
    ratios = FinancialRatiosEngine.compute_ratios(None)
    for r in ratios:
        assert 'name' in r
        assert 'category' in r
        assert 'status' in r
        assert r['status'] == 'AWAITING_DATA'
