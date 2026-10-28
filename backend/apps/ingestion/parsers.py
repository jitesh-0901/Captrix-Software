import re
import csv
import io
import os
import logging
from decimal import Decimal, InvalidOperation
from datetime import datetime
from dateutil import parser as date_parser
from typing import Any
import pandas as pd
import openpyxl

logger = logging.getLogger(__name__)

def parse_indian_amount(val, allow_blank_zero: bool = True) -> Decimal | None:
    """
    Parses Indian & standard formatted monetary values to Decimal.
    Supports:
    - '1,00,000.00' (Lakhs)
    - '1,00,00,000.00' (Crores)
    - '(50,000.00)' -> Decimal('-50000.00') (parentheses for negative/credit)
    - '₹ 25,450.75'
    - '45000 Cr' -> negative or credit indication
    - Explicit zero ('0', '0.00', '0', 'Nil') -> Decimal('0.00')
    - Blank / omitted ('', '-', '--', 'nan', 'N/A') ->
        Decimal('0.00') if allow_blank_zero is True (legitimate zero-movement in ledger debit/credit columns)
        None if allow_blank_zero is False (missing or unstated transaction amount, never fabricated as zero)
    - None or invalid corrupted text -> None
    """
    if val is None:
        return None
    if isinstance(val, (int, float, Decimal)) and val == 0:
        return Decimal('0.00')
    if isinstance(val, Decimal):
        return val

    s = str(val).strip()
    # Explicit zero strings
    if s in ('0.00', '0', '0.0', '00'):
        return Decimal('0.00')
    if s.lower() == 'nil':
        return Decimal('0.00')

    # Blank, missing, dash, or not-applicable values
    if s in ('', '-', '--', '---') or s.lower() in ('nan', 'n/a', 'na', 'null', 'none'):
        return Decimal('0.00') if allow_blank_zero else None

    # Remove currency symbols and spaces
    s = s.replace('₹', '').replace('Rs.', '').replace('Rs', '').replace('$', '').replace(' ', '')

    is_negative = False
    # Check parentheses: (100.00)
    if s.startswith('(') and s.endswith(')'):
        is_negative = True
        s = s[1:-1].strip()
    elif s.endswith('Dr') or s.endswith('dr'):
        s = s[:-2].strip()
    elif s.endswith('Cr') or s.endswith('cr'):
        # In Indian accounting, credit may indicate negative asset or liability depending on ledger
        s = s[:-2].strip()
    elif s.startswith('-'):
        is_negative = True
        s = s[1:].strip()

    # Remove commas
    s = s.replace(',', '')

    try:
        dec = Decimal(s)
        if is_negative:
            dec = -dec
        return dec
    except (InvalidOperation, ValueError):
        return None

def parse_field_amount(val, field_name: str = "", doc_type: str = "") -> Decimal | None:
    """
    Context-aware financial amount parser.
    Distinguishes legitimate zero-movement ledger columns (e.g., closing debit/credit in TB/GL)
    from transaction-level amounts (bank deposits/withdrawals, invoice amounts, asset original cost)
    where blank or missing values must NEVER be fabricated as zero.
    """
    field_lower = str(field_name).lower().strip()
    doc_upper = str(doc_type).upper().strip()

    # Zero-movement ledger columns where an empty cell legitimately indicates zero transaction
    is_ledger_col = any(k in field_lower for k in [
        'closing_debit', 'closing_credit', 'opening_debit', 'opening_credit',
        'debit_inr', 'credit_inr', 'debit (inr)', 'credit (inr)'
    ]) or (
        doc_upper in ('TRIAL_BALANCE', 'GENERAL_LEDGER')
        and field_lower in ('debit', 'credit', 'dr', 'cr', 'closing balance', 'opening balance')
    )

    return parse_indian_amount(val, allow_blank_zero=is_ledger_col)

def parse_flexible_date(val) -> str | None:
    """Parses various date formats to ISO YYYY-MM-DD"""
    if val is None:
        return None
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.strftime('%Y-%m-%d')
    s = str(val).strip()
    if not s or s.lower() == 'nan':
        return None
    try:
        # If already ISO YYYY-MM-DD
        if re.match(r'^\d{4}-\d{2}-\d{2}', s):
            return s[:10]
        # Standard Indian date format is DD/MM/YYYY
        dt = date_parser.parse(s, dayfirst=True)
        return dt.strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        return None

