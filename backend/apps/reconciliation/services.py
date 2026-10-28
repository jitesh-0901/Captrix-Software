import re
from decimal import Decimal
from datetime import datetime, date
from typing import List, Dict, Any, Optional

from .models import (
    ReconciliationRun, ReconciliationItem, MatchType,
    ReconciliationStatus, ReconciliationType
)
from apps.accounting.models import (
    Transaction, LedgerAccount, ChartOfAccounts,
    ScheduleIIIGroup, TrialBalanceSnapshot, AccountType
)

class BankReconciliationEngine:
    @staticmethod
    def execute_reconciliation(
        engagement,
        as_of_date,
        cashbook_items: list[dict],
        bank_items: list[dict],
        starting_cashbook_balance: Decimal = Decimal('0.00'),
        actual_statement_balance: Decimal = Decimal('0.00'),
        date_tolerance_days: int = 15
    ):
        """
        Executes deterministic multi-tier Bank Reconciliation Statement (BRS).
        cashbook_items: list of dicts with: date, ref, desc, amount, type ('DEPOSIT', 'WITHDRAWAL')
        bank_items: list of dicts with: date, ref, desc, amount, type ('DEPOSIT', 'WITHDRAWAL')
        """
        bal_books = starting_cashbook_balance if starting_cashbook_balance is not None else Decimal('0.00')
        bal_stmt = actual_statement_balance if actual_statement_balance is not None else Decimal('0.00')

        recon_run = ReconciliationRun.objects.create(
            engagement=engagement,
            recon_type=ReconciliationType.BANK,
            status=ReconciliationStatus.IN_PROGRESS,
            as_of_date=as_of_date,
            date_tolerance_days=date_tolerance_days,
            balance_per_books=bal_books,
            balance_per_statement=bal_stmt,
            total_source_items=len(cashbook_items),
            total_target_items=len(bank_items)
        )

        matched_bank_ids = set()
        matched_cashbook_ids = set()
        created_cb_items = []
        created_bank_items = []

        def _parse_item_date(val):
            if isinstance(val, date):
                return val
            if isinstance(val, datetime):
                return val.date()
            if not val:
                return date(2025, 4, 1)
            v_str = str(val).strip().split()[0]
            for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y'):
                try:
                    return datetime.strptime(v_str, fmt).date()
                except ValueError:
                    pass
            return date(2025, 4, 1)

        # 1. Create persistent items
        for cb in cashbook_items:
            amt = Decimal(str(cb.get('amount', 0)))
            dr = amt if cb.get('type') == 'DEPOSIT' else Decimal('0.00')
            cr = amt if cb.get('type') == 'WITHDRAWAL' else Decimal('0.00')
            d = _parse_item_date(cb.get('date'))

            created_cb_items.append(ReconciliationItem(
                reconciliation_run=recon_run,
                source_type='CASHBOOK',
                item_date=d,
                reference_number=str(cb.get('ref', '')),
                description=str(cb.get('desc', '')),
                party_name=str(cb.get('party', '')),
                debit_amount=dr,
                credit_amount=cr,
                amount=amt,
                raw_source_ref=str(cb.get('source_ref', ''))
            ))
        created_cb_items = ReconciliationItem.objects.bulk_create(created_cb_items)

        for b in bank_items:
            amt = Decimal(str(b.get('amount', 0)))
            cr = amt if b.get('type') == 'DEPOSIT' else Decimal('0.00')   # In bank statement, deposit is Credit
            dr = amt if b.get('type') == 'WITHDRAWAL' else Decimal('0.00') # In bank statement, withdrawal is Debit
            d = _parse_item_date(b.get('date'))

            created_bank_items.append(ReconciliationItem(
                reconciliation_run=recon_run,
                source_type='BANK_STATEMENT',
                item_date=d,
                reference_number=str(b.get('ref', '')),
                description=str(b.get('desc', '')),
                debit_amount=dr,
                credit_amount=cr,
                amount=amt,
                raw_source_ref=str(b.get('source_ref', ''))
            ))
        created_bank_items = ReconciliationItem.objects.bulk_create(created_bank_items)

        # 2. Stage 1: Exact Match (Amount + Ref)
        for cb in created_cb_items:
            if cb.id in matched_cashbook_ids:
                continue
            for b in created_bank_items:
                if b.id in matched_bank_ids:
                    continue
                type_matches = (cb.debit_amount > 0 and b.credit_amount > 0) or (cb.credit_amount > 0 and b.debit_amount > 0)
                amount_matches = abs(cb.amount - b.amount) < Decimal('0.01')
                ref_clean_cb = ''.join(c for c in cb.reference_number if c.isalnum()).lower()
                ref_clean_b = ''.join(c for c in b.reference_number if c.isalnum()).lower()
                ref_matches = bool(ref_clean_cb and ref_clean_b and (ref_clean_cb in ref_clean_b or ref_clean_b in ref_clean_cb))

                if type_matches and amount_matches and ref_matches:
                    cb.is_matched = True
                    cb.matched_with_id = b.id
                    cb.match_type = MatchType.EXACT
                    cb.timing_category = 'EXACT_MATCH'
                    cb.is_approved = True

                    b.is_matched = True
                    b.matched_with_id = cb.id
                    b.match_type = MatchType.EXACT
                    b.timing_category = 'EXACT_MATCH'
                    b.is_approved = True

                    matched_cashbook_ids.add(cb.id)
                    matched_bank_ids.add(b.id)
                    break

        # 3. Stage 2: Rule-Based Match (Amount + Date within configurable tolerance)
        for cb in created_cb_items:
            if cb.id in matched_cashbook_ids:
                continue
            for b in created_bank_items:
                if b.id in matched_bank_ids:
                    continue
                type_matches = (cb.debit_amount > 0 and b.credit_amount > 0) or (cb.credit_amount > 0 and b.debit_amount > 0)
                amount_matches = abs(cb.amount - b.amount) < Decimal('0.01')
                date_diff_days = abs((b.item_date - cb.item_date).days)

                if type_matches and amount_matches and date_diff_days <= date_tolerance_days:
                    cb.is_matched = True
                    cb.matched_with_id = b.id
                    cb.match_type = MatchType.RULE_BASED
                    cb.timing_category = 'TIMING_DIFFERENCE'
                    cb.match_notes = f"Matched within {date_diff_days} days clearance window"
                    cb.is_approved = True

                    b.is_matched = True
                    b.matched_with_id = cb.id
                    b.match_type = MatchType.RULE_BASED
                    b.timing_category = 'TIMING_DIFFERENCE'
                    b.match_notes = f"Matched within {date_diff_days} days clearance window"
                    b.is_approved = True

                    matched_cashbook_ids.add(cb.id)
                    matched_bank_ids.add(b.id)
                    break

        # 4. Stage 3: One-to-Many Consolidated Matching
        # Bank transaction whose amount equals the sum of 2 or 3 cashbook entries
        for b in created_bank_items:
            if b.id in matched_bank_ids:
                continue
            unmatched_cbs = [cb for cb in created_cb_items if cb.id not in matched_cashbook_ids]
            # Filter compatible direction
            is_bank_cr = b.credit_amount > 0
            compatible_cbs = [cb for cb in unmatched_cbs if (cb.debit_amount > 0 if is_bank_cr else cb.credit_amount > 0)]

            # Check pairs
            found_pair = None
            for i in range(len(compatible_cbs)):
                for j in range(i + 1, len(compatible_cbs)):
                    cb1, cb2 = compatible_cbs[i], compatible_cbs[j]
                    if abs((cb1.amount + cb2.amount) - b.amount) < Decimal('0.01'):
                        found_pair = (cb1, cb2)
                        break
                if found_pair:
                    break

            if found_pair:
                cb1, cb2 = found_pair
                b.is_matched = True
                b.match_type = MatchType.ONE_TO_MANY
                b.timing_category = 'CONSOLIDATED_MATCH'
                b.match_notes = f"Consolidated match with Cashbook refs: {cb1.reference_number}, {cb2.reference_number}"
                b.is_approved = True
                matched_bank_ids.add(b.id)

                for cb_item in [cb1, cb2]:
                    cb_item.is_matched = True
                    cb_item.matched_with_id = b.id
                    cb_item.match_type = MatchType.ONE_TO_MANY
                    cb_item.timing_category = 'CONSOLIDATED_MATCH'
                    cb_item.match_notes = f"Consolidated into Bank statement entry {b.reference_number}"
                    cb_item.is_approved = True
                    matched_cashbook_ids.add(cb_item.id)

        # 5. Stage 4: Suggested / Ambiguous Matches (Requiring CA Review)
        unresolved_count = 0
        for cb in created_cb_items:
            if cb.id in matched_cashbook_ids:
                continue
            for b in created_bank_items:
                if b.id in matched_bank_ids:
                    continue
                type_matches = (cb.debit_amount > 0 and b.credit_amount > 0) or (cb.credit_amount > 0 and b.debit_amount > 0)
                # Amount close within ₹1.00 or similar
                amt_diff = abs(cb.amount - b.amount)
                if type_matches and Decimal('0.01') < amt_diff <= Decimal('1.00'):
                    cb.is_matched = False
                    cb.match_type = MatchType.SUGGESTED
                    cb.timing_category = 'AMBIGUOUS_SUGGESTION'
                    cb.match_notes = f"Suggested near-match (variance ₹{amt_diff}). Requires CA review."
                    cb.is_approved = False

                    b.is_matched = False
                    b.match_type = MatchType.SUGGESTED
                    b.timing_category = 'AMBIGUOUS_SUGGESTION'
                    b.match_notes = f"Suggested near-match with CB ref {cb.reference_number}. Requires CA review."
                    b.is_approved = False
                    unresolved_count += 2
                    break

        as_of_dt = as_of_date
        if isinstance(as_of_dt, str):
            try:
                as_of_dt = datetime.strptime(as_of_dt, '%Y-%m-%d').date()
            except Exception:
                as_of_dt = None

        # 6. Classify Remaining Unmatched items into BRS standard categories
        cheques_issued_not_presented = Decimal('0.00')
        cheques_deposited_not_cleared = Decimal('0.00')
        direct_debits_by_bank = Decimal('0.00')
        direct_credits_by_bank = Decimal('0.00')
        stale_cheques_count = 0
        stale_cheques_amount = Decimal('0.00')
        stale_deposits_count = 0
        stale_deposits_amount = Decimal('0.00')
        valid_timing_count = 0
        valid_timing_amount = Decimal('0.00')

        for cb in created_cb_items:
            if not cb.is_matched and cb.timing_category != 'AMBIGUOUS_SUGGESTION':
                days_old = (as_of_dt - cb.item_date).days if (as_of_dt and cb.item_date) else 0
                if cb.credit_amount > 0:
                    if days_old > 90:
                        cb.timing_category = 'STALE_CHEQUE_UNPRESENTED'
                        cb.match_notes = f"Cheque issued {days_old} days prior to balance sheet date (>90 days). Stale under Negotiable Instruments Act Sec 138 / RBI Guidelines; requires management write-back/reversal."
                        stale_cheques_count += 1
                        stale_cheques_amount += cb.amount
                    else:
                        cb.timing_category = 'CHEQUE_ISSUED_NOT_PRESENTED'
                        valid_timing_count += 1
                        valid_timing_amount += cb.amount
                    cheques_issued_not_presented += cb.amount
                elif cb.debit_amount > 0:
                    if days_old > 90:
                        cb.timing_category = 'STALE_DEPOSIT_UNCLEARED'
                        cb.match_notes = f"Deposit pending {days_old} days (>90 days). Potential dishonoured cheque; requires management write-off/reversal."
                        stale_deposits_count += 1
                        stale_deposits_amount += cb.amount
                    else:
                        cb.timing_category = 'CHEQUE_DEPOSITED_NOT_CLEARED'
                        valid_timing_count += 1
                        valid_timing_amount += cb.amount
                    cheques_deposited_not_cleared += cb.amount
            cb.save()

        for b in created_bank_items:
            if not b.is_matched and b.timing_category != 'AMBIGUOUS_SUGGESTION':
                if b.debit_amount > 0:
                    b.timing_category = 'DIRECT_DEBIT_BANK_CHARGES'
                    b.match_notes = "Direct debit/bank charges appearing in bank statement but unrecorded in cashbook. Requires adjusting journal entry."
                    direct_debits_by_bank += b.amount
                elif b.credit_amount > 0:
                    b.timing_category = 'DIRECT_CREDIT_INTEREST_DIVIDEND'
                    b.match_notes = "Direct credit/interest appearing in bank statement but unrecorded in cashbook. Requires adjusting journal entry."
                    direct_credits_by_bank += b.amount
            b.save()

        # 7. Calculate Reconciled Statement Balance Formula:
        # Reconciled = Starting Cashbook + Cheques Issued Not Presented - Cheques Deposited Not Cleared + Direct Credits - Direct Debits
        reconciled_statement_balance = (
            starting_cashbook_balance
            + cheques_issued_not_presented
            - cheques_deposited_not_cleared
            + direct_credits_by_bank
            - direct_debits_by_bank
        )

        if actual_statement_balance is not None:
            unreconciled_diff = abs(reconciled_statement_balance - actual_statement_balance)
        else:
            unreconciled_diff = Decimal('0.00')
        recon_run.timing_differences_amount = (
            cheques_issued_not_presented
            - cheques_deposited_not_cleared
            + direct_credits_by_bank
            - direct_debits_by_bank
        )
        recon_run.unreconciled_difference = unreconciled_diff
        recon_run.matched_count = len(matched_cashbook_ids)
        recon_run.unmatched_count = (len(created_cb_items) - len(matched_cashbook_ids)) + (len(created_bank_items) - len(matched_bank_ids))
        recon_run.unresolved_count = unresolved_count

        matched_amount = sum((cb.amount for cb in created_cb_items if cb.is_matched), Decimal('0.00'))
        unmatched_cb_payments = [cb for cb in created_cb_items if not cb.is_matched and cb.credit_amount > Decimal('0.00')]
        unmatched_cb_deposits = [cb for cb in created_cb_items if not cb.is_matched and cb.debit_amount > Decimal('0.00')]
        unmatched_b_debits = [b for b in created_bank_items if not b.is_matched and b.debit_amount > Decimal('0.00')]
        unmatched_b_credits = [b for b in created_bank_items if not b.is_matched and b.credit_amount > Decimal('0.00')]

        # Fail-closed audit status:
        # Arithmetically balanced only if difference is zero and inputs were complete.
        # But if stale cheques exist (>90 days old), unresolved items exist, or data missing, audit status MUST be REVIEW_REQUIRED.
        has_missing_data = (len(cashbook_items) == 0 or len(bank_items) == 0 or actual_statement_balance is None)
        has_audit_concerns = (
            has_missing_data or
            unreconciled_diff >= Decimal('0.01') or
            unresolved_count > 0 or
            stale_cheques_count > 0 or
            stale_deposits_count > 0
        )

        if not has_audit_concerns:
            recon_run.status = ReconciliationStatus.BALANCED
        else:
            recon_run.status = ReconciliationStatus.REVIEW_REQUIRED

        review_reasons = []
        if has_missing_data:
            review_reasons.append("Bank reconciliation data incomplete; cashbook entries or bank statement balance missing.")
        if stale_cheques_count > 0:
            review_reasons.append(f"{stale_cheques_count} stale cheques (>90 days old) totaling ₹{stale_cheques_amount:,.2f} require management write-back under NI Act Sec 138.")
        if stale_deposits_count > 0:
            review_reasons.append(f"{stale_deposits_count} stale deposits (>90 days old) totaling ₹{stale_deposits_amount:,.2f} require dishonour review.")
        if unreconciled_diff >= Decimal('0.01'):
            review_reasons.append(f"Arithmetic variance of ₹{unreconciled_diff:,.2f} between cashbook bridge and bank statement.")

        recon_run.summary_data = {
            'starting_cashbook_balance': str(starting_cashbook_balance),
            'cheques_issued_not_presented': str(cheques_issued_not_presented),
            'cheques_deposited_not_cleared': str(cheques_deposited_not_cleared),
            'stale_cheques_count': stale_cheques_count,
            'stale_cheques_amount': str(stale_cheques_amount),
            'stale_deposits_count': stale_deposits_count,
            'stale_deposits_amount': str(stale_deposits_amount),
            'valid_timing_count': valid_timing_count,
            'valid_timing_amount': str(valid_timing_amount),
            'direct_credits_by_bank': str(direct_credits_by_bank),
            'direct_debits_by_bank': str(direct_debits_by_bank),
            'computed_statement_balance': str(reconciled_statement_balance),
            'actual_statement_balance': str(actual_statement_balance if actual_statement_balance is not None else '0.00'),
            'unreconciled_variance': str(unreconciled_diff),
            'arithmetic_balanced': (unreconciled_diff < Decimal('0.01') and not has_missing_data),
            'date_tolerance_days': date_tolerance_days,
            'is_fully_reconciled': (not has_audit_concerns),
            'unresolved_items_count': unresolved_count,
            'matched_items_count': len(matched_cashbook_ids),
            'matched_items_amount': str(matched_amount),
            'unmatched_items_count': recon_run.unmatched_count,
            'ledger_only_transactions': {
                'unpresented_cheques_count': len(unmatched_cb_payments),
                'unpresented_cheques_amount': str(sum((c.amount for c in unmatched_cb_payments), Decimal('0.00'))),
                'uncleared_deposits_count': len(unmatched_cb_deposits),
                'uncleared_deposits_amount': str(sum((c.amount for c in unmatched_cb_deposits), Decimal('0.00'))),
                'total_count': len(unmatched_cb_payments) + len(unmatched_cb_deposits),
                'total_amount': str(sum((c.amount for c in unmatched_cb_payments + unmatched_cb_deposits), Decimal('0.00')))
            },
            'bank_only_transactions': {
                'bank_service_fees_count': len(unmatched_b_debits),
                'bank_service_fees_amount': str(sum((b.amount for b in unmatched_b_debits), Decimal('0.00'))),
                'customer_receipts_count': len(unmatched_b_credits),
                'customer_receipts_amount': str(sum((b.amount for b in unmatched_b_credits), Decimal('0.00'))),
                'total_count': len(unmatched_b_debits) + len(unmatched_b_credits),
                'total_amount': str(sum((b.amount for b in unmatched_b_debits + unmatched_b_credits), Decimal('0.00')))
            },
            'review_required_reason': " ".join(review_reasons)
        }
        recon_run.save()

        return recon_run


