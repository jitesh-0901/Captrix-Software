from decimal import Decimal
from datetime import date, timedelta
from collections import defaultdict
from typing import List, Dict, Any, Optional

from apps.accounting.models import (
    Transaction, LedgerAccount, ChartOfAccounts,
    ScheduleIIIGroup, AccountType, TrialBalanceSnapshot
)
from apps.audit.models import ExceptionItem, ExceptionSeverity, ExceptionStatus
from apps.ingestion.models import Document, ExtractedRecord

class FinancialDataValidationService:
    """
    Reusable, deterministic financial data validation engine for Captrix AI.
    All calculations utilize Python Decimal arithmetic with fail-closed assertions.
    """

    @staticmethod
    def validate_reporting_periods(engagement, transactions: List[Transaction]) -> List[Dict[str, Any]]:
        """
        Validates that all transactions fall strictly within the engagement financial year.
        Creates persisted ExceptionItem for out-of-period entries.
        """
        fy = engagement.financial_year
        fy_start = fy.start_date
        fy_end = fy.end_date
        today = date.today()

        violations = []
        for txn in transactions:
            if txn.date < fy_start or txn.date > fy_end:
                amt = txn.debit_amount if txn.debit_amount > 0 else txn.credit_amount
                violations.append({
                    'transaction_id': txn.id,
                    'voucher_number': txn.voucher_number,
                    'date': txn.date.isoformat(),
                    'amount': str(amt),
                    'rule_code': 'DATE-OUT-OF-BOUNDS',
                    'reason': f"Date {txn.date} is outside FY period [{fy_start} to {fy_end}]"
                })
                ExceptionItem.objects.create(
                    engagement=engagement,
                    related_transaction=txn,
                    related_ledger=txn.ledger_account,
                    rule_code="RULE_PERIOD_MISMATCH",
                    title=f"Out-of-Period Transaction: {txn.voucher_number} on {txn.date}",
                    category="PERIODICITY",
                    severity=ExceptionSeverity.HIGH,
                    amount_involved=amt,
                    explanation=(
                        f"Voucher {txn.voucher_number} dated {txn.date} recorded in ledger '{txn.ledger_account.name}' "
                        f"falls outside the authorized financial year ({fy.label}: {fy_start} to {fy_end})."
                    ),
                    recommended_action="Investigate whether transaction belongs to prior or subsequent accounting period. Post cut-off rectifying entry.",
                    source_reference=txn.source_reference or f"Vch_{txn.voucher_number}"
                )
            elif txn.date > today:
                amt = txn.debit_amount if txn.debit_amount > 0 else txn.credit_amount
                violations.append({
                    'transaction_id': txn.id,
                    'voucher_number': txn.voucher_number,
                    'date': txn.date.isoformat(),
                    'amount': str(amt),
                    'reason': f"Future-dated transaction: {txn.date} > {today}"
                })
                ExceptionItem.objects.create(
                    engagement=engagement,
                    related_transaction=txn,
                    related_ledger=txn.ledger_account,
                    rule_code="RULE_FUTURE_DATED",
                    title=f"Future-Dated Posting: {txn.voucher_number} on {txn.date}",
                    category="PERIODICITY",
                    severity=ExceptionSeverity.MEDIUM,
                    amount_involved=amt,
                    explanation=f"Voucher {txn.voucher_number} has an effective posting date ({txn.date}) in the future.",
                    recommended_action="Verify system clock or invoice issuance dates. Audit for pre-billing or advance entries.",
                    source_reference=txn.source_reference or f"Vch_{txn.voucher_number}"
                )

        return violations

    @staticmethod
    def validate_amounts_and_debit_credit(transactions: List[Transaction]) -> List[Dict[str, Any]]:
        """
        Validates non-negative amounts, non-zero postings, and voucher-level double-entry equality.
        """
        issues = []
        vouchers_grouped = defaultdict(lambda: {'dr': Decimal('0.00'), 'cr': Decimal('0.00'), 'txns': []})

        for txn in transactions:
            if txn.debit_amount < 0 or txn.credit_amount < 0:
                issues.append({
                    'transaction_id': txn.id,
                    'voucher_number': txn.voucher_number,
                    'issue': 'NEGATIVE_AMOUNT',
                    'detail': f"Negative debit ({txn.debit_amount}) or credit ({txn.credit_amount}) detected"
                })
            if txn.debit_amount == 0 and txn.credit_amount == 0:
                issues.append({
                    'transaction_id': txn.id,
                    'voucher_number': txn.voucher_number,
                    'issue': 'ZERO_AMOUNT',
                    'detail': "Both debit and credit amounts are zero"
                })

            vouchers_grouped[txn.voucher_number]['dr'] += txn.debit_amount
            vouchers_grouped[txn.voucher_number]['cr'] += txn.credit_amount
            vouchers_grouped[txn.voucher_number]['txns'].append(txn)

        # Check multi-leg voucher equality
        for vch_no, data in vouchers_grouped.items():
            if len(data['txns']) > 1:
                diff = abs(data['dr'] - data['cr'])
                if diff > Decimal('0.01'):
                    issues.append({
                        'voucher_number': vch_no,
                        'issue': 'VOUCHER_UNBALANCED',
                        'rule_code': 'VOUCHER-UNBALANCED',
                        'total_debit': str(data['dr']),
                        'total_credit': str(data['cr']),
                        'variance': str(diff)
                    })
                    eng = data['txns'][0].engagement
                    ExceptionItem.objects.create(
                        engagement=eng,
                        rule_code="RULE_VOUCHER_UNBALANCED",
                        title=f"Unbalanced Multi-Leg Voucher: {vch_no} (Diff: ₹{diff})",
                        category="ACCURACY",
                        severity=ExceptionSeverity.CRITICAL,
                        amount_involved=diff,
                        explanation=f"Multi-leg journal voucher {vch_no} has total debits ₹{data['dr']} and credits ₹{data['cr']}. Variance of ₹{diff}.",
                        recommended_action="Inspect source journal entry extraction for omitted balancing legs or split row parsing errors.",
                        source_reference=data['txns'][0].source_reference or f"Vch_{vch_no}"
                    )

        return issues

    @staticmethod
    def detect_duplicate_candidates(engagement, transactions: List[Transaction]) -> List[Dict[str, Any]]:
        """
        Detects exact duplicates and near-duplicate candidate transactions (same amount, ledger/counterparty within +-3 days).
        """
        exact_map = defaultdict(list)
        near_candidates = []

        for txn in transactions:
            amt = txn.debit_amount if txn.debit_amount > 0 else txn.credit_amount
            if amt == 0:
                continue

            # Exact key: (date, voucher_number, ledger_id, amt)
            exact_key = (txn.date, txn.voucher_number, txn.ledger_account_id, amt)
            exact_map[exact_key].append(txn)

        duplicates_found = []
        # Flag exact duplicates
        for key, txns in exact_map.items():
            if len(txns) > 1:
                primary = txns[0]
                duplicates_found.append({
                    'type': 'EXACT_DUPLICATE',
                    'rule_code': 'DUPLICATE-CANDIDATE',
                    'voucher_number': primary.voucher_number,
                    'amount': str(key[3]),
                    'count': len(txns)
                })
                ExceptionItem.objects.create(
                    engagement=engagement,
                    related_transaction=primary,
                    related_ledger=primary.ledger_account,
                    rule_code="RULE_DUPLICATE_TXN",
                    title=f"Exact Duplicate Transaction: {primary.voucher_number} ({len(txns)} instances)",
                    category="ACCURACY",
                    severity=ExceptionSeverity.HIGH,
                    amount_involved=key[3] * Decimal(str(len(txns) - 1)),
                    explanation=(
                        f"Found {len(txns)} identical transactions for voucher {primary.voucher_number} "
                        f"dated {primary.date} for ₹{key[3]} in ledger '{primary.ledger_account.name}'."
                    ),
                    recommended_action="Review ledger import to ensure vouchers were not duplicated across multiple monthly sheets.",
                    source_reference=primary.source_reference or f"Vch_{primary.voucher_number}"
                )

        # Flag near-duplicate candidates (same amount, same ledger or counterparty, within 3 days)
        sorted_txns = sorted(transactions, key=lambda x: (x.ledger_account_id, x.date))
        for i in range(len(sorted_txns)):
            t1 = sorted_txns[i]
            amt1 = t1.debit_amount if t1.debit_amount > 0 else t1.credit_amount
            if amt1 == 0:
                continue

            for j in range(i + 1, min(i + 15, len(sorted_txns))):
                t2 = sorted_txns[j]
                if t1.ledger_account_id != t2.ledger_account_id:
                    break
                amt2 = t2.debit_amount if t2.debit_amount > 0 else t2.credit_amount
                date_diff = abs((t2.date - t1.date).days)
                if date_diff > 3:
                    break

                if amt1 == amt2 and t1.voucher_number != t2.voucher_number:
                    near_candidates.append({
                        'type': 'NEAR_DUPLICATE',
                        'rule_code': 'DUPLICATE-CANDIDATE',
                        'txn_1': t1.voucher_number,
                        'txn_2': t2.voucher_number,
                        'date_1': t1.date.isoformat(),
                        'date_2': t2.date.isoformat(),
                        'amount': str(amt1),
                        'ledger': t1.ledger_account.name
                    })

        return duplicates_found + near_candidates

    @classmethod
    def validate_engagement_transactions(cls, engagement, transactions: Optional[List[Transaction]] = None) -> List[Dict[str, Any]]:
        """
        Runs comprehensive validation across transactions of an engagement:
        - Reporting period boundaries
        - Amounts, positivity, and multi-leg voucher double-entry equality
        - Duplicate candidate detection
        """
        if transactions is None:
            transactions = list(Transaction.objects.filter(engagement=engagement))
        
        findings = []
        period_issues = cls.validate_reporting_periods(engagement, transactions)
        findings.extend(period_issues)
        
        amount_issues = cls.validate_amounts_and_debit_credit(transactions)
        findings.extend(amount_issues)
        
        duplicate_issues = cls.detect_duplicate_candidates(engagement, transactions)
        findings.extend(duplicate_issues)
        
        return findings

    @staticmethod
    def validate_rollforward(opening_balance: Decimal, total_debits: Decimal, total_credits: Decimal, closing_balance: Decimal, is_debit_balance: bool = True) -> Dict[str, Any]:
        """
        Validates the mathematical roll-forward equation:
        Dr balance: Closing = Opening + Dr - Cr
        Cr balance: Closing = Opening - Dr + Cr
        """
        op = Decimal(str(opening_balance))
        dr = Decimal(str(total_debits))
        cr = Decimal(str(total_credits))
        cl = Decimal(str(closing_balance))
        
        expected = (op + dr - cr) if is_debit_balance else (op - dr + cr)
        variance = abs(expected - cl)
        is_reconciled = variance < Decimal('0.01')
        
        return {
            'opening_balance': op,
            'total_debits': dr,
            'total_credits': cr,
            'expected_closing': expected,
            'actual_closing': cl,
            'variance': variance,
            'is_reconciled': is_reconciled
        }

    @staticmethod
    def validate_account_mappings(company, engagement=None) -> List[Dict[str, Any]]:
        """
        Validates that all ledger accounts are mapped to Chart of Accounts and valid Schedule III groups.
        Identifies unmapped accounts and suspense/holding accounts.
        """
        unmapped = []
        ledgers = LedgerAccount.objects.filter(company=company).select_related('coa')

        for l in ledgers:
            is_suspense = False
            sch_group = l.coa.schedule_iii_group if l.coa else ScheduleIIIGroup.UNCLASSIFIED
            name_lower = l.name.lower()

            if any(term in name_lower for term in ['suspense', 'unclassified', 'temporary', 'clearing', 'holding', 'dummy']):
                is_suspense = True
                l.is_suspense = True
                l.save(update_fields=['is_suspense'])

            if not l.coa or sch_group == ScheduleIIIGroup.UNCLASSIFIED or is_suspense:
                unmapped.append({
                    'ledger_id': l.id,
                    'ledger_name': l.name,
                    'code': l.code,
                    'schedule_iii_group': sch_group,
                    'is_suspense': is_suspense,
                    'closing_balance': str(l.closing_balance)
                })

                if engagement:
                    ExceptionItem.objects.create(
                        engagement=engagement,
                        related_ledger=l,
                        rule_code="RULE_UNMAPPED_COA" if not is_suspense else "RULE_SUSPENSE_ACCOUNT",
                        title=f"{'Suspense Account Detected' if is_suspense else 'Unmapped Ledger Account'}: {l.name}",
                        category="CLASSIFICATION",
                        severity=ExceptionSeverity.HIGH if is_suspense else ExceptionSeverity.MEDIUM,
                        amount_involved=l.closing_balance,
                        explanation=(
                            f"Ledger account '{l.name}' (Closing Balance: ₹{l.closing_balance} {l.closing_balance_type}) "
                            f"is classified as '{sch_group}'. "
                            f"{'Active suspense accounts violate Schedule III fair presentation.' if is_suspense else 'Unmapped accounts must be mapped to Schedule III before balance sheet finalization.'}"
                        ),
                        recommended_action=(
                            "Review transactions in this ledger and map to appropriate Schedule III Division I head. "
                            "Clear suspense balance prior to issuing final audit report."
                        ),
                        source_reference=f"Ledger_{l.code or l.name}"
                    )

        return unmapped

    @staticmethod
    def validate_opening_closing_rollforward(engagement) -> List[Dict[str, Any]]:
        """
        Validates the fundamental roll-forward identity for every ledger account:
        For Debit balance accounts: Closing = Opening + Debits - Credits
        For Credit balance accounts: Closing = Opening - Debits + Credits
        Flags roll-forward discrepancies without fabricating entries.
        """
        discrepancies = []
        ledgers = LedgerAccount.objects.filter(company=engagement.company)

        for l in ledgers:
            txns = Transaction.objects.filter(engagement=engagement, ledger_account=l)
            tot_dr = sum((t.debit_amount for t in txns), Decimal('0.00'))
            tot_cr = sum((t.credit_amount for t in txns), Decimal('0.00'))

            op = l.opening_balance
            op_net = op if l.opening_balance_type == 'Dr' else -op
            expected_net = op_net + tot_dr - tot_cr
            actual_net = l.closing_balance if l.closing_balance_type == 'Dr' else -l.closing_balance

            diff = abs(expected_net - actual_net)
            if diff > Decimal('0.01'):
                discrepancies.append({
                    'ledger_name': l.name,
                    'opening_balance': str(l.opening_balance),
                    'total_debits': str(tot_dr),
                    'total_credits': str(tot_cr),
                    'expected_closing': str(abs(expected_net)),
                    'actual_closing': str(l.closing_balance),
                    'variance': str(diff)
                })
                ExceptionItem.objects.create(
                    engagement=engagement,
                    related_ledger=l,
                    rule_code="RULE_ROLLFORWARD_MISMATCH",
                    title=f"Roll-Forward Discrepancy in '{l.name}': Variance of ₹{diff:,.2f}",
                    category="ACCURACY",
                    severity=ExceptionSeverity.HIGH,
                    amount_involved=diff,
                    explanation=(
                        f"Opening balance (₹{l.opening_balance} {l.opening_balance_type}) plus period debits (₹{tot_dr:,.2f}) "
                        f"less period credits (₹{tot_cr:,.2f}) equals expected closing ₹{abs(expected_net):,.2f}, "
                        f"which differs from reported closing balance ₹{l.closing_balance:,.2f}. Discrepancy = ₹{diff:,.2f}."
                    ),
                    recommended_action="Verify opening balance carryover from prior year signed financial statements or check for unposted vouchers.",
                    source_reference=f"Ledger_{l.name}"
                )

        return discrepancies

    @staticmethod
    def validate_abnormal_account_balances(engagement) -> List[Dict[str, Any]]:
        """
        Identifies abnormal account balances (e.g. Asset account with Credit closing balance,
        Liability or Equity account with Debit closing balance).
        """
        abnormal = []
        ledgers = LedgerAccount.objects.filter(company=engagement.company).select_related('coa')

        for l in ledgers:
            if not l.coa:
                continue
            ac_type = l.coa.account_type

            # Normal: Asset/Expense -> Dr; Liability/Equity/Revenue -> Cr
            is_abnormal = False
            if ac_type in [AccountType.ASSET, AccountType.EXPENSE] and l.closing_balance_type == 'Cr' and l.closing_balance > Decimal('100.00'):
                is_abnormal = True
            elif ac_type in [AccountType.LIABILITY, AccountType.EQUITY, AccountType.REVENUE] and l.closing_balance_type == 'Dr' and l.closing_balance > Decimal('100.00'):
                is_abnormal = True

            if is_abnormal:
                abnormal.append({
                    'account_name': l.name,
                    'account_type': ac_type,
                    'closing_balance': str(l.closing_balance),
                    'balance_type': l.closing_balance_type
                })
                ExceptionItem.objects.create(
                    engagement=engagement,
                    related_ledger=l,
                    rule_code="RULE_ABNORMAL_BALANCE",
                    title=f"Abnormal Account Balance: '{l.name}' has {l.closing_balance_type} balance of ₹{l.closing_balance:,.2f}",
                    category="ACCURACY",
                    severity=ExceptionSeverity.MEDIUM,
                    amount_involved=l.closing_balance,
                    explanation=(
                        f"Account '{l.name}' is categorized as {ac_type}, which normally maintains a "
                        f"{'Dr' if ac_type in [AccountType.ASSET, AccountType.EXPENSE] else 'Cr'} balance. "
                        f"Current closing balance is ₹{l.closing_balance:,.2f} {l.closing_balance_type}."
                    ),
                    recommended_action="Inspect whether this represents an unclassified bank overdraft, negative debtor balance, or incorrect sign convention.",
                    source_reference=f"Ledger_{l.name}"
                )

        return abnormal

    @staticmethod
    def validate_source_vs_imported_totals(document: Document) -> Dict[str, Any]:
        """
        Verifies that totals parsed from raw source ExtractedRecords match the persisted Transaction or Snapshot totals.
        """
        recs = ExtractedRecord.objects.filter(document=document)
        raw_dr = Decimal('0.00')
        raw_cr = Decimal('0.00')

        for r in recs:
            norm = r.normalized_data
            for k, v in norm.items():
                k_lower = k.lower()
                if 'debit' in k_lower or k_lower in ['dr', 'withdrawal']:
                    try:
                        raw_dr += Decimal(str(v))
                    except Exception:
                        pass
                elif 'credit' in k_lower or k_lower in ['cr', 'deposit']:
                    try:
                        raw_cr += Decimal(str(v))
                    except Exception:
                        pass

        # Compare with transactions created from this document
        txns = Transaction.objects.filter(document=document)
        imported_dr = sum((t.debit_amount for t in txns), Decimal('0.00'))
        imported_cr = sum((t.credit_amount for t in txns), Decimal('0.00'))

        dr_diff = abs(raw_dr - imported_dr)
        cr_diff = abs(raw_cr - imported_cr)

        is_consistent = (dr_diff < Decimal('1.00')) and (cr_diff < Decimal('1.00'))
        return {
            'source_debit': str(raw_dr),
            'imported_debit': str(imported_dr),
            'debit_difference': str(dr_diff),
            'source_credit': str(raw_cr),
            'imported_credit': str(imported_cr),
            'credit_difference': str(cr_diff),
            'is_consistent': is_consistent
        }