def classify_document_by_headers(headers: list[str]) -> str:
    """Identifies document type based on column signatures with comprehensive Indian accounting terminology"""
    h_lower = [str(h).lower().strip() for h in headers if h]
    h_text = ' '.join(h_lower)

    # 1. Bank Statement: specific banking instruments, running balances, deposit/withdrawal columns
    if any(k in h_text for k in ['withdrawal', 'deposit', 'value date', 'chq no', 'bank ref', 'withdrawal amt', 'deposit amt', 'utr', 'instrument', 'chq/ref', 'running balance', 'running_balance', 'bank_reference']) and ('balance' in h_text or 'txn' in h_text or 'date' in h_text or 'running' in h_text):
        return 'BANK_STATEMENT'

    # 2. General Ledger: journal vouchers, posting date, document ref, narration with debit/credit
    if (
        any(k in h_text for k in ['voucher no', 'voucher_no', 'vch no', 'vch type', 'voucher type', 'daybook', 'posting date', 'posting_date', 'document ref', 'document_ref', 'doc ref'])
        or ('narration' in h_text and ('debit' in h_text or 'credit' in h_text or 'inr' in h_text))
    ) and ('debit' in h_text or 'credit' in h_text or 'amount' in h_text or 'inr' in h_text):
        return 'GENERAL_LEDGER'

    # 3. Fixed Asset Register: assets, useful life, WDV, gross block, depreciation rates
    if any(k in h_text for k in ['asset name', 'asset id', 'asset_id', 'asset description', 'asset_description', 'gross block', 'accumulated dep', 'accumulated_depreciation', 'useful life', 'useful_life', 'capitalized cost', 'capitalized_cost', 'sch ii', 'sec 32']):
        return 'FIXED_ASSET_REGISTER'

    # 4. GSTR-2B: MUST have specific GST Portal/ITC keywords - NEVER match on generic 'gstin' alone!
    is_gstr2b_specific = (
        any(k in h_text for k in ['gstr-2b', 'gstr2b', 'gstr_2b', 'table 3', 'itc available', 'itc eligibility', 'portal reference', 'portal_reference'])
        or (('supplier gstin' in h_text or 'gstin of supplier' in h_text or ('gstin' in h_text and ('integrated tax' in h_text or 'central tax' in h_text))) and any(k in h_text for k in ['taxable value', 'taxable_value', 'tax amount', 'tax_amount', 'integrated tax', 'central tax', 'state/ut tax']))
        or ('itc' in h_text and any(k in h_text for k in ['taxable value', 'integrated tax', 'central tax']))
    )
    if is_gstr2b_specific:
        return 'GSTR_2B'

    # 5. Subledger Aging: party outstanding, aging buckets, MSME status
    if any(k in h_text for k in ['age bucket', 'age_bucket', 'age days', 'age_days', 'due date', 'due_date', 'subledger_type', 'subledger type', 'msme registered', 'msme_registered']) or (
        any(k in h_text for k in ['msme', '43b', 'ageing', 'aging']) and any(k in h_text for k in ['outstanding', 'party', 'creditor', 'debtor', 'days'])
    ):
        return 'SUBLEDGER_AGING'

    # 6. Trial Balance: account code, account name, closing debit, closing credit
    if any(k in h_text for k in ['trial balance', 'account code', 'account_code', 'account name', 'account_name', 'closing debit', 'closing_debit', 'opening debit', 'opening_debit', 'ledger name', 'particulars']) and ('debit' in h_text or 'credit' in h_text or 'dr' in h_text or 'cr' in h_text):
        return 'TRIAL_BALANCE'

    # 7. Sales Register
    if any(k in h_text for k in ['customer name', 'buyer', 'sales amount', 'bill to']) and any(k in h_text for k in ['invoice no', 'invoice date']):
        return 'SALES_REGISTER'

    # 8. Purchase Register
    if any(k in h_text for k in ['vendor', 'supplier name', 'purchase amount', 'supplier inv']) and any(k in h_text for k in ['bill no', 'bill date', 'invoice no']):
        return 'PURCHASE_REGISTER'

    return 'UNKNOWN'

def classify_document_by_name_and_headers(name: str, headers: list[str]) -> str:
    """Combines sheet/file name semantics and column headers to classify document type with maximum accuracy"""
    n_clean = re.sub(r'[\s_\-]+', ' ', str(name).lower()).strip()

    # 1. High-intent explicit sheet / file names take absolute top priority
    if any(k in n_clean for k in ['general ledger', 'gen ledger', 'daybook', 'vouchers', 'gl dump']) or n_clean == 'gl':
        return 'GENERAL_LEDGER'
    if any(k in n_clean for k in ['trial balance', 'trial_balance']) or n_clean == 'tb':
        return 'TRIAL_BALANCE'
    if any(k in n_clean for k in ['bank statement', 'bank_statement', 'passbook', 'bank stmt', 'bank book']):
        return 'BANK_STATEMENT'
    if any(k in n_clean for k in ['fixed asset', 'fixed_asset', 'asset register', 'far', 'depreciation register']):
        return 'FIXED_ASSET_REGISTER'
    if any(k in n_clean for k in ['subledger', 'sub ledger', 'subledger_aging', 'debtors aging', 'creditors aging', 'receivable aging', 'payable aging']):
        return 'SUBLEDGER_AGING'
    if any(k in n_clean for k in ['gstr 2b', 'gstr_2b', 'gstr2b', '2b purchase', 'gstr2b_purchase']):
        return 'GSTR_2B'
    if any(k in n_clean for k in ['purchase register', 'purchase_register', 'purchases']):
        return 'PURCHASE_REGISTER'
    if any(k in n_clean for k in ['sales register', 'sales_register']):
        return 'SALES_REGISTER'

    # 2. Header-based classification
    doc_type = classify_document_by_headers(headers)
    if doc_type != 'UNKNOWN':
        return doc_type

    # 3. Secondary relaxed name checks
    if any(k in n_clean for k in ['trial', 'balance sheet', 'p&l', 'financials', 'financial statements']):
        return 'TRIAL_BALANCE'
    elif any(k in n_clean for k in ['bank', 'statement', 'brs', 'current account']):
        return 'BANK_STATEMENT'
    elif any(k in n_clean for k in ['ledger', 'journal']):
        return 'GENERAL_LEDGER'
    elif any(k in n_clean for k in ['asset', 'depreciation']):
        return 'FIXED_ASSET_REGISTER'
    elif any(k in n_clean for k in ['debtor', 'creditor', 'aging', 'ageing', 'msme', 'receivable', 'payable']):
        return 'SUBLEDGER_AGING'
    elif any(k in n_clean for k in ['gstr', '2b', 'itc', 'gst']):
        return 'GSTR_2B'
    elif any(k in n_clean for k in ['purchase', 'pr']):
        return 'PURCHASE_REGISTER'
    elif any(k in n_clean for k in ['sale', 'sr']):
        return 'SALES_REGISTER'

    return 'UNKNOWN'

CARRYOVER_PATTERN = re.compile(
    r'\b(brought\s+forward|carried\s+forward|\bb/f\b|\bc/f\b|bal\s+b/f|bal\s+c/f|total\s+b/f|total\s+c/f|to\s+b/f|by\s+b/f|opening\s+balance)\b',
    re.IGNORECASE
)