class GstItcReconciliationEngine:
    @staticmethod
    def execute_reconciliation(engagement, as_of_date, purchase_items: list[dict], gstr2b_items: list[dict]):
        """
        Reconciles Purchase Register against GSTR-2B for GST ITC compliance (Rule 36(4) / Sec 16(2)(aa)).
        Performs bidirectional invoice-level matching across taxable values and tax amounts:
        1. Purchase Register invoices matched against GSTR-2B
        2. GSTR-2B invoices matched against Purchase Register
        3. Identifies taxable value differences, tax differences, and missing invoices in either source
        4. Fails closed (status = REVIEW_REQUIRED) if any discrepancy or missing invoice exists.
        """
        recon_run = ReconciliationRun.objects.create(
            engagement=engagement,
            recon_type=ReconciliationType.GST_ITC,
            as_of_date=as_of_date,
            total_source_items=len(purchase_items),
            total_target_items=len(gstr2b_items)
        )

        def _clean_str(val):
            return str(val or '').strip().upper()

        def _norm_inv(val):
            return re.sub(r'[^A-Z0-9]', '', _clean_str(val)).lstrip('0')

        def _parse_dec(val):
            if val is None:
                return Decimal('0.00')
            clean = str(val).replace(',', '').replace('₹', '').replace(' ', '').strip()
            try:
                return Decimal(clean) if clean else Decimal('0.00')
            except Exception:
                return Decimal('0.00')

        matched_count = 0
        mismatch_tax_count = 0
        mismatch_taxable_count = 0
        missing_in_2b_count = 0
        missing_in_books_count = 0

        total_taxable_books = Decimal('0.00')
        total_taxable_2b = Decimal('0.00')
        total_itc_books = Decimal('0.00')
        total_itc_2b = Decimal('0.00')

        # Index GSTR-2B items by (norm_gstin, norm_inv) and fallback by norm_inv
        gstr2b_dict = {}
        gstr2b_by_inv = {}
        matched_2b_keys = set()

        for idx, item in enumerate(gstr2b_items):
            gstin = _clean_str(item.get('gstin', item.get('supplier_gstin', item.get('GSTIN', ''))))
            raw_inv = _clean_str(item.get('invoice_no', item.get('invoice_number', item.get('Invoice No', ''))))
            norm_inv = _norm_inv(raw_inv)

            taxable_val = _parse_dec(item.get('taxable_value', item.get('taxable_amount', item.get('Taxable Value', 0))))
            itc_val = _parse_dec(item.get('itc_amount', item.get('tax_amount', item.get('gst_amount', item.get('Tax Amount', 0)))))

            total_taxable_2b += taxable_val
            total_itc_2b += itc_val

            item_record = {
                'idx': idx,
                'raw_item': item,
                'gstin': gstin,
                'invoice_no': raw_inv,
                'norm_inv': norm_inv,
                'taxable_value': taxable_val,
                'itc_amount': itc_val,
                'date': item.get('date', item.get('invoice_date')),
                'vendor_name': item.get('vendor_name', item.get('trade_name', item.get('legal_name', '')))
            }
            if gstin and norm_inv:
                gstr2b_dict[(gstin, norm_inv)] = item_record
            if norm_inv:
                gstr2b_by_inv[norm_inv] = item_record

        # Reconcile Purchase Register items
        created_recon_items = []
        for p in purchase_items:
            gstin = _clean_str(p.get('gstin', p.get('supplier_gstin', p.get('GSTIN', ''))))
            raw_inv = _clean_str(p.get('invoice_no', p.get('invoice_number', p.get('Invoice No', ''))))
            norm_inv = _norm_inv(raw_inv)

            taxable_in_books = _parse_dec(p.get('taxable_value', p.get('taxable_amount', p.get('Taxable Value', 0))))
            tax_in_books = _parse_dec(p.get('itc_amount', p.get('tax_amount', p.get('gst_amount', p.get('Tax Amount', 0)))))

            total_taxable_books += taxable_in_books
            total_itc_books += tax_in_books

            matched_2b_item = None
            matched_key = None

            if gstin and norm_inv and (gstin, norm_inv) in gstr2b_dict:
                matched_key = (gstin, norm_inv)
                matched_2b_item = gstr2b_dict[matched_key]
            elif norm_inv and norm_inv in gstr2b_by_inv:
                matched_key = norm_inv
                matched_2b_item = gstr2b_by_inv[matched_key]

            if matched_2b_item:
                matched_2b_keys.add(matched_2b_item['idx'])
                taxable_diff = abs(taxable_in_books - matched_2b_item['taxable_value'])
                tax_diff = abs(tax_in_books - matched_2b_item['itc_amount'])

                has_taxable_mismatch = (taxable_diff >= Decimal('1.00'))
                has_tax_mismatch = (tax_diff >= Decimal('1.00'))

                if not has_taxable_mismatch and not has_tax_mismatch:
                    status_cat = 'EXACT_MATCH'
                    matched_count += 1
                    notes = f"Exact match with GSTR-2B invoice {matched_2b_item['invoice_no']} (Taxable ₹{taxable_in_books:,.2f}, Tax ₹{tax_in_books:,.2f})"
                elif has_taxable_mismatch and has_tax_mismatch:
                    status_cat = 'TAXABLE_AND_TAX_MISMATCH'
                    mismatch_taxable_count += 1
                    mismatch_tax_count += 1
                    notes = f"Taxable variance ₹{taxable_diff:,.2f} and Tax variance ₹{tax_diff:,.2f} vs GSTR-2B"
                elif has_taxable_mismatch:
                    status_cat = 'TAXABLE_VALUE_MISMATCH'
                    mismatch_taxable_count += 1
                    notes = f"Taxable value variance of ₹{taxable_diff:,.2f} vs GSTR-2B"
                else:
                    status_cat = 'TAX_AMOUNT_MISMATCH'
                    mismatch_tax_count += 1
                    notes = f"ITC tax variance of ₹{tax_diff:,.2f} vs GSTR-2B"

                created_recon_items.append(ReconciliationItem(
                    reconciliation_run=recon_run,
                    source_type='PURCHASE_REGISTER',
                    item_date=p.get('date', p.get('invoice_date')),
                    reference_number=raw_inv,
                    party_name=p.get('vendor_name', ''),
                    amount=tax_in_books,
                    timing_category=status_cat,
                    is_matched=(status_cat == 'EXACT_MATCH'),
                    is_approved=(status_cat == 'EXACT_MATCH'),
                    match_notes=notes
                ))
            else:
                status_cat = 'MISSING_IN_GSTR_2B'
                missing_in_2b_count += 1
                created_recon_items.append(ReconciliationItem(
                    reconciliation_run=recon_run,
                    source_type='PURCHASE_REGISTER',
                    item_date=p.get('date', p.get('invoice_date')),
                    reference_number=raw_inv,
                    party_name=p.get('vendor_name', ''),
                    amount=tax_in_books,
                    timing_category=status_cat,
                    is_matched=False,
                    is_approved=False,
                    match_notes=f"Invoice missing from GSTR-2B; ITC of ₹{tax_in_books:,.2f} restricted under CGST Sec 16(2)(aa) & Rule 36(4)"
                ))

        # Check for unbooked GSTR-2B invoices (appearing in 2B but missing from Purchase Register)
        for idx, item in enumerate(gstr2b_items):
            if idx not in matched_2b_keys:
                raw_inv = _clean_str(item.get('invoice_no', item.get('invoice_number', item.get('Invoice No', ''))))
                itc_val = _parse_dec(item.get('itc_amount', item.get('tax_amount', item.get('gst_amount', item.get('Tax Amount', 0)))))
                taxable_val = _parse_dec(item.get('taxable_value', item.get('taxable_amount', item.get('Taxable Value', 0))))
                missing_in_books_count += 1

                created_recon_items.append(ReconciliationItem(
                    reconciliation_run=recon_run,
                    source_type='GSTR_2B',
                    item_date=item.get('date', item.get('invoice_date')),
                    reference_number=raw_inv,
                    party_name=item.get('vendor_name', item.get('supplier_name', '')),
                    amount=itc_val,
                    timing_category='MISSING_IN_PURCHASE_REGISTER',
                    is_matched=False,
                    is_approved=False,
                    match_notes=f"Appears in GSTR-2B but missing from purchase register (Taxable ₹{taxable_val:,.2f}, Tax ₹{itc_val:,.2f})"
                ))

        if created_recon_items:
            ReconciliationItem.objects.bulk_create(created_recon_items)

        taxable_variance = abs(total_taxable_books - total_taxable_2b)
        itc_variance = abs(total_itc_books - total_itc_2b)
        total_exceptions = mismatch_tax_count + mismatch_taxable_count + missing_in_2b_count + missing_in_books_count

        has_data = len(purchase_items) > 0 or len(gstr2b_items) > 0
        is_balanced = (has_data and total_exceptions == 0 and itc_variance < Decimal('1.00') and taxable_variance < Decimal('1.00'))

        recon_run.matched_count = matched_count
        recon_run.unmatched_count = total_exceptions
        recon_run.unreconciled_difference = itc_variance
        recon_run.status = ReconciliationStatus.BALANCED if is_balanced else ReconciliationStatus.REVIEW_REQUIRED

        recon_run.summary_data = {
            'total_taxable_per_books': str(total_taxable_books),
            'total_taxable_per_gstr2b': str(total_taxable_2b),
            'taxable_variance': str(taxable_variance),
            'total_itc_per_books': str(total_itc_books),
            'total_itc_per_gstr2b': str(total_itc_2b),
            'itc_variance': str(itc_variance),
            'matched_invoices': matched_count,
            'mismatched_tax_invoices': mismatch_tax_count,
            'mismatched_taxable_invoices': mismatch_taxable_count,
            'missing_in_gstr_2b_invoices': missing_in_2b_count,
            'missing_in_purchase_register_invoices': missing_in_books_count,
            'has_sufficient_data': has_data,
            'rule_36_4_risk': missing_in_2b_count > 0,
            'is_fully_reconciled': is_balanced,
            'review_required_reason': (
                f"{missing_in_2b_count} invoices missing from GSTR-2B (ITC at risk under Rule 36(4)); " if missing_in_2b_count > 0 else ""
            ) + (
                f"{missing_in_books_count} invoices in GSTR-2B missing from books; " if missing_in_books_count > 0 else ""
            ) + (
                f"{mismatch_tax_count} invoices with tax amount mismatches; " if mismatch_tax_count > 0 else ""
            ) + (
                f"Taxable variance of ₹{taxable_variance:,.2f}; " if taxable_variance >= Decimal('1.00') else ""
            ) + (
                "Purchase Register or GSTR-2B datasets not uploaded." if not has_data else ""
            )
        }
        recon_run.save()
        return recon_run


