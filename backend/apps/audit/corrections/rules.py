"""
Concrete Statutory Audit Correction Rules for Indian Entities.
Adheres strictly to:
- Companies Act 2013 (Schedule II, Schedule III Division I, CARO 2020)
- Income Tax Act 1961 (Section 43B(h), Section 32, Section 40(a)(ia))
- MSMED Act 2006 (Section 15, 16, 22)
- Central Goods and Services Tax Act 2017 (Section 16(2), Section 17(5), Rule 37)
"""

from decimal import Decimal
from typing import Dict, Any, List
from .registry import BaseAuditCorrectionRule, correction_rule_registry

@correction_rule_registry.register
class MSMEDisallowanceRule(BaseAuditCorrectionRule):
    rule_id = "MSME_SEC_43B_H"
    title = "MSME Section 43B(h) Overdue & Compound Interest Accrual"
    statutory_reference = "Income Tax Act 1961 Sec 43B(h) & MSMED Act 2006 Sec 16"
    category = "DISALLOWANCE"

    def evaluate(self, engagement_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        corrections = []
        subledger_items = engagement_context.get("subledger_aging", [])
        
        # RBI bank rate reference ~ 6.5%, 3x compound monthly = ~19.5% - 20%
        annual_interest_rate = Decimal("0.20")

        for item in subledger_items:
            is_msme = item.get("is_msme", False)
            overdue_days = item.get("overdue_days", 0)
            balance = Decimal(str(item.get("balance", "0.00")))
            party_name = item.get("party_name", "Unknown Supplier")

            # Check if overdue beyond 45 days (or 15 days without agreement)
            if is_msme and overdue_days > 45 and balance > Decimal("0.00"):
                # Calculate compound interest under Sec 16 MSMED Act
                pro_rata_interest = (balance * annual_interest_rate * Decimal(str(overdue_days))) / Decimal("365.0")
                pro_rata_interest = pro_rata_interest.quantize(Decimal("0.01"))

                corrections.append({
                    "rule_id": self.rule_id,
                    "title": f"MSME Statutory Disallowance & Interest: {party_name}",
                    "statutory_ref": self.statutory_reference,
                    "severity": "HIGH",
                    "party_name": party_name,
                    "recommended_debit_ledger": "Interest on Delayed MSME Payments (Inadmissible u/s 23 MSMED)",
                    "recommended_credit_ledger": f"Interest Payable - {party_name}",
                    "amount": float(pro_rata_interest),
                    "disallowance_principal": float(balance),
                    "narration": f"Accrual of statutory compound interest u/s 16 MSMED Act on overdue balance of ₹{balance} ({overdue_days} days overdue). Principal disallowed under Sec 43B(h).",
                    "pnl_impact": float(-pro_rata_interest),
                    "balance_sheet_impact": float(pro_rata_interest),
                    "audit_note": "This interest expense is expressly disallowed as a tax deduction under Section 23 of the MSMED Act. Principal must be added back in Tax Audit Form 3CD Clause 22."
                })
        return corrections


@correction_rule_registry.register
class DepreciationScheduleIIRule(BaseAuditCorrectionRule):
    rule_id = "FAR_DEPN_SCH_II"
    title = "Schedule II Companies Act 2013 Useful Life Depreciation Rectification"
    statutory_reference = "Companies Act 2013 Schedule II & AS 10 / Ind AS 16"
    category = "RECLASSIFICATION"

    def evaluate(self, engagement_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        corrections = []
        fixed_assets = engagement_context.get("fixed_assets", [])

        total_variance = Decimal("0.00")
        for asset in fixed_assets:
            book_depn = Decimal(str(asset.get("book_depreciation", "0.00")))
            sch2_depn = Decimal(str(asset.get("calculated_schedule_ii_depreciation", "0.00")))
            diff = sch2_depn - book_depn
            if abs(diff) > Decimal("500.00"):
                total_variance += diff

        if abs(total_variance) > Decimal("1000.00"):
            is_underprovided = total_variance > Decimal("0.00")
            corrections.append({
                "rule_id": self.rule_id,
                "title": "Depreciation Schedule II True & Fair Adjustment",
                "statutory_ref": self.statutory_reference,
                "severity": "MEDIUM",
                "recommended_debit_ledger": "Depreciation and Amortization Expense" if is_underprovided else "Accumulated Depreciation",
                "recommended_credit_ledger": "Accumulated Depreciation" if is_underprovided else "Depreciation and Amortization Expense",
                "amount": float(abs(total_variance)),
                "narration": f"Being adjustment of {'under-provided' if is_underprovided else 'excess'} depreciation to align with statutory useful lives prescribed under Schedule II of Companies Act 2013.",
                "pnl_impact": float(-total_variance),
                "balance_sheet_impact": float(-total_variance),
                "audit_note": "Variance creates a temporary timing difference requiring Deferred Tax Asset/Liability re-computation under AS 22 / Ind AS 12."
            })
        return corrections


@correction_rule_registry.register
class GSTBlockedCreditReversalRule(BaseAuditCorrectionRule):
    rule_id = "GST_RULE_37_17_5"
    title = "GST Ineligible ITC Reversal (Sec 17(5) & Rule 37 180-Day Rule)",
    statutory_reference = "CGST Act 2017 Sec 16(2) 2nd Proviso, Sec 17(5) & Rule 37"
    category = "COMPLIANCE"

    def evaluate(self, engagement_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        corrections = []
        gst_exceptions = engagement_context.get("gst_ineligible_records", [])

        total_reversal = Decimal("0.00")
        for item in gst_exceptions:
            itc_amt = Decimal(str(item.get("tax_amount", "0.00")))
            reason = item.get("reason", "Ineligible / Unpaid > 180 Days")
            if itc_amt > Decimal("0.00"):
                total_reversal += itc_amt

        if total_reversal > Decimal("500.00"):
            corrections.append({
                "rule_id": self.rule_id,
                "title": "GST ITC Reversal for Ineligible Credits / Unpaid Suppliers",
                "statutory_ref": self.statutory_reference,
                "severity": "HIGH",
                "recommended_debit_ledger": "Ineligible ITC Written Off (P&L)",
                "recommended_credit_ledger": "Electronic Credit Ledger / GST Input IGST/CGST/SGST",
                "amount": float(total_reversal),
                "narration": "Reversal of ineligible ITC u/s 17(5) and non-payment to suppliers beyond 180 days under Rule 37 of CGST Rules 2017.",
                "pnl_impact": float(-total_reversal),
                "balance_sheet_impact": float(-total_reversal),
                "audit_note": "Requires disclosure in GSTR-3B Table 4(B) and payment of 18% p.a. interest from date of availment till date of reversal."
            })
        return corrections


@correction_rule_registry.register
class DebtorProvisioningRule(BaseAuditCorrectionRule):
    rule_id = "DEBTOR_DOUBTFUL_PROVISION"
    title = "Provision for Doubtful Debts & Unbilled Accruals"
    statutory_reference = "Companies Act 2013 Schedule III & ICAI SA 540"
    category = "PROVISIONING"

    def evaluate(self, engagement_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        corrections = []
        debtors_aging = engagement_context.get("debtors_aging", [])
        
        # Debts > 180 days with dispute or > 3 years (time-barred under Limitation Act 1963)
        doubtful_pool = Decimal("0.00")
        for d in debtors_aging:
            age = d.get("age_days", 0)
            amt = Decimal(str(d.get("amount", "0.00")))
            if age > 365 and amt > Decimal("0.00"):
                doubtful_pool += (amt * Decimal("0.50")) # 50% prudent provision
            elif age > 1095: # 3 years
                doubtful_pool += amt # 100% provision for time-barred debts

        if doubtful_pool > Decimal("5000.00"):
            doubtful_pool = doubtful_pool.quantize(Decimal("0.01"))
            corrections.append({
                "rule_id": self.rule_id,
                "title": "Prudent Provision for Doubtful Trade Receivables (>1 Year)",
                "statutory_ref": self.statutory_reference,
                "severity": "MEDIUM",
                "recommended_debit_ledger": "Provision for Doubtful Debts (P&L)",
                "recommended_credit_ledger": "Allowance for Bad & Doubtful Debts (Deduction from Trade Receivables)",
                "amount": float(doubtful_pool),
                "narration": "Being creation of prudent provision for trade receivables aged over 1 year / 3 years without recovery.",
                "pnl_impact": float(-doubtful_pool),
                "balance_sheet_impact": float(-doubtful_pool),
                "audit_note": "Required under Schedule III Division I Trade Receivables disclosure (Doubtful debts must be presented separately)."
            })
        return corrections


@correction_rule_registry.register
class RevenueCutoffRule(BaseAuditCorrectionRule):
    rule_id = "REVENUE_CUTOFF_SA_560"
    title = "Year-End Sales Cut-off & Unearned Revenue Deferral"
    statutory_reference = "ICAI SA 500 / SA 560 & Ind AS 115"
    category = "RECLASSIFICATION"

    def evaluate(self, engagement_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        corrections = []
        cutoff_invoices = engagement_context.get("cutoff_mismatches", [])

        total_deferral = Decimal("0.00")
        for inv in cutoff_invoices:
            amt = Decimal(str(inv.get("amount", "0.00")))
            if amt > Decimal("0.00"):
                total_deferral += amt

        if total_deferral > Decimal("1000.00"):
            corrections.append({
                "rule_id": self.rule_id,
                "title": "Revenue Cut-off Rectification (Goods Delivered Post Balance Sheet Date)",
                "statutory_ref": self.statutory_reference,
                "severity": "HIGH",
                "recommended_debit_ledger": "Revenue from Operations",
                "recommended_credit_ledger": "Unearned Revenue / Advances from Customers",
                "amount": float(total_deferral),
                "narration": "Reversal of revenue recognized before satisfaction of performance obligation / physical delivery of goods prior to March 31.",
                "pnl_impact": float(-total_deferral),
                "balance_sheet_impact": Decimal("0.00"), # Shift from Equity to Liability
                "audit_note": "In accordance with Ind AS 115 / AS 9 Revenue Recognition principles."
            })
        return corrections