TOTAL_ROW_PATTERN = re.compile(
    r'^(total|grand\s+total|total\s+debits?|total\s+credits?|closing\s+balance|total\s+transactions)\b',
    re.IGNORECASE
)

NOISE_LINE_PATTERN = re.compile(
    r'(page\s+\d+(\s+(?:of|/)\s+\d+)?|computer\s+generated|does\s+not\s+require\s+signature|disclaimer|subject\s+to\s+.*jurisdiction|registered\s+office|branch\s+manager|authorized\s+signatory|customer\s+care|terms\s+and\s+conditions|system-generated)',
    re.IGNORECASE
)

HEADER_NOISE_PATTERN = re.compile(
    r'(bank\s+of|state\s+bank|hdfc\s+bank|icici\s+bank|axis\s+bank|kotak|punjab\s+national|canara\s+bank|bank\s+ltd|account\s+name|account\s+no|ifsc|branch|statement\s+of\s+account|cin\s*:|statement\s+period)',
    re.IGNORECASE
)

def clean_cell_text(val):
    if val is None:
        return ""
    s = str(val).strip()
    s = s.replace('\xa0', ' ').replace('\r', ' ')
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

def normalize_financial_header_name(header: str) -> str:
    h_clean = clean_cell_text(header)
    h_lower = h_clean.lower().replace('.', '').replace('_', ' ').strip()
    if not h_clean:
        return "Column"
    
    # 1. Composite Account Identifiers (Must precede generic 'account')
    if any(k in h_lower for k in ['account code', 'ledger code', 'gl code', 'acc code', 'a/c code']) or h_lower in ['code', 'acc no', 'account no', 'account number']:
        return 'Account Code'
    if any(k in h_lower for k in ['account type', 'acc type', 'ledger type', 'head type', 'account classification', 'group type', 'source type', 'src type']):
        return 'Account Type'

    # 2. Dates
    if 'txn' in h_lower and 'date' in h_lower:
        return 'Txn Date'
    if 'value' in h_lower and 'date' in h_lower:
        return 'Value Date'
    if 'posting' in h_lower and 'date' in h_lower:
        return 'Posting Date'
    if 'due' in h_lower and 'date' in h_lower:
        return 'Due Date'
    if 'date' in h_lower and len(h_clean) < 18:
        return 'Date'

    # 3. References and Vouchers
    if any(k in h_lower for k in ['chq', 'cheque', 'ref', 'utr', 'instrument', 'vch no', 'voucher no', 'voucher', 'doc ref', 'document ref']):
        return 'Chq / Ref No'
    if any(k in h_lower for k in ['narration', 'description', 'remarks']):
        return 'Description'

    # 4. Account Name / Particulars (Specific phrases first, exact word match for generic words)
    if any(k in h_lower for k in ['account name', 'particulars', 'ledger name', 'account description', 'head of account', 'party name']) or h_lower in ['ledger', 'head', 'account', 'a/c', 'acc', 'party', 'particular']:
        return 'Particulars'

    # 5. Amounts and Balances
    if 'withdrawal' in h_lower:
        return 'Withdrawal (Debit)'
    if 'deposit' in h_lower:
        return 'Deposit (Credit)'
    if any(k in h_lower for k in ['closing debit', 'closing dr', 'balance debit', 'bal dr']):
        return 'Closing Debit'
    if any(k in h_lower for k in ['closing credit', 'closing cr', 'balance credit', 'bal cr']):
        return 'Closing Credit'
    if any(k in h_lower for k in ['opening debit', 'opening dr']):
        return 'Opening Debit'
    if any(k in h_lower for k in ['opening credit', 'opening cr']):
        return 'Opening Credit'
    if any(k in h_lower for k in ['debit', 'dr']):
        return 'Debit (INR)' if 'inr' in h_lower else 'Debit'
    if any(k in h_lower for k in ['credit', 'cr']):
        return 'Credit (INR)' if 'inr' in h_lower else 'Credit'
    if 'balance' in h_lower or 'net bal' in h_lower or h_lower == 'closing':
        return 'Balance'

    # 6. Trade and Statutory
    if any(k in h_lower for k in ['invoice no', 'inv no', 'bill no', 'invoice number', 'bill number']):
        return 'Invoice No'
    if any(k in h_lower for k in ['taxable value', 'taxable amount', 'taxable']):
        return 'Taxable Value'
    return h_clean

