import pytest
from decimal import Decimal
from apps.audit.corrections.registry import correction_rule_registry
from apps.audit.corrections.rules import (
    MSMEDisallowanceRule,
    DepreciationScheduleIIRule,
    GSTBlockedCreditReversalRule,
    DebtorProvisioningRule,
    RevenueCutoffRule
)
from apps.audit.corrections.engine import AuditCorrectionEngine

def test_registry_has_statutory_rules():
    rules = correction_rule_registry.get_all_rules()
    rule_ids = [r.rule_id for r in rules]
    assert "MSME_SEC_43B_H" in rule_ids
    assert "FAR_DEPN_SCH_II" in rule_ids
    assert "GST_RULE_37_17_5" in rule_ids
    assert "DEBTOR_DOUBTFUL_PROVISION" in rule_ids
    assert "REVENUE_CUTOFF_SA_560" in rule_ids

def test_msme_disallowance_calculation():
    rule = MSMEDisallowanceRule()
    context = {
        "subledger_aging": [
            {
                "party_name": "ABC Micro Engineering",
                "is_msme": True,
                "overdue_days": 60,
                "balance": Decimal("500000.00")
            },
            {
                "party_name": "XYZ Regular Supplier",
                "is_msme": False,
                "overdue_days": 90,
                "balance": Decimal("300000.00")
            }
        ]
    }
    corrections = rule.evaluate(context)
    assert len(corrections) == 1
    corr = corrections[0]
    assert corr["party_name"] == "ABC Micro Engineering"
    assert corr["severity"] == "HIGH"
    assert corr["disallowance_principal"] == 500000.00
    assert corr["amount"] > 0

def test_depreciation_variance_rule():
    rule = DepreciationScheduleIIRule()
    context = {
        "fixed_assets": [
            {
                "book_depreciation": Decimal("10000.00"),
                "calculated_schedule_ii_depreciation": Decimal("15000.00")
            }
        ]
    }
    corrections = rule.evaluate(context)
    assert len(corrections) == 1
    assert corrections[0]["amount"] == 5000.00

def test_gst_blocked_credit_rule():
    rule = GSTBlockedCreditReversalRule()
    context = {
        "gst_ineligible_records": [
            {
                "tax_amount": Decimal("18000.00"),
                "reason": "Vehicle purchase ITC blocked u/s 17(5)"
            }
        ]
    }
    corrections = rule.evaluate(context)
    assert len(corrections) == 1
    assert corrections[0]["amount"] == 18000.00
    assert corrections[0]["severity"] == "HIGH"
