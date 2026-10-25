import pytest
from decimal import Decimal
from datetime import date
from apps.accounting.services import TrialBalanceService, GeneralLedgerScrutinyService
from apps.accounting.models import Transaction, LedgerAccount, ChartOfAccounts, AccountType, ScheduleIIIGroup
from apps.companies.models import Company, FinancialYear, Engagement

@pytest.mark.django_db
def test_trial_balance_balanced():
    """Verify trial balance calculation when Debits equal Credits"""
    rows = [
        {'Particulars': 'Cash in Hand', 'Debit': '50000.00', 'Credit': '0.00'},
        {'Particulars': 'Capital Account', 'Debit': '0.00', 'Credit': '50000.00'},
    ]
    result = TrialBalanceService.calculate_trial_balance(rows)
    assert result['is_balanced'] is True
    assert result['status'] == 'BALANCED'
    assert Decimal(result['total_debits']) == Decimal('50000.00')
    assert Decimal(result['total_credits']) == Decimal('50000.00')
    assert Decimal(result['difference_amount']) == Decimal('0.00')

@pytest.mark.django_db
def test_trial_balance_unbalanced_fails_closed():
    """Verify trial balance fails closed with exact difference when Debits != Credits"""
    rows = [
        {'Particulars': 'Cash in Hand', 'Debit': '50000.00', 'Credit': '0.00'},
        {'Particulars': 'Capital Account', 'Debit': '0.00', 'Credit': '48000.00'},
    ]
    result = TrialBalanceService.calculate_trial_balance(rows)
    assert result['is_balanced'] is False
    assert result['status'] == 'UNBALANCED_DIFFERENCE'
    assert Decimal(result['difference_amount']) == Decimal('2000.00')

@pytest.mark.django_db
def test_general_ledger_scrutiny():
    """Verify GL scrutiny detects Section 40A(3), round amounts, and weekend postings"""
    company = Company.objects.create(name="Test Corp", pan="AABCT1234F")
    fy = FinancialYear.objects.create(company=company, label="FY 24-25", start_date=date(2024, 4, 1), end_date=date(2025, 3, 31))
    eng = Engagement.objects.create(company=company, financial_year=fy, title="Test Audit")
    
    coa = ChartOfAccounts.objects.create(company=company, account_code="4001", account_name="Cash Expenses", account_type=AccountType.EXPENSE)
    ledger = LedgerAccount.objects.create(company=company, name="Office Cash Expenses", coa=coa)

    # Cash transaction > 10,000 (Section 40A(3) violation)
    t1 = Transaction.objects.create(
        engagement=eng,
        ledger_account=ledger,
        voucher_number="PV-01",
        date=date(2024, 5, 10), # Friday
        counterparty="Cash Supplier",
        narration="Payment in cash for urgent repairs",
        debit_amount=Decimal('25000.00'),
        credit_amount=Decimal('0.00')
    )

    # Round amount voucher (multiple of 10,000)
    t2 = Transaction.objects.create(
        engagement=eng,
        ledger_account=ledger,
        voucher_number="PV-02",
        date=date(2024, 5, 12), # Sunday (Weekend!)
        counterparty="Consultant",
        narration="Advisory fee round 1",
        debit_amount=Decimal('50000.00'),
        credit_amount=Decimal('0.00')
    )

    results = GeneralLedgerScrutinyService.scrutinize_transactions([t1, t2])
    assert results['total_scrutinized'] == 2
    assert results['flagged_count'] == 2

    # Verify t1 was flagged for Section 40A(3)
    t1.refresh_from_db()
    assert t1.is_unusual is True
    assert "SECTION_40A3_CASH_LIMIT_EXCEEDED" in t1.risk_flags

    # Verify t2 was flagged for weekend posting and round amount
    t2.refresh_from_db()
    assert t2.is_unusual is True
    assert "WEEKEND_POSTING" in t2.risk_flags
    assert "ROUND_AMOUNT" in t2.risk_flags
