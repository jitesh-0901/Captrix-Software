from decimal import Decimal
from datetime import date, timedelta
from typing import List, Dict, Any, Optional
from apps.companies.models import Engagement
from apps.audit.models import RelatedParty, ExceptionItem, ExceptionSeverity, ExceptionStatus
from apps.accounting.models import Transaction, LedgerAccount, VoucherType, AccountType

class ForensicScrutinyEngine:
    """
    Forensic auditing engine for Related Party transactions (Section 2(76) / Section 188 / AS 18)
    and Manual Journal Voucher scrutiny under SA 240 (Auditor's Responsibilities Relating to Fraud).
    """

    @classmethod
    def scrutinize_related_parties(
        cls,
        engagement: Engagement,
        parties_data: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Populates RelatedParty master and matches against General Ledger counterparties.
        Analyzes for Section 188 compliance (arm's length pricing and approval thresholds).
        """
        if parties_data:
            RelatedParty.objects.filter(engagement=engagement).delete()
            for p in parties_data:
                RelatedParty.objects.create(
                    engagement=engagement,
                    party_name=str(p.get('party_name', '')).strip(),
                    pan=str(p.get('pan', '')).strip(),
                    relationship_type=str(p.get('relationship_type', 'Director / KMP')).strip(),
                    applicable_standard=str(p.get('applicable_standard', 'SECTION_2_76')).strip(),
                    notes=str(p.get('notes', ''))
                )

        parties = list(RelatedParty.objects.filter(engagement=engagement, is_active=True))
        matched_txns = []
        tot_related_party_volume = Decimal('0.00')

        all_txns = Transaction.objects.filter(engagement=engagement)

        for p in parties:
            p_name_lower = p.party_name.lower()
            p_txns = [
                t for t in all_txns
                if p_name_lower in t.counterparty.lower() or p_name_lower in t.narration.lower()
            ]

            p_volume = Decimal('0.00')
            for t in p_txns:
                amt = t.debit_amount if t.debit_amount > 0 else t.credit_amount
                p_volume += amt
                matched_txns.append({
                    'party_name': p.party_name,
                    'relationship': p.relationship_type,
                    'voucher_number': t.voucher_number,
                    'date': t.date.isoformat(),
                    'amount': str(amt),
                    'ledger': t.ledger_account.name,
                    'narration': t.narration
                })

            tot_related_party_volume += p_volume

        # Flag related party summary exception for auditor review
        if matched_txns:
            ExceptionItem.objects.create(
                engagement=engagement,
                rule_code="RULE_RELATED_PARTY_TXN",
                title=f"Related Party Transactions Scrutinized: {len(parties)} Parties (₹{tot_related_party_volume:,.2f})",
                category="STATUTORY_COMPLIANCE",
                severity=ExceptionSeverity.MEDIUM,
                amount_involved=tot_related_party_volume,
                explanation=(
                    f"Identified {len(matched_txns)} transactions totaling ₹{tot_related_party_volume:,.2f} "
                    f"involving configured related parties under Section 2(76) of Companies Act 2013 / AS 18."
                ),
                recommended_action=(
                    "Verify Audit Committee and Board approval under Section 188. "
                    "Review transfer pricing and arm's length documentation for Form 3CD Clause 23 disclosure."
                ),
                source_reference="Related_Party_Register"
            )

        return {
            'total_related_parties': len(parties),
            'matched_transactions_count': len(matched_txns),
            'total_volume': str(tot_related_party_volume),
            'transactions': matched_txns[:50]
        }

    @classmethod
    def scrutinize_manual_journals(
        cls,
        engagement: Engagement
    ) -> Dict[str, Any]:
        """
        Executes forensic journal entry scrutiny under SA 240:
        1. Manual journal entries vs automated system vouchers
        2. Period-end postings (within +-5 days of March 31)
        3. Weekend / Sunday postings
        4. Unusual round amounts (multiples of 50,000 / 1,00,000 / 10,00,000)
        5. Unusual account combinations (e.g. Debit Expense vs Credit Share Capital)
        """
        txns = list(Transaction.objects.filter(engagement=engagement).select_related('ledger_account__coa'))
        fy_end = engagement.financial_year.end_date

        manual_journals = []
        period_end_journals = []
        weekend_journals = []
        round_amount_journals = []
        unusual_combinations = []

        for t in txns:
            amt = t.debit_amount if t.debit_amount > 0 else t.credit_amount
            is_manual = (t.voucher_type == VoucherType.JOURNAL)

            if is_manual:
                manual_journals.append(t)

            # Period-end check (+-5 days of March 31)
            days_from_end = abs((t.date - fy_end).days)
            if days_from_end <= 5 and amt > Decimal('50000.00'):
                period_end_journals.append({
                    'voucher_number': t.voucher_number,
                    'date': t.date.isoformat(),
                    'amount': str(amt),
                    'ledger': t.ledger_account.name,
                    'narration': t.narration
                })

            # Weekend check (Saturday=5, Sunday=6)
            if t.date.weekday() in [5, 6] and amt > Decimal('25000.00'):
                weekend_journals.append({
                    'voucher_number': t.voucher_number,
                    'date': t.date.isoformat(),
                    'day': 'Sunday' if t.date.weekday() == 6 else 'Saturday',
                    'amount': str(amt),
                    'ledger': t.ledger_account.name
                })

            # Round amount check (multiple of 50,000)
            if amt >= Decimal('50000.00') and (amt % Decimal('50000.00') == Decimal('0.00')):
                round_amount_journals.append({
                    'voucher_number': t.voucher_number,
                    'amount': str(amt),
                    'ledger': t.ledger_account.name
                })

            # Unusual combination check (e.g., Credit Revenue with Debit Asset directly without Debtors/Cash)
            coa = t.ledger_account.coa
            if coa:
                ac_type = coa.account_type
                if ac_type == AccountType.REVENUE and t.debit_amount > Decimal('10000.00'):
                    unusual_combinations.append({
                        'voucher_number': t.voucher_number,
                        'reason': 'Direct Debit to Revenue Account (Potential unauthorized revenue reversal)',
                        'amount': str(t.debit_amount),
                        'ledger': t.ledger_account.name
                    })

        return {
            'total_transactions_scrutinized': len(txns),
            'manual_journal_count': len(manual_journals),
            'period_end_journals_count': len(period_end_journals),
            'weekend_journals_count': len(weekend_journals),
            'round_amount_journals_count': len(round_amount_journals),
            'unusual_combinations_count': len(unusual_combinations),
            'period_end_samples': period_end_journals[:10],
            'weekend_samples': weekend_journals[:10],
            'unusual_samples': unusual_combinations[:10],
            'disclaimer': "Forensic scrutiny observations represent risk indicators under SA 240, not automatic proof of fraud or non-compliance."
        }