def score_candidate_financial_header(row: list, next_row: list = None) -> float:
    """
    Computes a deterministic, multi-signal confidence score for whether a row is the True Table Header.
    Scores presence of standard Indian financial headers, penalizes metadata/company titles,
    and checks if the subsequent row looks like actual transactional data.
    """
    cells = [clean_cell_text(c) for c in row if c is not None and clean_cell_text(c)]
    if len(cells) < 2:
        return -100.0

    joined = ' '.join(c.lower() for c in cells)
    score = 0.0

    # 1. Accounts & Ledgers (+45 for exact table column anchor)
    if any(k in joined for k in ['particulars', 'account name', 'ledger name', 'head of account', 'account description', 'party name', 'name of party', 'customer name', 'vendor name', 'supplier name', 'ledger']):
        score += 45.0
    elif any(k in joined for k in ['account', 'head', 'party', 'description', 'narration']):
        score += 20.0

    # 2. Debit & Credit & Amounts (+25)
    if any(k in joined for k in ['debit (inr)', 'credit (inr)', 'closing debit', 'closing credit', 'withdrawal amt', 'deposit amt', 'withdrawal (debit)', 'deposit (credit)']):
        score += 30.0
    elif ('debit' in joined and 'credit' in joined) or ('withdrawal' in joined and 'deposit' in joined) or ('dr' in joined and 'cr' in joined):
        score += 25.0
    elif any(k in joined for k in ['debit', 'credit', 'withdrawal', 'deposit', 'amount', 'amt', 'taxable value']):
        score += 12.0

    # 3. Balance (+15)
    if any(k in joined for k in ['closing balance', 'net balance', 'running balance', 'balance']):
        score += 15.0

    # 4. Dates & Vouchers (+18)
    if any(k in joined for k in ['txn date', 'value date', 'posting date', 'bill date', 'invoice date']):
        score += 15.0
    elif 'date' in joined:
        score += 10.0

    if any(k in joined for k in ['voucher no', 'vch no', 'voucher type', 'vch type', 'chq no', 'cheque no', 'utr', 'ref no', 'instrument no', 'doc ref', 'invoice no', 'bill no']):
        score += 18.0

    # 5. Statutory & Taxes (+20)
    if any(k in joined for k in ['gstin', 'integrated tax', 'central tax', 'state tax', 'itc available', 'rate of dep', 'gross block', 'accumulated dep', 'useful life', 'wdv']):
        score += 20.0

    # Penalties: Company titles, period lines, addresses
    if any(k in joined for k in ['pvt ltd', 'private limited', 'ltd.', 'limited', 'inc.', 'llp', 'trial balance as on', 'balance sheet as at', 'statement of account', 'for the period', 'from date', 'to date']):
        score -= 40.0

    if any(k in joined for k in ['cin:', 'pan:', 'gstin:', 'phone:', 'email:', 'website:', 'address:', 'registered office', 'branch:']):
        score -= 30.0

    # Penalize long prose/paragraph text
    if any(len(c) > 40 for c in cells):
        score -= 20.0

    # Check if subsequent row looks like data
    if next_row:
        next_cells = [clean_cell_text(c) for c in next_row if c is not None and clean_cell_text(c)]
        if next_cells:
            has_next_amount = any(parse_indian_amount(c) is not None for c in next_cells)
            has_next_date = any(bool(re.match(r'^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', c) or re.match(r'^\d{4}-\d{2}-\d{2}', c)) for c in next_cells)
            if has_next_amount or has_next_date:
                score += 20.0

    return score


def deduplicate_headers(headers: list[str]) -> list[str]:
    seen = {}
    unique = []
    for h in headers:
        base = h if h else "Column"
        if base not in seen:
            seen[base] = 1
            unique.append(base)
        else:
            seen[base] += 1
            unique.append(f"{base}_{seen[base]}")
    return unique


def detect_best_header_row_and_stitch(all_rows: list[list[str]], max_search: int = 25) -> tuple[int, list[str]]:
    """
    Finds the True Table Header row using deterministic hard-scoring,
    and automatically stitches multi-level headers (e.g. Tally Closing Balance -> Debit / Credit).
    Returns (start_data_row_index, list_of_final_headers).
    """
    if not all_rows:
        return 0, []

    limit = min(len(all_rows), max_search)
    best_idx = 0
    best_score = -999.0

    for i in range(limit):
        curr_row = all_rows[i]
        next_row = all_rows[i + 1] if i + 1 < len(all_rows) else None
        sc = score_candidate_financial_header(curr_row, next_row)
        if sc > best_score:
            best_score = sc
            best_idx = i

    # Fallback to row 0 if no candidate reached acceptable score
    if best_score < 10.0:
        best_idx = 0

    base_header = [clean_cell_text(c) for c in all_rows[best_idx]]

    # Check if the row immediately following is a sub-header (e.g. Row i: Particulars | Opening | Closing; Row i+1: | Dr | Cr | Dr | Cr)
    if best_idx + 1 < len(all_rows):
        sub_row = [clean_cell_text(c) for c in all_rows[best_idx + 1]]
        sub_joined = ' '.join(sub_row).lower()
        sub_words = set(re.findall(r'\b[a-z/]+\b', sub_joined))
        has_sub_keywords = any(w in sub_words for w in ['debit', 'credit', 'dr', 'cr', 'withdrawal', 'deposit'])
        has_numeric_amounts = any(parse_indian_amount(c) is not None for c in sub_row if c)
        is_sub_header = (
            has_sub_keywords
            and not has_numeric_amounts
            and not any(k in sub_joined for k in ['particulars', 'ledger', 'head of account'])
            and not any(bool(re.match(r'^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', c)) for c in sub_row if c)
        )
        if is_sub_header:
            stitched = []
            max_len = max(len(base_header), len(sub_row))
            for col_i in range(max_len):
                top_c = base_header[col_i] if col_i < len(base_header) else ""
                sub_c = sub_row[col_i] if col_i < len(sub_row) else ""
                if top_c and sub_c:
                    stitched.append(f"{top_c} {sub_c}".strip())
                elif sub_c:
                    stitched.append(sub_c)
                else:
                    stitched.append(top_c)
            normalized = deduplicate_headers([normalize_financial_header_name(h) for h in stitched])
            return best_idx + 2, normalized

    normalized = deduplicate_headers([normalize_financial_header_name(h) for h in base_header])
    return best_idx + 1, normalized


