import pytest
from decimal import Decimal
from apps.ingestion.parsers import parse_indian_amount, parse_flexible_date, classify_document_by_headers

def test_decimal_precision_no_floating_point():
    """Verify exact decimal arithmetic without binary floating-point drift"""
    d1 = Decimal('0.1')
    d2 = Decimal('0.2')
    assert d1 + d2 == Decimal('0.3')
    assert float(0.1) + float(0.2) != 0.3 # Proof that float drifts but Decimal does not!

def test_parse_indian_currency_formats():
    """Tests parsing Indian commas (lakhs/crores), symbols, negative parentheses"""
    # Standard lakhs formatting
    assert parse_indian_amount("1,00,000.00") == Decimal('100000.00')
    assert parse_indian_amount("1,50,25,000.50") == Decimal('15025000.50')

    # Currency symbol prefixed
    assert parse_indian_amount("₹ 45,000.00") == Decimal('45000.00')
    assert parse_indian_amount("Rs. 12,345") == Decimal('12345.00')

    # Parentheses representing negative / credit balance
    assert parse_indian_amount("(25,000.00)") == Decimal('-25000.00')
    assert parse_indian_amount("-15,000.50") == Decimal('-15000.50')

    # Dr / Cr suffixes
    assert parse_indian_amount("50000 Dr") == Decimal('50000.00')
    assert parse_indian_amount("50000 Cr") == Decimal('50000.00')

    # Zero / dashes
    assert parse_indian_amount("-") == Decimal('0.00')
    assert parse_indian_amount("Nil") == Decimal('0.00')
    assert parse_indian_amount(None) is None

def test_parse_flexible_dates():
    """Tests parsing Indian format (DD/MM/YYYY) and standard formats"""
    assert parse_flexible_date("31/03/2025") == "2025-03-31"
    assert parse_flexible_date("15-08-2024") == "2024-08-15"
    assert parse_flexible_date("2024-04-01") == "2024-04-01"
    assert parse_flexible_date("InvalidDate") is None

def test_document_classification_by_headers():
    """Tests deterministic document classification based on column signatures"""
    gstr_headers = ["GSTIN of Supplier", "Trade Name", "Invoice number", "Taxable Value", "Integrated Tax"]
    assert classify_document_by_headers(gstr_headers) == "GSTR_2B"

    bank_headers = ["Txn Date", "Value Date", "Description", "Ref No", "Withdrawal", "Deposit", "Balance"]
    assert classify_document_by_headers(bank_headers) == "BANK_STATEMENT"

    tb_headers = ["Account Code", "Particulars", "Debit (INR)", "Credit (INR)"]
    assert classify_document_by_headers(tb_headers) == "TRIAL_BALANCE"
