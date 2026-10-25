"""
Audit Correction Engine.
Orchestrates rule evaluation against live engagement data, aggregates impacts,
and generates Proposed Journal Entries (PJEs) for auditor review.
"""

from decimal import Decimal
from typing import Dict, Any, List
import logging
from .registry import correction_rule_registry

logger = logging.getLogger(__name__)

class AuditCorrectionEngine:
    @classmethod
    def evaluate_engagement(cls, engagement) -> Dict[str, Any]:
        """
        Extracts engagement data, runs all statutory correction rules,
        and returns an Audit Adjustment Schedule with financial impacts.
        """
        from apps.audit.models import FixedAsset, SubledgerAgingItem, ExceptionItem
        from apps.accounting.models import TrialBalanceAccount

        # Build context from engagement records
        context = {
            "engagement_id": engagement.id if hasattr(engagement, 'id') else None,
            "subledger_aging": [],
            "fixed_assets": [],
            "debtors_aging": [],
            "gst_ineligible_records": [],
            "cutoff_mismatches": []
        }

        # 1. Fetch MSME & Creditor Subledger Items
        aging_items = SubledgerAgingItem.objects.filter(engagement=engagement)
        for item in aging_items:
            context["subledger_aging"].append({
                "party_name": item.party_name,
                "is_msme": item.is_msme,
                "overdue_days": item.overdue_days,
                "balance": item.closing_balance or item.overdue_amount or Decimal("0.00")
            })
            if not item.is_msme and item.closing_balance and item.closing_balance > Decimal("0.00"):
                context["debtors_aging"].append({
                    "party_name": item.party_name,
                    "amount": item.closing_balance,
                    "age_days": item.overdue_days
                })

        # 2. Fetch Fixed Assets
        assets = FixedAsset.objects.filter(engagement=engagement)
        for a in assets:
            context["fixed_assets"].append({
                "asset_id": a.asset_id,
                "asset_name": a.asset_name,
                "book_depreciation": a.book_depreciation or Decimal("0.00"),
                "calculated_schedule_ii_depreciation": a.calculated_depreciation or a.book_depreciation or Decimal("0.00")
            })

        # 3. Fetch Ineligible GST or Exception Items
        exceptions = ExceptionItem.objects.filter(engagement=engagement)
        for exc in exceptions:
            if "GST" in (exc.category or "").upper() or "ITC" in (exc.title or "").upper():
                context["gst_ineligible_records"].append({
                    "tax_amount": exc.amount or Decimal("0.00"),
                    "reason": exc.title
                })
            elif "CUTOFF" in (exc.category or "").upper() or "CUT-OFF" in (exc.title or "").upper():
                context["cutoff_mismatches"].append({
                    "amount": exc.amount or Decimal("0.00"),
                    "details": exc.title
                })

        # Run registered rules
        proposed_adjustments = correction_rule_registry.execute_all(context)

        # Calculate Financial Statement Impact Summary
        total_pnl_impact = Decimal("0.00")
        total_bs_impact = Decimal("0.00")
        high_severity_count = 0

        for adj in proposed_adjustments:
            total_pnl_impact += Decimal(str(adj.get("pnl_impact", "0.00")))
            total_bs_impact += Decimal(str(adj.get("balance_sheet_impact", "0.00")))
            if adj.get("severity") == "HIGH":
                high_severity_count += 1

        return {
            "engagement_id": engagement.id if hasattr(engagement, 'id') else None,
            "total_adjustments_count": len(proposed_adjustments),
            "high_severity_count": high_severity_count,
            "financial_impact": {
                "net_profit_impact": float(total_pnl_impact),
                "balance_sheet_impact": float(total_bs_impact),
                "is_material": abs(total_pnl_impact) > Decimal("50000.00")
            },
            "proposed_journal_entries": proposed_adjustments
        }