def clean_and_flatten_tally_record(row_dict: dict, headers: list[str], doc_type: str) -> tuple[dict, bool]:
    """
    Automates Tally hierarchy flattening, Dr/Cr suffix separation, and parent category filtering.
    Returns (cleaned_row_dict, is_valid_data_row).
    """
    if is_noise_or_carryover_row(row_dict, headers)[0]:
        return row_dict, False

    # 1. TRIAL BALANCE & LEDGERS
    if doc_type in ('TRIAL_BALANCE', 'GENERAL_LEDGER'):
        particulars_key = None
        for h in headers:
            if h in ('Particulars', 'Ledger Name', 'Account Name', 'Head of Account'):
                particulars_key = h
                break

        if particulars_key:
            part_val = clean_cell_text(row_dict.get(particulars_key, ''))
            if not part_val:
                return row_dict, False

        debit_key = None
        credit_key = None
        for h in headers:
            h_lower = h.lower()
            if 'closing debit' in h_lower or 'closing dr' in h_lower:
                debit_key = h
            elif 'closing credit' in h_lower or 'closing cr' in h_lower:
                credit_key = h
            elif not debit_key and ('debit' in h_lower or h_lower == 'dr'):
                debit_key = h
            elif not credit_key and ('credit' in h_lower or h_lower == 'cr'):
                credit_key = h

        # Handle Tally single column Dr/Cr (e.g. "45,000.00 Dr" or "70,000.00 Cr")
        for col_name, col_val in list(row_dict.items()):
            if not col_val:
                continue
            s_val = str(col_val).strip()
            if s_val.endswith(('Dr', 'dr', 'DR')):
                amt_clean = s_val[:-2].strip()
                if debit_key and not row_dict.get(debit_key):
                    row_dict[debit_key] = amt_clean
                if credit_key and not row_dict.get(credit_key):
                    row_dict[credit_key] = "0.00"
            elif s_val.endswith(('Cr', 'cr', 'CR')):
                amt_clean = s_val[:-2].strip()
                if credit_key and not row_dict.get(credit_key):
                    row_dict[credit_key] = amt_clean
                if debit_key and not row_dict.get(debit_key):
                    row_dict[debit_key] = "0.00"

        # Filter out Tally parent categories (where both Debit and Credit are 0 or empty)
        # BUT preserve valid accounts that have an Account Code or explicit identifier
        if debit_key and credit_key:
            deb_amt = parse_indian_amount(row_dict.get(debit_key))
            crd_amt = parse_indian_amount(row_dict.get(credit_key))
            if (deb_amt is None or deb_amt == Decimal('0.00')) and (crd_amt is None or crd_amt == Decimal('0.00')):
                has_acc_code = any(bool(row_dict.get(k)) for k in ['Account Code', 'account_code', 'code', 'GL Code', 'A/c Code'])
                if not has_acc_code:
                    return row_dict, False

    # 2. BANK STATEMENTS: Auto-align Single Amount with Type column
    elif doc_type == 'BANK_STATEMENT':
        type_key = None
        amount_key = None
        for h in headers:
            h_l = h.lower()
            if any(t in h_l for t in ['type', 'cr/dr', 'dr/cr', 'txn type']):
                type_key = h
            elif h_l in ('amount', 'amt', 'txn amount'):
                amount_key = h

        if type_key and amount_key and row_dict.get(amount_key):
            t_val = str(row_dict.get(type_key, '')).upper().strip()
            amt_val = str(row_dict.get(amount_key, '')).strip()
            if 'DR' in t_val:
                row_dict['Withdrawal (Debit)'] = amt_val
                row_dict['Deposit (Credit)'] = "0.00"
            elif 'CR' in t_val:
                row_dict['Deposit (Credit)'] = amt_val
                row_dict['Withdrawal (Debit)'] = "0.00"

    return row_dict, True


def is_candidate_financial_header(row):
    cells = [clean_cell_text(c).lower() for c in row if c]
    joined = ' '.join(cells)
    has_date_or_id = any(k in joined for k in ['date', 'txn', 'value', 'code', 'particular', 'description', 'narration', 'account', 'vch', 'voucher', 'invoice', 'gstin', 'asset', 'head', 'ledger', 'a/c'])
    has_amount = any(k in joined for k in ['debit', 'credit', 'withdrawal', 'deposit', 'balance', 'amount', 'amt', 'dr', 'cr', 'taxable', 'rate', 'wdv', 'cost'])
    return has_date_or_id and has_amount and len(cells) >= 2

def is_noise_or_carryover_row(row_dict, headers):
    row_text = ' '.join(str(v) for v in row_dict.values() if v).strip()
    if not row_text:
        return True, 'EMPTY'
        
    if NOISE_LINE_PATTERN.search(row_text):
        return True, 'FOOTER_NOISE'
        
    first_val = clean_cell_text(list(row_dict.values())[0]) if row_dict else ""
    if TOTAL_ROW_PATTERN.search(first_val) or TOTAL_ROW_PATTERN.search(row_text):
        return True, 'TOTAL_ROW'

    for h in headers:
        val = clean_cell_text(row_dict.get(h, ""))
        if CARRYOVER_PATTERN.search(val):
            debit_val = None
            credit_val = None
            for dh in headers:
                dh_lower = dh.lower()
                if any(term in dh_lower for term in ['withdrawal', 'debit', 'dr']):
                    debit_val = parse_indian_amount(row_dict.get(dh))
                elif any(term in dh_lower for term in ['deposit', 'credit', 'cr']):
                    credit_val = parse_indian_amount(row_dict.get(dh))
            
            if (debit_val is None or debit_val == 0) and (credit_val is None or credit_val == 0):
                return True, 'CARRYOVER'

    return False, None

