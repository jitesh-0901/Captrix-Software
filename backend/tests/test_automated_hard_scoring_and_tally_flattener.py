import pytest
from decimal import Decimal
from apps.ingestion.parsers import (
    score_candidate_financial_header,
    detect_best_header_row_and_stitch,
    clean_and_flatten_tally_record,
    classify_document_by_name_and_headers,
    parse_indian_amount
)

def test_hard_scoring_skips_company_title_and_finds_tally_header():
    """
    Verifies that multi-signal hard scoring ignores company titles, addresses, and period lines,
    and accurately locates the true table header row.
    """
    rows = [
        ["Apex Infotech Private Limited", "", "", ""],
        ["CIN: U72200TN2020PTC123456", "PAN: AABCA1234F", "", ""],
        ["Trial Balance as on 31-Mar-2025", "", "", ""],
        ["", "", "", ""],
        ["Particulars", "Opening Balance", "", "Closing Balance"],
        ["", "Debit", "Credit", "Debit", "Credit"],
        ["Capital Account", "", "", "10,00,000.00 Cr", ""],
        ["Sundry Debtors", "", "", "4,50,000.00 Dr", ""],
        ["Bank of India - Current A/c", "", "", "2,15,450.75 Dr", ""],
        ["Office Rent Expense", "", "", "1,20,000.00 Dr", ""],
    ]

    start_idx, headers = detect_best_header_row_and_stitch(rows, max_search=10)

    # Must skip title rows 0-3, detect Row 4, stitch Row 5, and start data at Row 6
    assert start_idx == 6
    assert "Particulars" in headers[0]
    assert any("Debit" in h for h in headers)
    assert any("Credit" in h for h in headers)

def test_tally_hierarchy_flattener_removes_empty_parents():
    """
    Verifies that Tally parent categories (e.g. Current Assets without Dr/Cr) are stripped,
    preventing corrupt ₹0.00 ledger accounts.
    """
    headers = ["Particulars", "Closing Debit", "Closing Credit"]

    # Parent group row with no amounts
    parent_row = {"Particulars": "Current Assets", "Closing Debit": "", "Closing Credit": ""}
    norm_row, is_valid = clean_and_flatten_tally_record(parent_row, headers, "TRIAL_BALANCE")
    assert is_valid is False

    # Leaf ledger row with valid amounts
    leaf_row = {"Particulars": "HDFC Bank - 501004523", "Closing Debit": "2,50,000.00", "Closing Credit": "0.00"}
    norm_row, is_valid = clean_and_flatten_tally_record(leaf_row, headers, "TRIAL_BALANCE")
    assert is_valid is True
    assert norm_row["Closing Debit"] == "2,50,000.00"

def test_tally_single_column_dr_cr_auto_split():
    """
    Verifies that amounts with 'Dr' or 'Cr' suffixes are automatically parsed into Debit and Credit.
    """
    headers = ["Particulars", "Closing Debit", "Closing Credit"]

    row_dr = {"Particulars": "Prepaid Insurance", "Amount": "45,000.00 Dr", "Closing Debit": "", "Closing Credit": ""}
    norm_row, is_valid = clean_and_flatten_tally_record(row_dr, headers, "TRIAL_BALANCE")
    assert is_valid is True
    assert norm_row["Closing Debit"] == "45,000.00"
    assert norm_row["Closing Credit"] == "0.00"

    row_cr = {"Particulars": "Trade Payables", "Amount": "1,80,000.00 Cr", "Closing Debit": "", "Closing Credit": ""}
    norm_row, is_valid = clean_and_flatten_tally_record(row_cr, headers, "TRIAL_BALANCE")
    assert is_valid is True
    assert norm_row["Closing Debit"] == "0.00"
    assert norm_row["Closing Credit"] == "1,80,000.00"

def test_bank_statement_single_amount_type_splitter():
    """
    Verifies that bank statements with Amount and Type ('DR'/'CR') auto-split into Withdrawal and Deposit.
    """
    headers = ["Date", "Description", "Amount", "Type", "Withdrawal (Debit)", "Deposit (Credit)", "Balance"]

    row_dr = {"Date": "2025-03-10", "Description": "VENDOR PAYMENT", "Amount": "25000.00", "Type": "DR"}
    norm_row, is_valid = clean_and_flatten_tally_record(row_dr, headers, "BANK_STATEMENT")
    assert is_valid is True
    assert norm_row["Withdrawal (Debit)"] == "25000.00"
    assert norm_row["Deposit (Credit)"] == "0.00"

    row_cr = {"Date": "2025-03-12", "Description": "CLIENT RECEIPT", "Amount": "75000.00", "Type": "CR"}
    norm_row, is_valid = clean_and_flatten_tally_record(row_cr, headers, "BANK_STATEMENT")
    assert is_valid is True
    assert norm_row["Withdrawal (Debit)"] == "0.00"
    assert norm_row["Deposit (Credit)"] == "75000.00"
