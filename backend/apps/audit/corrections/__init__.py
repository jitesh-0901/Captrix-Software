"""
Captrix AI - Statutory Audit Correction & Adjustments Package
Dedicated, decoupled package for managing audit corrections, proposed journal entries (AJEs),
and statutory reclassifications (Companies Act 2013, Income Tax Act 1961, GST Acts).
"""

from .engine import AuditCorrectionEngine
from .registry import correction_rule_registry, BaseAuditCorrectionRule
from .rules import (
    MSMEDisallowanceRule,
    DepreciationScheduleIIRule,
    GSTBlockedCreditReversalRule,
    DebtorProvisioningRule,
    RevenueCutoffRule
)

__all__ = [
    'AuditCorrectionEngine',
    'correction_rule_registry',
    'BaseAuditCorrectionRule',
    'MSMEDisallowanceRule',
    'DepreciationScheduleIIRule',
    'GSTBlockedCreditReversalRule',
    'DebtorProvisioningRule',
    'RevenueCutoffRule',
]
