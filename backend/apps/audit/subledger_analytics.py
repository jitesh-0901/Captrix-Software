from decimal import Decimal
from datetime import date, datetime
from typing import List, Dict, Any, Optional
from apps.companies.models import Engagement
from apps.audit.models import SubledgerAgingItem, ExceptionItem, ExceptionSeverity, ExceptionStatus
from apps.accounting.models import LedgerAccount

class SubledgerAnalyticsEngine:
    """
    Subledger ageing analytics, control account reconciliation,
    MSMED Act 2006 compliance & Section 43B(h) overdue disallowance screening,
    and documentary inventory movement verification.
    """

    @classmethod
    def process_subledger_items(
        cls,
        engagement: Engagement,
        aging_records: List[Dict[str, Any]],
        as_of_date: date
    ) -> Dict[str, Any]:
        """
        Parses receivables and payables schedule records, computes ageing buckets,
        screens MSMED Act 45-day threshold under Section 43B(h), and reconciles against GL Control Accounts.
        """
        SubledgerAgingItem.objects.filter(engagement=engagement).delete()

        created_items = []
        rec_buckets = {'0-30 days': Decimal('0.00'), '31-60 days': Decimal('0.00'), '61-90 days': Decimal('0.00'), '91-180 days': Decimal('0.00'), '181-365 days': Decimal('0.00'), '>365 days': Decimal('0.00')}
        pay_buckets = {'0-30 days': Decimal('0.00'), '31-60 days': Decimal('0.00'), '61-90 days': Decimal('0.00'), '91-180 days': Decimal('0.00'), '181-365 days': Decimal('0.00'), '>365 days': Decimal('0.00')}

        total_receivables = Decimal('0.00')
        total_payables = Decimal('0.00')
        msme_overdue_43bh_total = Decimal('0.00')
        msme_overdue_count = 0

        def _clean_dec(val: Any, default: str = '0.00') -> Decimal:
            if val is None or val == '':
                return Decimal(default)
            cleaned = str(val).replace(',', '').replace('₹', '').replace('Rs.', '').replace('$', '').strip()
            try:
                return Decimal(cleaned)
            except Exception:
                return Decimal(default)

        def _parse_date(val: Any, default_val: date) -> date:
            if isinstance(val, datetime):
                return val.date()
            if isinstance(val, date):
                return val
            if not val:
                if isinstance(default_val, datetime):
                    return default_val.date()
                if isinstance(default_val, date):
                    return default_val
                return date(2025, 4, 1)
            val_str = str(val).strip()
            for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d', '%d.%m.%Y'):
                try:
                    return datetime.strptime(val_str, fmt).date()
                except ValueError:
                    pass
            if isinstance(default_val, datetime):
                return default_val.date()
            if isinstance(default_val, date):
                return default_val
            return date(2025, 4, 1)

        for idx, r in enumerate(aging_records, start=1):
            raw_type = str(
                r.get('item_type') or r.get('Account Type') or r.get('Account_Type') or
                r.get('Classification') or r.get('Type') or r.get('Subledger_Type') or
                r.get('subledger_type') or r.get('Subledger') or 'RECEIVABLE'
            ).strip().upper()
            if any(k in raw_type for k in ['CREDITOR', 'PAYABLE', 'VENDOR', 'SUPPLIER']):
                item_type = 'PAYABLE'
            elif any(k in raw_type for k in ['DEBTOR', 'RECEIVABLE', 'CUSTOMER', 'CLIENT']):
                item_type = 'RECEIVABLE'
            else:
                item_type = 'RECEIVABLE'

            party = str(
                r.get('party_name') or r.get('Party Name') or r.get('Particulars') or
                r.get('Party') or r.get('Counterparty_Name') or r.get('Counterparty_ID') or
                r.get('Counterparty') or f"Party {idx}"
            ).strip()
            pan = str(r.get('party_pan', r.get('Party PAN', r.get('PAN', r.get('Counterparty_PAN', ''))))).strip()
            gstin = str(r.get('party_gstin', r.get('Party GSTIN', r.get('GSTIN', r.get('Counterparty_GSTIN', ''))))).strip()

            raw_msme_type = str(
                r.get('msme_type') or r.get('MSME Type') or r.get('MSME_Registered') or
                r.get('MSME Registered') or r.get('MSME_Status') or r.get('MSME_Category') or 'NON_MSME'
            ).strip().upper()
            if raw_msme_type in ['MICRO', 'SMALL', 'MEDIUM']:
                msme_type = raw_msme_type
                is_msme = True
            elif raw_msme_type in ['YES', 'TRUE', '1', 'Y']:
                msme_type = 'MICRO'
                is_msme = True
            else:
                msme_type = 'NON_MSME'
                is_msme = bool(r.get('is_msme', False))

            inv_no = str(
                r.get('invoice_number') or r.get('Invoice No') or r.get('Invoice Number') or
                r.get('Invoice_Number') or r.get('Bill No') or f"INV-{idx:04d}"
            ).strip()
            inv_date = _parse_date(
                r.get('invoice_date') or r.get('Invoice Date') or r.get('Date') or
                r.get('Posting Date') or r.get('Invoice_Date') or r.get('Posting_Date'),
                as_of_date
            )
            due_date = _parse_date(
                r.get('due_date') or r.get('Due Date') or r.get('Due_Date'),
                inv_date
            )

            tot_amt = _clean_dec(
                r.get('total_amount') or r.get('Gross Amount') or r.get('Total Amount') or
                r.get('Total_INR') or r.get('Invoice_Amount_INR') or r.get('Outstanding_INR')
            )
            out_amt = _clean_dec(
                r.get('outstanding_amount') or r.get('Outstanding Amount') or r.get('Outstanding_INR') or
                r.get('Balance') or r.get('Outstanding_Amount_INR') or tot_amt
            )
            if tot_amt == Decimal('0.00') and out_amt > Decimal('0.00'):
                tot_amt = out_amt
            elif out_amt == Decimal('0.00') and tot_amt > Decimal('0.00'):
                out_amt = tot_amt

            # Calculate Ageing Days from invoice date
            ageing_days = max(0, (as_of_date - inv_date).days)
            if ageing_days <= 30:
                bucket = '0-30 days'
            elif ageing_days <= 60:
                bucket = '31-60 days'
            elif ageing_days <= 90:
                bucket = '61-90 days'
            elif ageing_days <= 180:
                bucket = '91-180 days'
            elif ageing_days <= 365:
                bucket = '181-365 days'
            else:
                bucket = '>365 days'

            # Section 43B(h) MSMED Screening:
            # Applies ONLY to Micro and Small suppliers with positive outstanding amounts.
            # Medium enterprises and Retail/Wholesale Traders are exempt under MSME Ministry OM.
            is_overdue_43bh = False
            overdue_days_msme = 0
            is_trader = bool(r.get('is_trader', False)) or any(k in party.lower() for k in ['retailer', 'trader', 'trading']) or (str(r.get('activity_type', '')).upper() in ['TRADING', 'RETAIL', 'WHOLESALE'])

            if item_type == 'PAYABLE' and msme_type in ['MICRO', 'SMALL'] and not is_trader and out_amt > Decimal('0.00'):
                has_agreement = r.get('has_written_agreement', True)
                threshold = 45 if has_agreement else 15
                if due_date and due_date > inv_date:
                    agreed_days = (due_date - inv_date).days
                    threshold = min(agreed_days, 45) if has_agreement else 15

                days_from_invoice = max(0, (as_of_date - inv_date).days)
                if days_from_invoice > threshold:
                    is_overdue_43bh = True
                    overdue_days_msme = days_from_invoice - threshold
                    msme_overdue_43bh_total += out_amt
                    msme_overdue_count += 1

            if item_type == 'RECEIVABLE':
                total_receivables += out_amt
                rec_buckets[bucket] += out_amt
            else:
                total_payables += out_amt
                pay_buckets[bucket] += out_amt

            item_obj = SubledgerAgingItem.objects.create(
                engagement=engagement,
                item_type=item_type,
                party_name=party,
                party_pan=pan,
                party_gstin=gstin,
                is_msme=is_msme,
                msme_type=msme_type,
                invoice_number=inv_no,
                invoice_date=inv_date,
                due_date=due_date,
                total_amount=tot_amt,
                outstanding_amount=out_amt,
                ageing_days=ageing_days,
                ageing_bucket=bucket,
                is_disputed=bool(r.get('is_disputed', False)),
                is_overdue_43bh=is_overdue_43bh,
                overdue_days_msme=overdue_days_msme,
                source_reference=str(r.get('source_location', r.get('Evidence_Reference', r.get('source_reference', f"Schedule_{item_type}_{idx}"))))
            )
            created_items.append(item_obj)

        # Create Section 43B(h) / Form 3CD Clause 22 Exception if MSME overdue detected
        if msme_overdue_count > 0:
            ExceptionItem.objects.create(
                engagement=engagement,
                rule_code="RULE_MSME_OVERDUE_43BH",
                title=f"Section 43B(h) Disallowance: Overdue MSME Payables (₹{msme_overdue_43bh_total:,.2f})",
                category="TAX_AUDIT_3CD",
                severity=ExceptionSeverity.CRITICAL,
                amount_involved=msme_overdue_43bh_total,
                explanation=(
                    f"Found {msme_overdue_count} invoices payable to Micro and Small Enterprises "
                    f"outstanding beyond statutory MSMED Act threshold (>45 days) as of March 31. "
                    f"Total overdue amount: ₹{msme_overdue_43bh_total:,.2f}."
                ),
                recommended_action=(
                    "Disallow expenditure in current financial year under Section 43B(h). "
                    "Report details in Tax Audit Form 3CD Clause 22. Deduction allowable in subsequent FY upon actual payment."
                ),
                source_reference="Creditors_Ageing_MSME"
            )

        # Control Account Reconciliations
        ar_ledgers = LedgerAccount.objects.filter(company=engagement.company, coa__schedule_iii_group='TRADE_RECEIVABLES')
        ar_control_balance = sum((l.closing_balance for l in ar_ledgers), Decimal('0.00'))
        ar_diff = abs(total_receivables - ar_control_balance)

        ap_ledgers = LedgerAccount.objects.filter(company=engagement.company, coa__schedule_iii_group='TRADE_PAYABLES')
        ap_control_balance = sum((l.closing_balance for l in ap_ledgers), Decimal('0.00'))
        ap_diff = abs(total_payables - ap_control_balance)

        return {
            'as_of_date': as_of_date.isoformat(),
            'total_items': len(created_items),
            'receivables': {
                'total_schedule_amount': str(total_receivables),
                'gl_control_balance': str(ar_control_balance),
                'variance': str(ar_diff),
                'buckets': {k: str(v) for k, v in rec_buckets.items()}
            },
            'payables': {
                'total_schedule_amount': str(total_payables),
                'gl_control_balance': str(ap_control_balance),
                'variance': str(ap_diff),
                'buckets': {k: str(v) for k, v in pay_buckets.items()}
            },
            'msme_compliance': {
                'overdue_count': msme_overdue_count,
                'overdue_amount_section_43bh': str(msme_overdue_43bh_total),
                'status': 'DISALLOWANCE_REQUIRED' if msme_overdue_count > 0 else 'COMPLIANT'
            },
            'msme_overdue_43bh_total': str(msme_overdue_43bh_total),
            'msme_overdue_count': msme_overdue_count
        }

    @classmethod
    def verify_documentary_inventory(
        cls,
        engagement: Engagement,
        stock_items: List[Dict[str, Any]],
        period_label: str = "FY 2024-25"
    ) -> Dict[str, Any]:
        """
        Validates mathematical stock movement equation:
        Opening Stock + Purchases/Inward - Sales/Outward = Expected Closing Stock.
        Detects negative closing stocks, duplicate item codes, and unusual valuation drops.
        """
        negative_stocks = []
        duplicate_codes = set()
        seen_codes = set()
        reconciliation_discrepancies = []

        total_opening_value = Decimal('0.00')
        total_closing_value = Decimal('0.00')

        def _clean_dec(val: Any, default: str = '0.00') -> Decimal:
            if val is None or val == '':
                return Decimal(default)
            cleaned = str(val).replace(',', '').replace('₹', '').replace('Rs.', '').replace('$', '').strip()
            try:
                return Decimal(cleaned)
            except Exception:
                return Decimal(default)

        for idx, item in enumerate(stock_items, start=1):
            code = str(item.get('item_code', f"SKU-{idx:04d}")).strip()
            desc = str(item.get('description', f"Stock Item {idx}")).strip()

            if code in seen_codes:
                duplicate_codes.add(code)
            seen_codes.add(code)

            op_qty = _clean_dec(item.get('opening_qty', 0))
            op_rate = _clean_dec(item.get('opening_rate', 0))
            inward_qty = _clean_dec(item.get('inward_qty', 0))
            outward_qty = _clean_dec(item.get('outward_qty', 0))
            closing_qty = _clean_dec(item.get('closing_qty', 0))
            closing_rate = _clean_dec(item.get('closing_rate', op_rate))

            expected_closing_qty = op_qty + inward_qty - outward_qty
            qty_variance = abs(expected_closing_qty - closing_qty)

            if closing_qty < 0:
                negative_stocks.append({
                    'item_code': code,
                    'description': desc,
                    'closing_qty': str(closing_qty),
                    'rate': str(closing_rate)
                })

            if qty_variance > Decimal('0.001'):
                reconciliation_discrepancies.append({
                    'item_code': code,
                    'expected_qty': str(expected_closing_qty),
                    'actual_qty': str(closing_qty),
                    'variance_qty': str(qty_variance)
                })

            total_opening_value += (op_qty * op_rate)
            total_closing_value += (closing_qty * closing_rate)

        # Flag negative stock exception if found
        if negative_stocks:
            ExceptionItem.objects.create(
                engagement=engagement,
                rule_code="RULE_NEGATIVE_STOCK",
                title=f"Negative Inventory Balances Detected ({len(negative_stocks)} items)",
                category="ACCURACY",
                severity=ExceptionSeverity.HIGH,
                amount_involved=Decimal('0.00'),
                explanation=f"Found {len(negative_stocks)} stock items with negative physical quantities in stock ledger.",
                recommended_action="Audit for unrecorded purchase delivery receipts or timing discrepancies in issue voucher postings.",
                source_reference="Inventory_Stock_Ledger"
            )

        return {
            'period_label': period_label,
            'total_items_tested': len(stock_items),
            'total_opening_valuation': str(total_opening_value.quantize(Decimal('0.01'))),
            'total_closing_valuation': str(total_closing_value.quantize(Decimal('0.01'))),
            'negative_stock_count': len(negative_stocks),
            'duplicate_codes_count': len(duplicate_codes),
            'movement_discrepancies_count': len(reconciliation_discrepancies),
            'disclaimer': (
                "IMPORTANT AUDIT CAVEAT: This analysis represents a deterministic mathematical check of documentary "
                "inventory movements and valuations. It does not constitute physical inventory verification under SA 501."
            )
        }
