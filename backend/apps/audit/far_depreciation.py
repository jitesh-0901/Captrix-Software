from decimal import Decimal
from datetime import date, datetime
from typing import List, Dict, Any, Optional
from apps.companies.models import Engagement
from apps.audit.models import FixedAsset, ExceptionItem, ExceptionSeverity, ExceptionStatus
from apps.accounting.models import LedgerAccount, Transaction

class FixedAssetAuditEngine:
    """
    Automated audit engine for Fixed Assets (PPE), Fixed Asset Register (FAR) scrutiny,
    and Dual Depreciation Recalculation (Companies Act 2013 Schedule II vs Income Tax Act Section 32).
    """

    # Standard Companies Act Schedule II Useful Lives (in Years)
    SCHEDULE_II_USEFUL_LIVES = {
        'PLANT & MACHINERY': Decimal('15.0'),
        'COMPUTERS & SERVERS': Decimal('3.0'),
        'OFFICE EQUIPMENT': Decimal('5.0'),
        'FURNITURE & FIXTURES': Decimal('10.0'),
        'BUILDINGS (RCC)': Decimal('60.0'),
        'VEHICLES': Decimal('8.0'),
    }

    # Income Tax Act Section 32 Block Depreciation Rates
    SECTION_32_RATES = {
        'PLANT & MACHINERY': Decimal('15.0'),
        'COMPUTERS & SERVERS': Decimal('40.0'),
        'OFFICE EQUIPMENT': Decimal('15.0'),
        'FURNITURE & FIXTURES': Decimal('10.0'),
        'BUILDINGS (RCC)': Decimal('10.0'),
        'VEHICLES': Decimal('15.0'),
    }

    @classmethod
    def import_and_validate_far(
        cls,
        engagement: Engagement,
        far_records: List[Dict[str, Any]],
        document=None
    ) -> Dict[str, Any]:
        """
        Parses FAR records, validates asset uniqueness, recalculates dual depreciation,
        and detects potential duplicate assets or date discrepancies.
        """
        FixedAsset.objects.filter(engagement=engagement).delete()

        created_assets = []
        seen_ids = set()
        seen_combos = {} # (name, cost, date) -> asset_id
        duplicates_detected = []
        zero_cost_detected = []
        invalid_dates_detected = []
        discrepancies = []

        total_cost = Decimal('0.00')
        total_sch_ii_dep = Decimal('0.00')
        total_sec_32_dep = Decimal('0.00')

        fy_start = engagement.financial_year.start_date
        fy_end = engagement.financial_year.end_date

        def get_field(record, keys, default=''):
            for k in keys:
                if k in record and record[k] is not None and str(record[k]).strip() != '':
                    return str(record[k]).strip()
                k_clean = k.lower().replace('_', ' ')
                for rk, rv in record.items():
                    if str(rk).strip().lower().replace('_', ' ') == k_clean:
                        if rv is not None and str(rv).strip() != '':
                            return str(rv).strip()
            return default

        for idx, rec in enumerate(far_records, start=1):
            raw_id = get_field(rec, ['asset_id', 'Asset_ID', 'Asset ID', 'Asset Code', 'Code'], f"FA-{idx:04d}")
            name = get_field(rec, ['asset_name', 'Asset_Description', 'Asset Description', 'Asset Name', 'Particulars', 'Description'], f"Asset {idx}")
            cat_raw = get_field(rec, ['category', 'Asset_Category', 'Asset Category', 'Asset Class', 'Category'], 'PLANT & MACHINERY').upper()
            if 'FURNITURE' in cat_raw:
                category = 'FURNITURE & FIXTURES'
            elif 'PLANT' in cat_raw or 'MACHINERY' in cat_raw:
                category = 'PLANT & MACHINERY'
            elif 'COMPUTER' in cat_raw or 'SERVER' in cat_raw or cat_raw.startswith('IT') or '_IT' in cat_raw or 'IT_' in cat_raw or cat_raw == 'IT':
                category = 'COMPUTERS & SERVERS'
            elif 'OFFICE' in cat_raw:
                category = 'OFFICE EQUIPMENT'
            elif 'VEHICLE' in cat_raw:
                category = 'VEHICLES'
            elif 'BUILDING' in cat_raw:
                category = 'BUILDINGS (RCC)'
            else:
                category = cat_raw
            
            raw_cost = get_field(rec, [
                'cost', 'Capitalized_Cost_INR', 'original_cost', 'Original Cost',
                'Gross Block (INR)', 'Gross Block', 'Cost', 'Purchase Cost', 'Purchase_Cost',
                'Purchase Price', 'Gross Value', 'Gross_Value', 'Acquisition Cost',
                'Acquisition_Cost', 'Cost of Asset', 'Total Cost', 'Asset Cost'
            ]).replace(',', '').replace('₹', '').replace(' ', '').strip()
            cost = Decimal(raw_cost) if raw_cost else Decimal('0.00')

            if cost <= Decimal('0.00'):
                zero_cost_detected.append({'asset_id': raw_id, 'name': name})

            raw_acc = get_field(rec, ['accumulated_depreciation', 'Opening_Accumulated_Depreciation_INR', 'Accumulated Depreciation', 'Opening Dep', 'Accumulated Dep']).replace(',', '').replace('₹', '').replace(' ', '').strip()
            acc_dep = Decimal(raw_acc) if raw_acc else Decimal('0.00')

            raw_booked = get_field(rec, [
                'booked_depreciation', 'book_depreciation', 'Book_Depreciation', 'Book Depreciation',
                'Current_Year_Depreciation_Booked_INR', 'current_year_depreciation_booked_inr',
                'Booked_Depreciation_INR', 'booked_depreciation_inr',
                'Depreciation_Charged', 'Current_Year_Depreciation', 'Depreciation_for_the_Year',
                'Depreciation_FY', 'Book Dep', 'Depn Book', 'Depreciation', 'Book Depn'
            ]).replace(',', '').replace('₹', '').replace(' ', '').strip()
            booked_dep_item = Decimal(raw_booked) if raw_booked else Decimal('0.00')

            location = get_field(rec, ['location', 'Location', 'Site', 'Plant'], 'Main Facility')

            raw_acq = get_field(rec, ['acquisition_date', 'Acquisition_Date', 'Purchase Date', 'Date of Purchase', 'Date of Capitalization', 'Capitalization Date'])
            if raw_acq:
                try:
                    date_part = raw_acq.split()[0]
                    acq_date = datetime.strptime(date_part, '%Y-%m-%d').date()
                except Exception:
                    try:
                        acq_date = datetime.strptime(date_part, '%d-%m-%Y').date()
                    except Exception:
                        acq_date = fy_start
            else:
                acq_date = fy_start

            raw_put = get_field(rec, ['put_to_use_date', 'Put_To_Use_Date', 'Put to Use Date', 'Date of Put to Use', 'Capitalization Date'])
            if raw_put:
                try:
                    date_part = raw_put.split()[0]
                    put_to_use = datetime.strptime(date_part, '%Y-%m-%d').date()
                except Exception:
                    try:
                        put_to_use = datetime.strptime(date_part, '%d-%m-%Y').date()
                    except Exception:
                        put_to_use = acq_date
            else:
                put_to_use = acq_date

            # Date sequence and reporting period validation
            if acq_date > fy_end:
                invalid_dates_detected.append({'asset_id': raw_id, 'reason': f"Acquisition date {acq_date} occurs after FY end {fy_end}"})
            if put_to_use > fy_end:
                invalid_dates_detected.append({'asset_id': raw_id, 'reason': f"Put-to-use date {put_to_use} occurs after FY end {fy_end}"})
            if put_to_use < acq_date:
                invalid_dates_detected.append({'asset_id': raw_id, 'reason': f"Put-to-use date {put_to_use} precedes acquisition date {acq_date}"})

            # Duplicate ID check
            is_dup = False
            if raw_id in seen_ids:
                is_dup = True
                duplicates_detected.append({'asset_id': raw_id, 'reason': 'Duplicate Asset Identifier'})
            seen_ids.add(raw_id)

            # Duplicate asset candidate check (same name, exact cost, same acquisition date)
            combo_key = (name.lower(), cost, acq_date)
            if combo_key in seen_combos:
                is_dup = True
                duplicates_detected.append({
                    'asset_id': raw_id,
                    'original_id': seen_combos[combo_key],
                    'reason': f"Exact duplicate candidate with {seen_combos[combo_key]} (Cost: ₹{cost})"
                })
            else:
                seen_combos[combo_key] = raw_id

            # Determine useful life and Section 32 rate (with explicit record overrides)
            raw_life = get_field(rec, ['useful_life_years', 'Useful_Life_Years', 'Sch II Life (Yrs)', 'Useful Life', 'Life (Years)'])
            if raw_life:
                try:
                    useful_life = Decimal(str(raw_life).strip())
                except Exception:
                    useful_life = cls.SCHEDULE_II_USEFUL_LIVES.get(category, Decimal('5.0'))
            else:
                useful_life = cls.SCHEDULE_II_USEFUL_LIVES.get(category, Decimal('5.0'))

            raw_sec32 = get_field(rec, ['sec_32_rate', 'Depreciation_Rate_Percent', 'Sec 32 Block Rate', 'Section 32 Rate', 'IT Rate'])
            if raw_sec32:
                try:
                    sec_32_rate = Decimal(str(raw_sec32).replace('%', '').strip())
                except Exception:
                    sec_32_rate = cls.SECTION_32_RATES.get(category, Decimal('15.0'))
            else:
                sec_32_rate = cls.SECTION_32_RATES.get(category, Decimal('15.0'))

            # Parse residual value / percentage
            raw_res_pct = get_field(rec, ['residual_pct', 'Residual_Pct', 'Residual %', 'Residual Percentage', 'Scrap %', 'Scrap_Pct'])
            raw_res_val = get_field(rec, ['residual_value', 'Residual_Value', 'Residual Value', 'Scrap Value', 'Scrap_Value', 'Salvage Value'])
            if raw_res_pct:
                try:
                    residual_pct = Decimal(str(raw_res_pct).replace('%', '').strip())
                    salvage_value = (cost * (residual_pct / Decimal('100.0'))).quantize(Decimal('0.01'))
                except Exception:
                    residual_pct = Decimal('5.00')
                    salvage_value = (cost * Decimal('0.05')).quantize(Decimal('0.01'))
            elif raw_res_val:
                try:
                    salvage_value = Decimal(str(raw_res_val).replace(',', '').replace('₹', '').strip()).quantize(Decimal('0.01'))
                    residual_pct = ((salvage_value / cost) * Decimal('100.0')).quantize(Decimal('0.01')) if cost > Decimal('0.00') else Decimal('5.00')
                except Exception:
                    residual_pct = Decimal('5.00')
                    salvage_value = (cost * Decimal('0.05')).quantize(Decimal('0.01'))
            else:
                residual_pct = Decimal('5.00')
                salvage_value = (cost * Decimal('0.05')).quantize(Decimal('0.01'))

            dep_method = get_field(rec, ['depreciation_method', 'Depreciation_Method', 'Depreciation Method', 'Method', 'method'], 'SLM').upper()

            # Recalculate Schedule II Depreciation
            total_days_in_fy = (fy_end - fy_start).days + 1
            days_in_fy = Decimal(str(max(1, total_days_in_fy)))

            if useful_life <= Decimal('0.0'):
                useful_life = cls.SCHEDULE_II_USEFUL_LIVES.get(category, Decimal('5.0'))

            max_depreciable_life = max(Decimal('0.00'), cost - salvage_value)
            remaining_headroom = max(Decimal('0.00'), max_depreciable_life - acc_dep)

            if put_to_use > fy_end:
                proportion = Decimal('0.0')
                computed_sch_ii_dep = Decimal('0.00')
                computed_sec_32_dep = Decimal('0.00')
            elif remaining_headroom <= Decimal('0.00'):
                proportion = Decimal('0.0')
                computed_sch_ii_dep = Decimal('0.00')
                computed_sec_32_dep = Decimal('0.00')
            else:
                if put_to_use > fy_start:
                    active_days = Decimal(str(max(0, (fy_end - put_to_use).days + 1)))
                    proportion = active_days / days_in_fy
                else:
                    proportion = Decimal('1.0')

                if 'WDV' in dep_method:
                    opening_wdv = max(Decimal('0.00'), cost - acc_dep)
                    annual_wdv = (opening_wdv * (sec_32_rate / Decimal('100.0')) * proportion).quantize(Decimal('0.01'))
                    computed_sch_ii_dep = min(remaining_headroom, annual_wdv)
                else:
                    annual_slm_dep = max_depreciable_life / useful_life
                    computed_sch_ii_dep = min(remaining_headroom, (annual_slm_dep * proportion).quantize(Decimal('0.01')))

                # Recalculate Income Tax Section 32 Depreciation
                if put_to_use >= fy_start:
                    days_used = (fy_end - put_to_use).days + 1
                    half_rate_factor = Decimal('0.5') if days_used < 180 else Decimal('1.0')
                    effective_sec_32_rate = (sec_32_rate / Decimal('100.0')) * half_rate_factor
                    computed_sec_32_dep = (cost * effective_sec_32_rate).quantize(Decimal('0.01'))
                else:
                    effective_sec_32_rate = sec_32_rate / Decimal('100.0')
                    opening_wdv = max(Decimal('0.00'), cost - acc_dep)
                    computed_sec_32_dep = (opening_wdv * effective_sec_32_rate).quantize(Decimal('0.01'))

            carrying_amt = max(salvage_value if cost > 0 else Decimal('0.00'), cost - acc_dep - computed_sch_ii_dep)

            total_cost += cost
            total_sch_ii_dep += computed_sch_ii_dep
            total_sec_32_dep += computed_sec_32_dep

            asset_dep_variance = abs(computed_sch_ii_dep - booked_dep_item)

            asset_obj = FixedAsset.objects.create(
                engagement=engagement,
                asset_id=raw_id,
                asset_name=name,
                category=category,
                acquisition_date=acq_date,
                put_to_use_date=put_to_use,
                original_cost=cost,
                useful_life_years=useful_life,
                residual_pct=residual_pct,
                sch_ii_depreciation=computed_sch_ii_dep,
                sec_32_rate=sec_32_rate,
                sec_32_depreciation=computed_sec_32_dep,
                booked_depreciation=booked_dep_item,
                depreciation_variance=asset_dep_variance,
                accumulated_depreciation=acc_dep + computed_sch_ii_dep,
                carrying_amount=carrying_amt,
                location=location,
                is_duplicate_candidate=is_dup,
                source_reference=f"FAR_Row_{idx}"
            )
            created_assets.append(asset_obj)

        # Flag duplicate candidates in Exceptions
        if duplicates_detected:
            ExceptionItem.objects.create(
                engagement=engagement,
                rule_code="RULE_FAR_DUPLICATE_ASSET",
                title=f"Potential Duplicate Assets Identified in FAR ({len(duplicates_detected)} instances)",
                category="CARO_2020",
                severity=ExceptionSeverity.HIGH,
                amount_involved=Decimal('0.00'),
                explanation=f"Identified {len(duplicates_detected)} duplicate asset records or duplicate asset identifiers in Fixed Asset Register.",
                recommended_action="Physically verify physical tag numbers and reconcile FAR against purchase invoices to eliminate redundant capitalizations.",
                source_reference="FAR_Register"
            )

        # Flag zero-cost assets in Exceptions
        if zero_cost_detected:
            ExceptionItem.objects.create(
                engagement=engagement,
                rule_code="RULE_FAR_ZERO_COST",
                title=f"Assets Recorded with Zero Cost in FAR ({len(zero_cost_detected)} items)",
                category="ACCURACY",
                severity=ExceptionSeverity.HIGH,
                amount_involved=Decimal('0.00'),
                explanation=f"{len(zero_cost_detected)} assets are recorded with zero acquisition cost in the Fixed Asset Register.",
                recommended_action="Inspect capitalization vouchers and vendor purchase invoices to establish actual historical cost.",
                source_reference="FAR_Register"
            )

        # Flag invalid dates / reporting-period mismatches in Exceptions
        if invalid_dates_detected:
            ExceptionItem.objects.create(
                engagement=engagement,
                rule_code="RULE_FAR_INVALID_DATE",
                title=f"Asset Date Sequencing or Reporting Period Anomaly ({len(invalid_dates_detected)} items)",
                category="ACCURACY",
                severity=ExceptionSeverity.HIGH,
                amount_involved=Decimal('0.00'),
                explanation=f"Identified {len(invalid_dates_detected)} date discrepancies in FAR (future capitalization dates or put-to-use preceding acquisition).",
                recommended_action="Verify asset commissioning certificates and capitalization dates against plant inspection records.",
                source_reference="FAR_Register"
            )

        # Compare recalculated Schedule II depreciation against Depreciation Ledger in Books
        dep_ledgers = LedgerAccount.objects.filter(
            company=engagement.company,
            coa__schedule_iii_group='DEPRECIATION_AMORT'
        )
        book_dep = sum((l.closing_balance for l in dep_ledgers), Decimal('0.00'))
        dep_variance = abs(total_sch_ii_dep - book_dep)

        if dep_variance > Decimal('1000.00'):
            ExceptionItem.objects.filter(engagement=engagement, rule_code="RULE_DEPRECIATION_VARIANCE").delete()
            from apps.reporting.models import ProposedAdjustment, AdjustmentStatus
            aje = engagement.adjustments.filter(adjustment_number__in=["AJE-01", "AJE-DEP-01"]).first()
            if not aje:
                aje = ProposedAdjustment.objects.create(
                    engagement=engagement,
                    adjustment_number="AJE-01",
                    title="Adjustment for Schedule II Depreciation Variance",
                    reason=f"Recalculated Schedule II depreciation (₹{total_sch_ii_dep:,.2f}) differs from booked depreciation (₹{book_dep:,.2f}) by ₹{dep_variance:,.2f}.",
                    journal_entries=[
                        {'account': 'Depreciation Expense (P&L)', 'debit': str(dep_variance), 'credit': '0.00'},
                        {'account': 'Accumulated Depreciation (PPE)', 'debit': '0.00', 'credit': str(dep_variance)}
                    ],
                    total_debit=dep_variance,
                    total_credit=dep_variance,
                    is_balanced=True,
                    pnl_impact=-dep_variance,
                    status=AdjustmentStatus.PROPOSED,
                    is_posted=False
                )

            if aje and aje.is_posted:
                init_status = ExceptionStatus.AJE_POSTED
            elif aje and aje.status == AdjustmentStatus.APPROVED_BY_PARTNER:
                init_status = ExceptionStatus.IN_REVIEW
            elif aje:
                init_status = ExceptionStatus.AJE_PROPOSED
            else:
                init_status = ExceptionStatus.OPEN

            ExceptionItem.objects.create(
                engagement=engagement,
                rule_code="RULE_DEPRECIATION_VARIANCE",
                title=f"Depreciation Variance: Schedule II (₹{total_sch_ii_dep:,.2f}) vs Books (₹{book_dep:,.2f})",
                category="ACCURACY",
                severity=ExceptionSeverity.HIGH,
                status=init_status,
                amount_involved=dep_variance,
                explanation=(
                    f"Recalculated Companies Act 2013 Schedule II depreciation based on asset-wise useful lives "
                    f"is ₹{total_sch_ii_dep:,.2f}, whereas recorded depreciation in general ledger is ₹{book_dep:,.2f}. "
                    f"Unexplained variance of ₹{dep_variance:,.2f}."
                ),
                recommended_action=f"Post proposed adjusting journal entry ({aje.adjustment_number}) for depreciation variance or adjust asset-wise useful life parameters in FAR.",
                source_reference="FAR_Depreciation_Recalculation"
            )
        else:
            ExceptionItem.objects.filter(engagement=engagement, rule_code="RULE_DEPRECIATION_VARIANCE").delete()

        assets_with_variance = [a for a in created_assets if a.depreciation_variance > Decimal('0.00')]
        return {
            'total_assets': len(created_assets),
            'total_gross_block': str(total_cost),
            'recalculated_schedule_ii_depreciation': str(total_sch_ii_dep),
            'recalculated_section_32_it_depreciation': str(total_sec_32_dep),
            'book_depreciation': str(book_dep),
            'depreciation_variance': str(dep_variance),
            'duplicate_candidates_count': len(duplicates_detected),
            'zero_cost_assets_count': len(zero_cost_detected),
            'invalid_dates_count': len(invalid_dates_detected),
            'assets_with_variance_count': len(assets_with_variance),
            'is_depreciation_reconciled': dep_variance <= Decimal('100.00'),
            'asset_wise_depreciation': [
                {
                    'asset_id': a.asset_id,
                    'name': a.asset_name,
                    'cost': str(a.original_cost),
                    'residual_pct': str(a.residual_pct),
                    'useful_life': str(a.useful_life_years),
                    'sch_ii_depreciation': str(a.sch_ii_depreciation),
                    'sec_32_depreciation': str(a.sec_32_depreciation),
                    'booked_depreciation': str(a.booked_depreciation),
                    'depreciation_variance': str(a.depreciation_variance)
                }
                for a in created_assets
            ]
        }
