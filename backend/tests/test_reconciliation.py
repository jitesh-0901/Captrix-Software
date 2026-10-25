import pytest
from decimal import Decimal
from datetime import date
from apps.companies.models import Company, FinancialYear, Engagement
from apps.reconciliation.services import BankReconciliationEngine, GstItcReconciliationEngine
from apps.reconciliation.models import ReconciliationStatus

@pytest.mark.django_db
def test_bank_reconciliation_statement():
    """Tests deterministic BRS calculation, timing difference detection, and passbook reconciliation"""
    company = Company.objects.create(name="Recon Test Ltd")
    fy = FinancialYear.objects.create(company=company, label="FY 24-25", start_date=date(2024, 4, 1), end_date=date(2025, 3, 31))
    eng = Engagement.objects.create(company=company, financial_year=fy, title="BRS Engagement")

    cashbook_items = [
        {'date': date(2025, 3, 10), 'ref': 'CHQ-101', 'desc': 'Vendor A', 'amount': '50000.00', 'type': 'WITHDRAWAL'},
        {'date': date(2025, 3, 28), 'ref': 'CHQ-102', 'desc': 'Vendor B', 'amount': '25000.00', 'type': 'WITHDRAWAL'}, # Timing: issued not presented
    ]
    bank_items = [
        {'date': date(2025, 3, 11), 'ref': 'CHQ-101', 'desc': 'CLG CHQ VENDOR A', 'amount': '50000.00', 'type': 'WITHDRAWAL'},
        {'date': date(2025, 3, 31), 'ref': 'BANK-CHG', 'desc': 'BANK SERVICE CHARGES', 'amount': '1200.00', 'type': 'WITHDRAWAL'}, # Timing: direct debit
    ]

    # Books Balance: 1,00,000.00
    # + Cheques issued not presented: 25,000.00
    # - Direct bank debits: 1,200.00
    # = Computed Statement Balance: 1,23,800.00
    starting_books_balance = Decimal('100000.00')
    actual_statement_balance = Decimal('123800.00')

    run = BankReconciliationEngine.execute_reconciliation(
        engagement=eng,
        as_of_date=date(2025, 3, 31),
        cashbook_items=cashbook_items,
        bank_items=bank_items,
        starting_cashbook_balance=starting_books_balance,
        actual_statement_balance=actual_statement_balance
    )

    assert run.status == ReconciliationStatus.BALANCED
    assert run.unreconciled_difference == Decimal('0.00')
    assert run.matched_count == 1
    assert run.summary_data['is_fully_reconciled'] is True
    assert Decimal(run.summary_data['cheques_issued_not_presented']) == Decimal('25000.00')
    assert Decimal(run.summary_data['direct_debits_by_bank']) == Decimal('1200.00')

@pytest.mark.django_db
def test_gst_itc_reconciliation():
    """Tests GSTR-2B vs Purchase Register invoice and tax matching"""
    company = Company.objects.create(name="GST Recon Ltd")
    fy = FinancialYear.objects.create(company=company, label="FY 24-25", start_date=date(2024, 4, 1), end_date=date(2025, 3, 31))
    eng = Engagement.objects.create(company=company, financial_year=fy, title="GST Audit")

    purchase_items = [
        {'date': date(2025, 2, 1), 'gstin': '27ABCDE1234F1Z5', 'invoice_no': 'INV-01', 'vendor_name': 'Cloud Corp', 'itc_amount': '18000.00'},
        {'date': date(2025, 2, 15), 'gstin': '27XYZAB9876C1Z2', 'invoice_no': 'INV-02', 'vendor_name': 'Office Mart', 'itc_amount': '5000.00'}, # Missing in 2B
    ]
    gstr2b_items = [
        {'gstin': '27ABCDE1234F1Z5', 'invoice_no': 'INV-01', 'itc_amount': '18000.00'},
    ]

    run = GstItcReconciliationEngine.execute_reconciliation(
        engagement=eng,
        as_of_date=date(2025, 2, 28),
        purchase_items=purchase_items,
        gstr2b_items=gstr2b_items
    )

    assert run.matched_count == 1
    assert run.summary_data['missing_in_gstr_2b_invoices'] == 1
    assert run.summary_data['rule_36_4_risk'] is True
