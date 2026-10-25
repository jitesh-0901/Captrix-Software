"""
Rule Registry for Audit Corrections and Proposed Journal Entries.
Allows developers and audit practitioners to add new statutory correction formulas
cleanly without altering core ingestion or database models.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class BaseAuditCorrectionRule(ABC):
    """
    Abstract base class for all statutory audit correction rules.
    """
    rule_id: str = "BASE_RULE"
    title: str = "Base Audit Correction"
    statutory_reference: str = "General Auditing Standard"
    category: str = "RECLASSIFICATION"  # RECLASSIFICATION, PROVISIONING, DISALLOWANCE, COMPLIANCE

    @abstractmethod
    def evaluate(self, engagement_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Evaluates audit records and generates recommended Proposed Journal Entries (PJEs)
        or correction notices.

        Returns list of dicts:
        [
            {
                "rule_id": self.rule_id,
                "title": self.title,
                "statutory_ref": self.statutory_reference,
                "severity": "HIGH" | "MEDIUM" | "LOW",
                "recommended_debit_ledger": "Interest Expense on MSME",
                "recommended_credit_ledger": "Interest Payable to MSME",
                "amount": Decimal("12500.00"),
                "narration": "Being interest accrued u/s 16 of MSMED Act 2006...",
                "pnl_impact": Decimal("-12500.00"),
                "balance_sheet_impact": Decimal("12500.00"),
                "audit_note": "..."
            }
        ]
        """
        pass


class CorrectionRuleRegistry:
    """
    Registry for dynamic loading and execution of audit correction rules.
    """
    def __init__(self):
        self._rules: Dict[str, BaseAuditCorrectionRule] = {}

    def register(self, rule_cls):
        """Decorator or method to register an audit correction rule."""
        rule_instance = rule_cls() if isinstance(rule_cls, type) else rule_cls
        self._rules[rule_instance.rule_id] = rule_instance
        logger.info(f"Registered audit correction rule: {rule_instance.rule_id} ({rule_instance.title})")
        return rule_cls

    def get_rule(self, rule_id: str) -> Optional[BaseAuditCorrectionRule]:
        return self._rules.get(rule_id)

    def get_all_rules(self) -> List[BaseAuditCorrectionRule]:
        return list(self._rules.values())

    def execute_all(self, engagement_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Executes all registered rules against the engagement context."""
        all_corrections = []
        for rule_id, rule in self._rules.items():
            try:
                corrections = rule.evaluate(engagement_context)
                if corrections:
                    all_corrections.extend(corrections)
            except Exception as e:
                logger.error(f"Error evaluating audit correction rule {rule_id}: {str(e)}", exc_info=True)
        return all_corrections


# Global singleton instance for the corrections package
correction_rule_registry = CorrectionRuleRegistry()