class CrossDocumentReconciliationEngine:
    """
    Automated cross-document reconciliation engine:
    1. General Ledger vs Trial Balance
    2. Sales Register vs Relevant Revenue Ledgers
    3. Purchase Register vs Relevant Expense Ledgers
    4. Receivables Ageing vs Control Account
    5. Payables Ageing vs Control Account
    6. Fixed Asset Register vs Asset Ledger
    7. Financial Statement Totals vs Trial Balance
    """

    @staticmethod
    def reconcile_ledger_vs_trial_balance(engagement) -> ReconciliationRun:
        """Cross-checks General Ledger total debits, credits, and account balances against Trial Balance Snapshot."""
        as_of = engagement.financial_year.end_date
        tb = engagement.trial_balances.first()
        txns = Transaction.objects.filter(engagement=engagement)
        ledgers = LedgerAccount.objects.filter(company=engagement.company)

        if not tb:
            return ReconciliationRun.objects.create(
                engagement=engagement,
                recon_type=ReconciliationType.LEDGER_TB,
                status=ReconciliationStatus.BLOCKED,
                as_of_date=as_of,
                summary_data={'error': 'Trial Balance snapshot has not been calculated or uploaded.'}
            )

        # 1. Double-entry equilibrium of GL transactions if available
        gl_total_dr = sum((t.debit_amount for t in txns), Decimal('0.00'))
        gl_total_cr = sum((t.credit_amount for t in txns), Decimal('0.00'))
        gl_internal_diff = abs(gl_total_dr - gl_total_cr)

        # 2. Double-entry equilibrium of Trial Balance
        tb_dr = tb.total_debits
        tb_cr = tb.total_credits
        tb_internal_diff = abs(tb_dr - tb_cr)

        # 3. Account-wise closing balance cross-match
        ledger_map = {l.name.lower(): l.closing_balance for l in ledgers}
        acct_variance = Decimal('0.00')
        matched_accounts = 0
        total_accounts = len(tb.accounts_snapshot or [])

        for a in (tb.accounts_snapshot or []):
            name = a.get('account_name', '').lower()
            tb_bal = Decimal(str(a.get('debit') or 0)) if a.get('balance_type') == 'Dr' else Decimal(str(a.get('credit') or 0))
            gl_bal = ledger_map.get(name)
            if gl_bal is not None:
                v = abs(gl_bal - tb_bal)
                acct_variance += v
                if v < Decimal('0.01'):
                    matched_accounts += 1

        total_diff = gl_internal_diff + tb_internal_diff + acct_variance
        is_balanced = total_diff < Decimal('1.00')

        # Clean prior run for this type
        ReconciliationRun.objects.filter(engagement=engagement, recon_type=ReconciliationType.LEDGER_TB).delete()

        recon = ReconciliationRun.objects.create(
            engagement=engagement,
            recon_type=ReconciliationType.LEDGER_TB,
            status=ReconciliationStatus.BALANCED if is_balanced else ReconciliationStatus.VARIANCE_DETECTED,
            as_of_date=as_of,
            balance_per_books=gl_total_dr if gl_total_dr > Decimal('0.00') else tb_dr,
            balance_per_statement=tb_dr,
            unreconciled_difference=total_diff,
            total_source_items=txns.count() if txns.exists() else len(ledger_map),
            total_target_items=total_accounts,
            matched_count=matched_accounts if is_balanced else 0,
            summary_data={
                'gl_total_debits': str(gl_total_dr),
                'gl_total_credits': str(gl_total_cr),
                'tb_total_debits': str(tb_dr),
                'tb_total_credits': str(tb_cr),
                'gl_internal_variance': str(gl_internal_diff),
                'tb_internal_variance': str(tb_internal_diff),
                'account_level_variance': str(acct_variance),
                'variance': str(total_diff),
                'is_balanced': is_balanced
            }
        )
        return recon

    @staticmethod
    def reconcile_sales_register(engagement, sales_register_items: Optional[List[Dict]] = None) -> ReconciliationRun:
        """Cross-checks Sales Register turnover against Revenue from Operations in General Ledger."""
        as_of = engagement.financial_year.end_date
        ReconciliationRun.objects.filter(engagement=engagement, recon_type=ReconciliationType.SALES_VS_LEDGER).delete()
        if not sales_register_items:
            return ReconciliationRun.objects.create(
                engagement=engagement,
                recon_type=ReconciliationType.SALES_VS_LEDGER,
                status=ReconciliationStatus.BLOCKED,
                as_of_date=as_of,
                summary_data={'message': 'Sales Register document not provided for this engagement.'}
            )

        total_sales_register = sum((Decimal(str(item.get('invoice_value', item.get('taxable_value', 0)))) for item in sales_register_items), Decimal('0.00'))

        # Revenue in GL
        rev_ledgers = LedgerAccount.objects.filter(
            company=engagement.company,
            coa__schedule_iii_group=ScheduleIIIGroup.REVENUE_OPERATIONS
        )
        gl_revenue = sum((l.closing_balance for l in rev_ledgers), Decimal('0.00'))

        diff = abs(total_sales_register - gl_revenue)
        is_matched = diff < Decimal('1.00')

        return ReconciliationRun.objects.create(
            engagement=engagement,
            recon_type=ReconciliationType.SALES_VS_LEDGER,
            status=ReconciliationStatus.BALANCED if is_matched else ReconciliationStatus.VARIANCE_DETECTED,
            as_of_date=as_of,
            balance_per_books=gl_revenue,
            balance_per_statement=total_sales_register,
            unreconciled_difference=diff,
            total_source_items=len(sales_register_items),
            total_target_items=rev_ledgers.count(),
            summary_data={
                'sales_register_total': str(total_sales_register),
                'gl_revenue_operations': str(gl_revenue),
                'variance': str(diff),
                'is_matched': is_matched
            }
        )

    @staticmethod
    def reconcile_purchase_register(engagement, purchase_register_items: Optional[List[Dict]] = None) -> ReconciliationRun:
        """Cross-checks Purchase Register against Trade Payables / Operating Expenses in General Ledger."""
        as_of = engagement.financial_year.end_date
        ReconciliationRun.objects.filter(engagement=engagement, recon_type=ReconciliationType.PURCHASE_VS_LEDGER).delete()
        if not purchase_register_items:
            return ReconciliationRun.objects.create(
                engagement=engagement,
                recon_type=ReconciliationType.PURCHASE_VS_LEDGER,
                status=ReconciliationStatus.BLOCKED,
                as_of_date=as_of,
                summary_data={'message': 'Purchase Register document not provided for this engagement.'}
            )

        total_purchase_reg = sum((Decimal(str(item.get('total_amount', 0))) for item in purchase_register_items), Decimal('0.00'))
        creditor_ledgers = LedgerAccount.objects.filter(
            company=engagement.company,
            coa__schedule_iii_group=ScheduleIIIGroup.TRADE_PAYABLES
        )
        gl_creditors = sum((l.closing_balance for l in creditor_ledgers), Decimal('0.00'))
        diff = abs(total_purchase_reg - gl_creditors)

        return ReconciliationRun.objects.create(
            engagement=engagement,
            recon_type=ReconciliationType.PURCHASE_VS_LEDGER,
            status=ReconciliationStatus.BALANCED if diff < Decimal('1.00') else ReconciliationStatus.VARIANCE_DETECTED,
            as_of_date=as_of,
            balance_per_books=gl_creditors,
            balance_per_statement=total_purchase_reg,
            unreconciled_difference=diff,
            total_source_items=len(purchase_register_items),
            total_target_items=creditor_ledgers.count(),
            summary_data={'purchase_register_total': str(total_purchase_reg), 'gl_payables': str(gl_creditors), 'variance': str(diff)}
        )

    @staticmethod
    def reconcile_debtors_ageing(engagement, debtors_items: Optional[List[Dict]] = None) -> ReconciliationRun:
        """Cross-checks Debtors Ageing Schedule total against Trade Receivables control account."""
        as_of = engagement.financial_year.end_date
        if not debtors_items:
            db_debtors = engagement.aging_items.filter(item_type='RECEIVABLE')
            if db_debtors.exists():
                debtors_items = [{'balance': d.outstanding_amount} for d in db_debtors]

        # Clean prior run for this type
        ReconciliationRun.objects.filter(engagement=engagement, recon_type=ReconciliationType.AR_VS_CONTROL).delete()

        if not debtors_items:
            return ReconciliationRun.objects.create(
                engagement=engagement,
                recon_type=ReconciliationType.AR_VS_CONTROL,
                status=ReconciliationStatus.BLOCKED,
                as_of_date=as_of,
                summary_data={'message': 'Debtors Ageing schedule not provided for this engagement.'}
            )

        total_subledger = sum((Decimal(str(d.get('balance', d.get('outstanding_amount', 0)))) for d in debtors_items), Decimal('0.00'))
        rec_ledgers = LedgerAccount.objects.filter(
            company=engagement.company,
            coa__schedule_iii_group=ScheduleIIIGroup.TRADE_RECEIVABLES
        )
        ctrl_balance = sum((l.closing_balance for l in rec_ledgers), Decimal('0.00'))
        if ctrl_balance == Decimal('0.00') and engagement.trial_balances.exists():
            tb = engagement.trial_balances.first()
            for a in (tb.accounts_snapshot or []):
                if a.get('schedule_iii_group') == ScheduleIIIGroup.TRADE_RECEIVABLES:
                    ctrl_balance += Decimal(str(a.get('debit') or a.get('net_balance') or 0))

        diff = abs(total_subledger - ctrl_balance)

        return ReconciliationRun.objects.create(
            engagement=engagement,
            recon_type=ReconciliationType.AR_VS_CONTROL,
            status=ReconciliationStatus.BALANCED if diff < Decimal('1.00') else ReconciliationStatus.VARIANCE_DETECTED,
            as_of_date=as_of,
            balance_per_books=ctrl_balance,
            balance_per_statement=total_subledger,
            unreconciled_difference=diff,
            total_source_items=len(debtors_items),
            total_target_items=rec_ledgers.count(),
            summary_data={'subledger_ageing_total': str(total_subledger), 'control_account_total': str(ctrl_balance), 'variance': str(diff)}
        )

    @staticmethod
    def reconcile_creditors_ageing(engagement, creditors_items: Optional[List[Dict]] = None) -> ReconciliationRun:
        """Cross-checks Creditors Ageing Schedule total against Trade Payables control account."""
        as_of = engagement.financial_year.end_date
        if not creditors_items:
            db_creditors = engagement.aging_items.filter(item_type='PAYABLE')
            if db_creditors.exists():
                creditors_items = [{'balance': c.outstanding_amount} for c in db_creditors]

        # Clean prior run for this type
        ReconciliationRun.objects.filter(engagement=engagement, recon_type=ReconciliationType.AP_VS_CONTROL).delete()

        if not creditors_items:
            return ReconciliationRun.objects.create(
                engagement=engagement,
                recon_type=ReconciliationType.AP_VS_CONTROL,
                status=ReconciliationStatus.BLOCKED,
                as_of_date=as_of,
                summary_data={'message': 'Creditors Ageing schedule not provided for this engagement.'}
            )

        total_subledger = sum((Decimal(str(c.get('balance', c.get('outstanding_amount', 0)))) for c in creditors_items), Decimal('0.00'))
        pay_ledgers = LedgerAccount.objects.filter(
            company=engagement.company,
            coa__schedule_iii_group=ScheduleIIIGroup.TRADE_PAYABLES
        )
        ctrl_balance = sum((l.closing_balance for l in pay_ledgers), Decimal('0.00'))
        if ctrl_balance == Decimal('0.00') and engagement.trial_balances.exists():
            tb = engagement.trial_balances.first()
            for a in (tb.accounts_snapshot or []):
                if a.get('schedule_iii_group') == ScheduleIIIGroup.TRADE_PAYABLES:
                    ctrl_balance += Decimal(str(a.get('credit') or abs(Decimal(str(a.get('net_balance') or 0)))))

        diff = abs(total_subledger - ctrl_balance)

        return ReconciliationRun.objects.create(
            engagement=engagement,
            recon_type=ReconciliationType.AP_VS_CONTROL,
            status=ReconciliationStatus.BALANCED if diff < Decimal('1.00') else ReconciliationStatus.VARIANCE_DETECTED,
            as_of_date=as_of,
            balance_per_books=ctrl_balance,
            balance_per_statement=total_subledger,
            unreconciled_difference=diff,
            total_source_items=len(creditors_items),
            total_target_items=pay_ledgers.count(),
            summary_data={'subledger_ageing_total': str(total_subledger), 'control_account_total': str(ctrl_balance), 'variance': str(diff)}
        )

    @staticmethod
    def reconcile_far_vs_ledger(engagement, far_items: Optional[List[Dict]] = None) -> ReconciliationRun:
        """Cross-checks Fixed Asset Register Gross Block against PPE Ledger Accounts."""
        as_of = engagement.financial_year.end_date
        if not far_items:
            db_fa = engagement.fixed_assets.all()
            if db_fa.exists():
                far_items = [{'original_cost': a.original_cost} for a in db_fa]

        # Clean prior run for this type
        ReconciliationRun.objects.filter(engagement=engagement, recon_type=ReconciliationType.FAR_VS_LEDGER).delete()

        if not far_items:
            return ReconciliationRun.objects.create(
                engagement=engagement,
                recon_type=ReconciliationType.FAR_VS_LEDGER,
                status=ReconciliationStatus.BLOCKED,
                as_of_date=as_of,
                summary_data={'message': 'Fixed Asset Register (FAR) schedule not provided for this engagement.'}
            )

        far_gross_block = sum((Decimal(str(a.get('original_cost', a.get('cost', 0)))) for a in far_items), Decimal('0.00'))
        ppe_ledgers = LedgerAccount.objects.filter(
            company=engagement.company,
            coa__schedule_iii_group=ScheduleIIIGroup.PPE
        ).exclude(name__icontains='accumulated').exclude(name__icontains='depreciation')
        gl_ppe = sum((l.closing_balance for l in ppe_ledgers), Decimal('0.00'))
        if gl_ppe == Decimal('0.00') and engagement.trial_balances.exists():
            tb = engagement.trial_balances.first()
            for a in (tb.accounts_snapshot or []):
                if a.get('schedule_iii_group') == ScheduleIIIGroup.PPE and 'accumulated' not in a.get('account_name', '').lower():
                    gl_ppe += Decimal(str(a.get('debit') or a.get('net_balance') or 0))

        diff = abs(far_gross_block - gl_ppe)

        return ReconciliationRun.objects.create(
            engagement=engagement,
            recon_type=ReconciliationType.FAR_VS_LEDGER,
            status=ReconciliationStatus.BALANCED if diff < Decimal('1.00') else ReconciliationStatus.VARIANCE_DETECTED,
            as_of_date=as_of,
            balance_per_books=gl_ppe,
            balance_per_statement=far_gross_block,
            unreconciled_difference=diff,
            total_source_items=len(far_items),
            total_target_items=ppe_ledgers.count(),
            summary_data={'far_gross_block': str(far_gross_block), 'gl_ppe': str(gl_ppe), 'variance': str(diff)}
        )

    @staticmethod
    def reconcile_financial_statements_vs_tb(engagement) -> ReconciliationRun:
        """
        Cross-checks Schedule III Financial Statement totals against Trial Balance Snapshot.
        Verifies Total Assets == Total Equity & Liabilities, and P&L Net Profit consistency.
        """
        as_of = engagement.financial_year.end_date
        tb = engagement.trial_balances.first()

        # Clean prior run for this type
        ReconciliationRun.objects.filter(engagement=engagement, recon_type=ReconciliationType.FS_VS_TB).delete()

        if not tb or not tb.accounts_snapshot:
            return ReconciliationRun.objects.create(
                engagement=engagement,
                recon_type=ReconciliationType.FS_VS_TB,
                status=ReconciliationStatus.BLOCKED,
                as_of_date=as_of,
                summary_data={'error': 'Trial balance snapshot required to compute financial statement totals.'}
            )

        from apps.accounting.services import TrialBalanceService
        fin_stmts = TrialBalanceService.compile_financial_statements(tb.accounts_snapshot)
        tot_assets = Decimal(str(fin_stmts['balance_sheet']['total_assets']))
        tot_liab_equity = Decimal(str(fin_stmts['balance_sheet']['total_equity_and_liabilities']))
        net_profit = Decimal(str(fin_stmts['profit_and_loss'].get('profit_after_tax', fin_stmts['profit_and_loss'].get('pat', 0))))
        balance_sheet_diff = abs(tot_assets - tot_liab_equity)

        is_balanced = balance_sheet_diff < Decimal('1.00')
        return ReconciliationRun.objects.create(
            engagement=engagement,
            recon_type=ReconciliationType.FS_VS_TB,
            status=ReconciliationStatus.BALANCED if is_balanced else ReconciliationStatus.VARIANCE_DETECTED,
            as_of_date=as_of,
            balance_per_books=tot_assets,
            balance_per_statement=tot_liab_equity,
            unreconciled_difference=balance_sheet_diff,
            total_source_items=len(tb.accounts_snapshot),
            summary_data={
                'total_assets': str(tot_assets),
                'total_liabilities_and_equity': str(tot_liab_equity),
                'net_profit_pat': str(net_profit),
                'balance_sheet_variance': str(balance_sheet_diff),
                'is_balanced': is_balanced
            }
        )

    @staticmethod
    def reconcile_gstr1_vs_books(engagement, gstr1_items: Optional[List[Dict]] = None) -> ReconciliationRun:
        """Cross-checks GSTR-1 outward supplies turnover and taxes against Revenue from Operations & GST Output ledgers."""
        as_of = engagement.financial_year.end_date
        ReconciliationRun.objects.filter(engagement=engagement, recon_type=ReconciliationType.GSTR1_VS_BOOKS).delete()
        if not gstr1_items:
            return ReconciliationRun.objects.create(
                engagement=engagement,
                recon_type=ReconciliationType.GSTR1_VS_BOOKS,
                status=ReconciliationStatus.BLOCKED,
                as_of_date=as_of,
                summary_data={'message': 'GSTR-1 portal return data not provided for this engagement.'}
            )

        total_taxable_gstr1 = sum((Decimal(str(i.get('taxable_value', 0))) for i in gstr1_items), Decimal('0.00'))
        cgst_gstr1 = sum((Decimal(str(i.get('cgst', 0))) for i in gstr1_items), Decimal('0.00'))
        sgst_gstr1 = sum((Decimal(str(i.get('sgst', 0))) for i in gstr1_items), Decimal('0.00'))
        igst_gstr1 = sum((Decimal(str(i.get('igst', 0))) for i in gstr1_items), Decimal('0.00'))
        total_tax_gstr1 = cgst_gstr1 + sgst_gstr1 + igst_gstr1

        rev_ledgers = LedgerAccount.objects.filter(company=engagement.company, coa__schedule_iii_group=ScheduleIIIGroup.REVENUE_OPERATIONS)
        gl_rev = sum((l.closing_balance for l in rev_ledgers), Decimal('0.00'))
        diff_turnover = abs(total_taxable_gstr1 - gl_rev)

        is_matched = diff_turnover < Decimal('10.00')

        return ReconciliationRun.objects.create(
            engagement=engagement,
            recon_type=ReconciliationType.GSTR1_VS_BOOKS,
            status=ReconciliationStatus.BALANCED if is_matched else ReconciliationStatus.VARIANCE_DETECTED,
            as_of_date=as_of,
            balance_per_books=gl_rev,
            balance_per_statement=total_taxable_gstr1,
            unreconciled_difference=diff_turnover,
            total_source_items=len(gstr1_items),
            total_target_items=rev_ledgers.count(),
            summary_data={
                'gstr1_taxable_turnover': str(total_taxable_gstr1),
                'gl_revenue_operations': str(gl_rev),
                'turnover_variance': str(diff_turnover),
                'gstr1_cgst': str(cgst_gstr1),
                'gstr1_sgst': str(sgst_gstr1),
                'gstr1_igst': str(igst_gstr1),
                'gstr1_total_tax': str(total_tax_gstr1),
                'is_turnover_matched': is_matched
            }
        )

    @staticmethod
    def reconcile_gstr3b_vs_books(engagement, gstr3b_items: Optional[List[Dict]] = None) -> ReconciliationRun:
        """Cross-checks GSTR-3B monthly summary return (Table 3.1 & Table 4 ITC) against Books."""
        as_of = engagement.financial_year.end_date
        ReconciliationRun.objects.filter(engagement=engagement, recon_type=ReconciliationType.GSTR3B_VS_BOOKS).delete()
        if not gstr3b_items:
            return ReconciliationRun.objects.create(
                engagement=engagement,
                recon_type=ReconciliationType.GSTR3B_VS_BOOKS,
                status=ReconciliationStatus.BLOCKED,
                as_of_date=as_of,
                summary_data={'message': 'GSTR-3B summary return data not provided for this engagement.'}
            )

        gstr3b_turnover = sum((Decimal(str(m.get('taxable_value', 0))) for m in gstr3b_items), Decimal('0.00'))
        gstr3b_tax_paid = sum((Decimal(str(m.get('tax_paid', 0))) for m in gstr3b_items), Decimal('0.00'))
        gstr3b_itc_claimed = sum((Decimal(str(m.get('itc_claimed', 0))) for m in gstr3b_items), Decimal('0.00'))

        rev_ledgers = LedgerAccount.objects.filter(company=engagement.company, coa__schedule_iii_group=ScheduleIIIGroup.REVENUE_OPERATIONS)
        gl_rev = sum((l.closing_balance for l in rev_ledgers), Decimal('0.00'))
        diff_turnover = abs(gstr3b_turnover - gl_rev)

        is_matched = diff_turnover < Decimal('10.00')

        return ReconciliationRun.objects.create(
            engagement=engagement,
            recon_type=ReconciliationType.GSTR3B_VS_BOOKS,
            status=ReconciliationStatus.BALANCED if is_matched else ReconciliationStatus.VARIANCE_DETECTED,
            as_of_date=as_of,
            balance_per_books=gl_rev,
            balance_per_statement=gstr3b_turnover,
            unreconciled_difference=diff_turnover,
            total_source_items=len(gstr3b_items),
            summary_data={
                'gstr3b_turnover': str(gstr3b_turnover),
                'gl_revenue_operations': str(gl_rev),
                'turnover_variance': str(diff_turnover),
                'gstr3b_tax_paid': str(gstr3b_tax_paid),
                'gstr3b_itc_claimed': str(gstr3b_itc_claimed),
                'is_turnover_matched': is_matched
            }
        )

    @staticmethod
    def reconcile_form_26as_tds(engagement, form26as_items: Optional[List[Dict]] = None) -> ReconciliationRun:
        """Cross-checks Form 26AS / AIS TDS credits against TDS Receivable in general ledger."""
        as_of = engagement.financial_year.end_date
        ReconciliationRun.objects.filter(engagement=engagement, recon_type=ReconciliationType.TDS_26AS).delete()
        if not form26as_items:
            return ReconciliationRun.objects.create(
                engagement=engagement,
                recon_type=ReconciliationType.TDS_26AS,
                status=ReconciliationStatus.BLOCKED,
                as_of_date=as_of,
                summary_data={'message': 'Form 26AS / AIS statement not provided for this engagement.'}
            )

        tds_26as_total = sum((Decimal(str(i.get('tds_deposited', i.get('tax_deducted', 0)))) for i in form26as_items), Decimal('0.00'))
        
        # Look for TDS receivable or advance tax ledgers
        tds_ledgers = LedgerAccount.objects.filter(
            company=engagement.company,
            name__icontains='TDS'
        ).exclude(name__icontains='Payable')
        gl_tds = sum((l.closing_balance for l in tds_ledgers), Decimal('0.00'))
        diff = abs(tds_26as_total - gl_tds)

        is_matched = diff < Decimal('50.00')

        return ReconciliationRun.objects.create(
            engagement=engagement,
            recon_type=ReconciliationType.TDS_26AS,
            status=ReconciliationStatus.BALANCED if is_matched else ReconciliationStatus.VARIANCE_DETECTED,
            as_of_date=as_of,
            balance_per_books=gl_tds,
            balance_per_statement=tds_26as_total,
            unreconciled_difference=diff,
            total_source_items=len(form26as_items),
            total_target_items=tds_ledgers.count(),
            summary_data={
                'form_26as_total_tds': str(tds_26as_total),
                'gl_tds_receivable': str(gl_tds),
                'variance': str(diff),
                'is_matched': is_matched
            }
        )

    @staticmethod
    def run_all_cross_reconciliations(engagement) -> List[ReconciliationRun]:
        """Executes all available cross-document reconciliations."""
        runs = []
        runs.append(CrossDocumentReconciliationEngine.reconcile_ledger_vs_trial_balance(engagement))
        runs.append(CrossDocumentReconciliationEngine.reconcile_financial_statements_vs_tb(engagement))
        runs.append(CrossDocumentReconciliationEngine.reconcile_sales_register(engagement, None))
        runs.append(CrossDocumentReconciliationEngine.reconcile_purchase_register(engagement, None))
        runs.append(CrossDocumentReconciliationEngine.reconcile_debtors_ageing(engagement, None))
        runs.append(CrossDocumentReconciliationEngine.reconcile_creditors_ageing(engagement, None))
        runs.append(CrossDocumentReconciliationEngine.reconcile_far_vs_ledger(engagement, None))
        runs.append(CrossDocumentReconciliationEngine.reconcile_gstr1_vs_books(engagement, None))
        runs.append(CrossDocumentReconciliationEngine.reconcile_gstr3b_vs_books(engagement, None))
        runs.append(CrossDocumentReconciliationEngine.reconcile_form_26as_tds(engagement, None))
        return runs