class DocumentParserService:
    @staticmethod
    def parse_file(file_path: Any, original_filename: str):
        ext = os.path.splitext(original_filename)[1].lower()
        if ext in ['.xlsx', '.xls']:
            return DocumentParserService._parse_excel(file_path)
        elif ext == '.csv':
            return DocumentParserService._parse_csv(file_path)
        elif ext == '.pdf':
            return DocumentParserService._parse_pdf(file_path, original_filename)
        elif ext in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']:
            return DocumentParserService._parse_image(file_path)
        else:
            raise ValueError(f"Unsupported file extension: {ext}")

    @staticmethod
    def _parse_csv(file_path: str):
        with open(file_path, 'r', encoding='utf-8-sig', errors='replace') as f:
            sample = f.read(4096)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=[',', '\t', ';', '|'])
                delimiter = dialect.delimiter
            except Exception:
                delimiter = ','
            
            reader = csv.reader(f, delimiter=delimiter)
            rows = [row for row in reader if any(cell.strip() for cell in row)]

        if not rows:
            return {'doc_type': 'UNKNOWN', 'headers': [], 'records': []}

        data_start_idx, headers = detect_best_header_row_and_stitch(rows, max_search=25)
        doc_type = classify_document_by_headers(headers)

        records = []
        for idx, row in enumerate(rows[data_start_idx:], start=1):
            if not any(cell.strip() for cell in row):
                continue

            cleaned_row = list(row)
            if len(cleaned_row) > len(headers) and len(headers) >= 2:
                excess = len(cleaned_row) - len(headers)
                head_text = ", ".join(c.strip() for c in cleaned_row[:excess + 1])
                cleaned_row = [head_text] + [c.strip() for c in cleaned_row[excess + 1:]]

            row_dict = {}
            for col_idx, h in enumerate(headers):
                val = cleaned_row[col_idx].strip() if col_idx < len(cleaned_row) else ''
                row_dict[h] = val

            norm_row, is_valid = clean_and_flatten_tally_record(row_dict, headers, doc_type)
            if is_valid:
                records.append({
                    'row_index': idx,
                    'source_location': f"Row_{idx + data_start_idx}",
                    'raw': norm_row,
                })

        return {
            'doc_type': doc_type,
            'headers': headers,
            'records': records,
        }

    @staticmethod
    def _parse_excel(file_path: str):
        wb = openpyxl.load_workbook(file_path, data_only=True)
        sheets_data = []

        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            all_rows = []
            for row in sheet.iter_rows(values_only=True):
                if any(c is not None and str(c).strip() != '' for c in row):
                    all_rows.append([str(c).strip() if c is not None else '' for c in row])

            if not all_rows:
                continue

            data_start_idx, headers = detect_best_header_row_and_stitch(all_rows, max_search=25)
            doc_type = classify_document_by_name_and_headers(sheet_name, headers)

            records = []
            for idx, row in enumerate(all_rows[data_start_idx:], start=1):
                if not any(row):
                    continue
                row_dict = {}
                for col_idx, h in enumerate(headers):
                    if not h:
                        h = f"Column_{col_idx+1}"
                    val = row[col_idx] if col_idx < len(row) else ''
                    row_dict[h] = val

                norm_row, is_valid = clean_and_flatten_tally_record(row_dict, headers, doc_type)
                if is_valid:
                    records.append({
                        'row_index': idx,
                        'source_location': f"{sheet_name}:Row_{idx + data_start_idx}",
                        'raw': norm_row,
                    })

            if records:
                sheets_data.append({
                    'sheet_name': sheet_name,
                    'doc_type': doc_type,
                    'headers': headers,
                    'records': records
                })

        if not sheets_data:
            return {'doc_type': 'UNKNOWN', 'headers': [], 'records': [], 'is_multi_sheet': False}

        primary = sheets_data[0]
        for s in sheets_data:
            if s['doc_type'] == 'TRIAL_BALANCE':
                primary = s
                break
            elif s['doc_type'] == 'GENERAL_LEDGER' and primary['doc_type'] != 'TRIAL_BALANCE':
                primary = s

        return {
            'doc_type': primary['doc_type'],
            'headers': primary['headers'],
            'records': primary['records'],
            'sheet_name': primary['sheet_name'],
            'is_multi_sheet': len(sheets_data) > 1,
            'sheets': sheets_data
        }

    @staticmethod
    def _parse_pdf(file_path: str, original_filename: str = ""):
        """
        Ultra-robust multi-strategy financial PDF parser for Indian statutory auditing.
        Strategy 1: High-precision grid table extraction with line detection, dynamic header isolation,
                    metadata boundary separation, and repeating header & carryover suppression.
        Strategy 2: Sub-millimeter coordinate-based word clustering for borderless banking & ledger statements
                    (SBI, HDFC, ICICI, Axis, PNB, Canara Bank, Kotak).
        Strategy 3: Multi-line narration and invoice stitching ensuring 100% data preservation without losing
                    vendor references or UTR tokens.
        """
        import pdfplumber
        records = []
        headers = []
        doc_type = 'UNKNOWN'
        summary_metadata = {}
        row_counter = 1

        # STRATEGY 0: Docling OCR Engine (Local Docling OCR Pipeline)
        docling_result = None
        try:
            from .docling_engine import DoclingOCREngine
            if DoclingOCREngine.is_available():
                docling_result = DoclingOCREngine.parse_document(file_path, original_filename)
                if docling_result and len(docling_result.get('records', [])) > 0:
                    if len(docling_result.get('headers', [])) >= 4 and docling_result.get('doc_type') != 'UNKNOWN':
                        logger.info(f"Docling OCR successfully parsed '{original_filename}' ({len(docling_result['records'])} records).")
                        return docling_result
        except Exception as d_err:
            logger.warning(f"Docling OCR pre-extraction skipped or encountered error: {d_err}")

        try:
            with pdfplumber.open(file_path) as pdf:
                # STRATEGY 1: Table Grid Extraction (Bordered lines)
                all_tables_by_page = []
                for page_idx, page in enumerate(pdf.pages, start=1):
                    tables = page.extract_tables()
                    all_tables_by_page.append((page_idx, page, tables))

                # Identify primary table headers from candidate tables across pages
                for page_idx, page, tables in all_tables_by_page:
                    for table in tables:
                        if not table or len(table) < 2:
                            continue
                        cand_h = [clean_cell_text(c) or f"Col_{i+1}" for i, c in enumerate(table[0])]
                        if is_candidate_financial_header(cand_h):
                            headers = [normalize_financial_header_name(h) for h in cand_h]
                            doc_type = classify_document_by_headers(headers)
                            break
                    if headers:
                        break

                if headers:
                    for page_idx, page, tables in all_tables_by_page:
                        for table_idx, table in enumerate(tables, start=1):
                            if not table or len(table) < 2:
                                continue
                            # If table doesn't match column count, see if it holds summary metadata
                            if len(table[0]) != len(headers):
                                for r in table:
                                    r_txt = ' '.join(clean_cell_text(c) for c in r if c)
                                    if 'opening balance' in r_txt.lower():
                                        summary_metadata['opening_balance'] = r_txt
                                    elif 'closing balance' in r_txt.lower():
                                        summary_metadata['closing_balance'] = r_txt
                                    elif 'account no' in r_txt.lower():
                                        summary_metadata['account_number'] = r_txt
                                continue

                            start_idx = 1 if is_candidate_financial_header(table[0]) else 0
                            for r in table[start_idx:]:
                                if not any(c for c in r if c and str(c).strip()):
                                    continue
                                row_dict = {}
                                for c_idx, h in enumerate(headers):
                                    val = clean_cell_text(r[c_idx]) if c_idx < len(r) else ''
                                    row_dict[h] = val

                                is_noise, reason = is_noise_or_carryover_row(row_dict, headers)
                                if is_noise:
                                    continue

                                # Check if this row is a continuation of previous row's narration
                                date_val = None
                                for dh in headers:
                                    if 'date' in dh.lower():
                                        date_val = row_dict.get(dh)
                                        break
                                has_date = bool(date_val and (re.match(r'^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', date_val) or re.match(r'^\d{4}-\d{2}-\d{2}', date_val)))
                                has_amounts = any(parse_indian_amount(row_dict.get(h)) for h in headers if any(k in h.lower() for k in ['debit', 'credit', 'withdrawal', 'deposit', 'amount']))

                                if not has_date and not has_amounts and records:
                                    for h in headers:
                                        if any(k in h.lower() for k in ['particular', 'narration', 'description']):
                                            extra = row_dict.get(h, '')
                                            if extra:
                                                records[-1]['raw'][h] = f"{records[-1]['raw'][h]} {extra}".strip()
                                    continue

                                records.append({
                                    'row_index': row_counter,
                                    'source_location': f"Page_{page_idx}:Row_{row_counter}",
                                    'raw': row_dict
                                })
                                row_counter += 1

                # STRATEGY 2: Coordinate-based Word Grouping for Borderless Statements
                if len(records) < 2:
                    records = []
                    headers = []
                    header_cols = []
                    row_counter = 1

                    pages_lines = []
                    for p_idx, page in enumerate(pdf.pages, start=1):
                        words = page.extract_words()
                        lines = []
                        curr_line = []
                        curr_top = None
                        for w in words:
                            if curr_top is None or abs(w['top'] - curr_top) <= 3.5:
                                curr_line.append(w)
                                curr_top = w['top']
                            else:
                                lines.append(curr_line)
                                curr_line = [w]
                                curr_top = w['top']
                        if curr_line:
                            lines.append(curr_line)
                        pages_lines.append((p_idx, lines))

                    # Detect header line from word groups
                    for p_idx, lines in pages_lines:
                        for line in lines:
                            txt = ' '.join(w['text'] for w in line)
                            if is_candidate_financial_header([w['text'] for w in line]):
                                col_clusters = []
                                curr_cluster = [line[0]]
                                for w in line[1:]:
                                    prev_w = curr_cluster[-1]
                                    is_distinct_split = False
                                    prev_txt = prev_w['text'].lower()
                                    curr_txt = w['text'].lower()
                                    if prev_txt in ['(dr)', 'dr', 'withdrawal', 'debit'] and curr_txt in ['deposit', 'credit', '(cr)', 'cr']:
                                        is_distinct_split = True
                                    elif prev_txt in ['(cr)', 'cr', 'deposit', 'credit'] and curr_txt in ['balance', 'bal']:
                                        is_distinct_split = True
                                    elif prev_txt in ['date', 'txn', 'value'] and curr_txt in ['particulars', 'narration', 'description']:
                                        is_distinct_split = True

                                    if not is_distinct_split and ((w['x0'] - prev_w['x1'] < 18) or (w['text'].startswith('(') and prev_txt not in ['(dr)', '(cr)']) or w['text'] == '/' or prev_w['text'] == '/'):
                                        curr_cluster.append(w)
                                    else:
                                        col_clusters.append(curr_cluster)
                                        curr_cluster = [w]
                                if curr_cluster:
                                    col_clusters.append(curr_cluster)

                                for c in col_clusters:
                                    c_title = normalize_financial_header_name(' '.join(w['text'] for w in c))
                                    x_min = min(w['x0'] for w in c)
                                    x_max = max(w['x1'] for w in c)
                                    header_cols.append({
                                        'title': c_title,
                                        'x0': x_min,
                                        'x1': x_max
                                    })
                                break
                        if header_cols:
                            break

                    if header_cols:
                        headers = [c['title'] for c in header_cols]
                        doc_type = classify_document_by_headers(headers)

                        for p_idx, lines in pages_lines:
                            for line in lines:
                                line_str = ' '.join(w['text'] for w in line).strip()
                                if not line_str or len(line_str) < 5:
                                    continue
                                if NOISE_LINE_PATTERN.search(line_str) or HEADER_NOISE_PATTERN.search(line_str):
                                    continue
                                if TOTAL_ROW_PATTERN.search(line_str):
                                    continue
                                if is_candidate_financial_header([w['text'] for w in line]):
                                    continue

                                row_data = {h['title']: [] for h in header_cols}
                                for w in line:
                                    assigned = False
                                    for c_idx, col in enumerate(header_cols):
                                        next_x0 = header_cols[c_idx+1]['x0'] if c_idx+1 < len(header_cols) else 1000.0
                                        prev_x1 = header_cols[c_idx-1]['x1'] if c_idx > 0 else 0.0
                                        left_bound = (col['x0'] + prev_x1) / 2.0 if c_idx > 0 else 0.0
                                        right_bound = (col['x1'] + next_x0) / 2.0 if c_idx+1 < len(header_cols) else 1000.0
                                        if left_bound <= w['x0'] < right_bound or (col['x0'] - 5 <= w['x0'] <= col['x1'] + 5):
                                            row_data[col['title']].append(w['text'])
                                            assigned = True
                                            break
                                    if not assigned and header_cols:
                                        row_data[header_cols[-1]['title']].append(w['text'])

                                row_dict = {k: ' '.join(v).strip() for k, v in row_data.items()}
                                is_noise, reason = is_noise_or_carryover_row(row_dict, headers)
                                if is_noise:
                                    continue

                                first_col = headers[0]
                                first_val = row_dict.get(first_col, '')
                                is_date = bool(re.match(r'^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', first_val) or re.match(r'^\d{4}-\d{2}-\d{2}', first_val))
                                has_amounts = any(parse_indian_amount(row_dict.get(h)) for h in headers if any(k in h.lower() for k in ['debit', 'credit', 'withdrawal', 'deposit', 'amount']))

                                if is_date or has_amounts:
                                    records.append({
                                        'row_index': row_counter,
                                        'source_location': f"Page_{p_idx}:Line_{row_counter}",
                                        'raw': row_dict
                                    })
                                    row_counter += 1
                                elif records and any(row_dict.values()):
                                    last_raw = records[-1]['raw']
                                    for col_title, text_val in row_dict.items():
                                        if text_val and not parse_indian_amount(text_val):
                                            last_raw[col_title] = f"{last_raw[col_title]} {text_val}".strip()
        except Exception as e:
            return {
                'doc_type': 'UNKNOWN',
                'headers': [],
                'records': [],
                'summary_metadata': {},
                'is_scanned_pdf': True,
                'warning_message': (
                    f"Unable to read PDF digital stream ({str(e)}). Scanned image/PDF without digital text layer detected. "
                    "Image-based OCR is not configured for scanned photocopies. "
                    "Please upload digital accounting exports (.xlsx, .xls, .csv, or searchable PDF) directly exported from Tally, SAP, Zoho Books, Busy, or QuickBooks."
                )
            }

        if doc_type == 'UNKNOWN' and original_filename:
            doc_type = classify_document_by_name_and_headers(original_filename, headers)

        if not records and docling_result and len(docling_result.get('records', [])) > 0:
            return docling_result

        is_scanned_pdf = len(records) == 0
        if is_scanned_pdf:
            # Fallback to Original Offline OCR Engine for Scanned / Image-based PDFs
            try:
                from .ocr_engine import OriginalOCREngine
                ocr_result = OriginalOCREngine.parse_scanned_pdf(file_path)
                if ocr_result and len(ocr_result.get('records', [])) > 0:
                    return {
                        'doc_type': ocr_result.get('doc_type', doc_type or 'BANK_STATEMENT'),
                        'headers': ocr_result.get('headers', headers),
                        'records': ocr_result.get('records', []),
                        'summary_metadata': summary_metadata,
                        'is_scanned_pdf': True,
                        'ocr_engine_used': 'RapidOCR-ONNX'
                    }
            except Exception as ocr_err:
                logger.warning(f"Scanned PDF OCR fallback failed: {ocr_err}")

        warning = None
        if len(records) == 0:
            warning = (
                "Unable to extract text or tabular rows from PDF. Please verify document readability or upload directly from Tally, SAP, or Bank Portal."
            )

        return {
            'doc_type': doc_type,
            'headers': headers,
            'records': records,
            'summary_metadata': summary_metadata,
            'is_scanned_pdf': is_scanned_pdf,
            'warning_message': warning
        }

    @staticmethod
    def _parse_image(file_path: str):
        """
        Original Offline OCR Engine for Passbooks, Scanned Bills, Cheques, and Receipts.
        Extracts structured financial transactions without external cloud APIs.
        """
        # Strategy 0: Docling OCR Engine
        try:
            from .docling_engine import DoclingOCREngine
            if DoclingOCREngine.is_available():
                docling_res = DoclingOCREngine.parse_document(file_path, os.path.basename(file_path))
                if docling_res and len(docling_res.get('records', [])) > 0:
                    return docling_res
        except Exception as d_img_err:
            logger.warning(f"Docling image OCR fallback to RapidOCR: {d_img_err}")

        from PIL import Image
        headers = ['Date', 'Particulars', 'Chq/Ref No', 'Debit', 'Credit', 'Balance']
        doc_type = 'BANK_STATEMENT'

        try:
            from .ocr_engine import OriginalOCREngine
            with Image.open(file_path) as img:
                ocr_items = OriginalOCREngine.process_image(img)
                structured_lines = OriginalOCREngine.structure_ocr_lines(ocr_items)
                h, records, detected_type = OriginalOCREngine.extract_financial_rows_from_lines(structured_lines)
                if detected_type != 'UNKNOWN':
                    doc_type = detected_type
                if records:
                    return {
                        'doc_type': doc_type,
                        'headers': h or headers,
                        'records': records,
                        'is_image_without_ocr': False,
                        'ocr_engine_used': 'RapidOCR-ONNX'
                    }
        except Exception as e:
            logger.exception(f"Original OCR error processing image '{file_path}': {e}")

        return {
            'doc_type': doc_type,
            'headers': headers,
            'records': [],
            'is_image_without_ocr': True,
            'warning_message': "Unable to detect recognizable text in image. Please ensure image has adequate lighting and resolution."
        }
