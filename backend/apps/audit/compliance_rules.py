from decimal import Decimal
from datetime import date, datetime
from typing import Dict, Any, List, Optional
from apps.companies.models import EntityType, Engagement

class ComplianceRule:
    """
    Structured, versioned compliance rule with official legal citations,
    applicability conditions, input requirements, and deterministic evaluation.
    """
    def __init__(
        self,
        rule_id: str,
        title: str,
        description: str,
        applicable_entity_types: List[str],
        applicable_engagement_types: List[str],
        relevant_fy: str,
        effective_from: date,
        effective_to: Optional[date],
        statutory_act: str,
        section_or_clause: str,
        official_citation: str,
        rule_version: str,
        required_inputs: List[str],
        evaluator_fn: Any
    ):
        self.rule_id = rule_id
        self.title = title
        self.description = description
        self.applicable_entity_types = applicable_entity_types
        self.applicable_engagement_types = applicable_engagement_types
        self.relevant_fy = relevant_fy
        self.effective_from = effective_from
        self.effective_to = effective_to
        self.statutory_act = statutory_act
        self.section_or_clause = section_or_clause
        self.official_citation = official_citation
        self.rule_version = rule_version
        self.required_inputs = required_inputs
        self.evaluator_fn = evaluator_fn

    def is_applicable_to_engagement(self, engagement: Engagement) -> bool:
        company = engagement.company
        if self.applicable_entity_types and company.entity_type not in self.applicable_entity_types:
            return False
        if self.applicable_engagement_types and engagement.engagement_type not in self.applicable_engagement_types:
            return False
        return True

    def evaluate(self, engagement: Engagement, context_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_applicable_to_engagement(engagement):
            return {
                'rule_id': self.rule_id,
                'rule_version': self.rule_version,
                'is_applicable': False,
                'status': 'EXEMPT',
                'amount_involved': Decimal('0.00'),
                'finding': f"Exempt for entity type '{engagement.company.entity_type}' under {self.statutory_act} {self.section_or_clause}.",
                'citation': self.official_citation
            }

        # Check required inputs
        missing_inputs = [inp for inp in self.required_inputs if inp not in context_data or context_data[inp] is None]
        if missing_inputs:
            return {
                'rule_id': self.rule_id,
                'rule_version': self.rule_version,
                'is_applicable': True,
                'status': 'BLOCKED_MISSING_DATA',
                'missing_inputs': missing_inputs,
                'amount_involved': Decimal('0.00'),
                'finding': f"Prerequisite evidence missing ({', '.join(missing_inputs)}) to verify {self.title}.",
                'citation': self.official_citation
            }

        # Run deterministic evaluation
        return self.evaluator_fn(engagement, context_data, self)


class ComplianceRuleRegistry:
    """Central registry of versioned Indian statutory rules"""
    _rules: Dict[str, ComplianceRule] = {}

    @classmethod
    def register(cls, rule: ComplianceRule):
        cls._rules[rule.rule_id] = rule

    @classmethod
    def get_rule(cls, rule_id: str) -> Optional[ComplianceRule]:
        return cls._rules.get(rule_id)

    @classmethod
    def get_applicable_rules(cls, engagement: Engagement) -> List[ComplianceRule]:
        return [r for r in cls._rules.values() if r.is_applicable_to_engagement(engagement)]

    @classmethod
    def evaluate_all(cls, engagement: Engagement, context_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        results = []
        for rule in cls.get_applicable_rules(engagement):
            res = rule.evaluate(engagement, context_data)
            results.append(res)
        return results


# -------------------------------------------------------------------------
# Rule Evaluator Implementations
# -------------------------------------------------------------------------

def eval_sec_40a3(engagement, data, rule: ComplianceRule):
    """Section 40A(3): Disallowance of cash payments > 10,000 INR"""
    cash_txns = data.get('cash_transactions', [])
    violations = []
    tot_amt = Decimal('0.00')

    for t in cash_txns:
        amt = Decimal(str(t.get('amount', 0)))
        if amt > Decimal('10000.00'):
            tot_amt += amt
            violations.append(t)

    is_compliant = len(violations) == 0
    return {
        'rule_id': rule.rule_id,
        'rule_version': rule.rule_version,
        'is_applicable': True,
        'status': 'COMPLIANT' if is_compliant else 'EXCEPTION_NOTED',
        'amount_involved': tot_amt,
        'violations_count': len(violations),
        'finding': f"Identified {len(violations)} cash transactions exceeding ₹10,000 threshold totaling ₹{tot_amt:,.2f}." if not is_compliant else "No cash payments exceeding ₹10,000 identified.",
        'citation': rule.official_citation,
        'recommended_action': "Disallow under Section 40A(3) in Tax Audit Form 3CD Clause 21(d)." if not is_compliant else "No reporting required."
    }

def eval_sec_43bh_msme(engagement, data, rule: ComplianceRule):
    """Section 43B(h): Overdue payables to Micro & Small Enterprises > 45 days"""
    payables = data.get('payables_aging', [])
    overdue_items = []
    tot_overdue = Decimal('0.00')

    for p in payables:
        is_micro_small = p.get('msme_type') in ['MICRO', 'SMALL']
        days = int(p.get('overdue_days', 0))
        amt = Decimal(str(p.get('outstanding_amount', 0)))
        # Statutory threshold: 45 days if written agreement, 15 days if no agreement
        has_agreement = p.get('has_written_agreement', True)
        threshold = 45 if has_agreement else 15

        if is_micro_small and days > threshold:
            tot_overdue += amt
            overdue_items.append(p)

    is_compliant = len(overdue_items) == 0
    return {
        'rule_id': rule.rule_id,
        'rule_version': rule.rule_version,
        'is_applicable': True,
        'status': 'COMPLIANT' if is_compliant else 'EXCEPTION_NOTED',
        'amount_involved': tot_overdue,
        'violations_count': len(overdue_items),
        'finding': (
            f"Found {len(overdue_items)} invoices payable to Micro/Small enterprises outstanding beyond statutory MSMED threshold (₹{tot_overdue:,.2f})."
            if not is_compliant else "All trade payables to Micro and Small enterprises paid within statutory MSMED limits."
        ),
        'citation': rule.official_citation,
        'recommended_action': "Disallow under Section 43B(h) for current FY; allowable in year of actual payment. Report in Form 3CD Clause 22." if not is_compliant else "No disallowance required."
    }

def eval_caro_ppe_title(engagement, data, rule: ComplianceRule):
    """CARO 2020 Clause 3(i)(c): Immovable property title deeds verification"""
    company = engagement.company
    if company.entity_type in [EntityType.LLP, EntityType.PARTNERSHIP, EntityType.PROPRIETORSHIP]:
        return {
            'rule_id': rule.rule_id,
            'rule_version': rule.rule_version,
            'is_applicable': False,
            'status': 'EXEMPT',
            'amount_involved': Decimal('0.00'),
            'finding': f"CARO 2020 is not applicable to non-corporate entity '{company.entity_type}'.",
            'citation': rule.official_citation
        }

    far_items = data.get('far_immovable_properties', [])
    unverified_titles = [p for p in far_items if not p.get('title_deed_in_company_name', True)]
    tot_unverified = sum((Decimal(str(p.get('carrying_amount', 0))) for p in unverified_titles), Decimal('0.00'))

    is_compliant = len(unverified_titles) == 0
    return {
        'rule_id': rule.rule_id,
        'rule_version': rule.rule_version,
        'is_applicable': True,
        'status': 'COMPLIANT' if is_compliant else 'EXCEPTION_NOTED',
        'amount_involved': tot_unverified,
        'violations_count': len(unverified_titles),
        'finding': f"{len(unverified_titles)} immovable properties have title deeds not held in company name (Gross value: ₹{tot_unverified:,.2f})." if not is_compliant else "All immovable property title deeds are held in company name.",
        'citation': rule.official_citation,
        'recommended_action': "Report details in CARO 2020 Order Clause 3(i)(c) table format." if not is_compliant else "Standard unmodified reporting."
    }

def eval_caro_statutory_dues(engagement, data, rule: ComplianceRule):
    """CARO 2020 Clause 3(vii)(a): Undisputed statutory dues > 6 months"""
    dues = data.get('statutory_dues', [])
    overdue_6m = []
    tot_amt = Decimal('0.00')

    for d in dues:
        days = int(d.get('overdue_days', 0))
        amt = Decimal(str(d.get('amount', 0)))
        if days > 180 and not d.get('is_disputed', False):
            tot_amt += amt
            overdue_6m.append(d)

    is_compliant = len(overdue_6m) == 0
    return {
        'rule_id': rule.rule_id,
        'rule_version': rule.rule_version,
        'is_applicable': True,
        'status': 'COMPLIANT' if is_compliant else 'EXCEPTION_NOTED',
        'amount_involved': tot_amt,
        'violations_count': len(overdue_6m),
        'finding': f"{len(overdue_6m)} undisputed statutory dues outstanding for more than 6 months totaling ₹{tot_amt:,.2f}." if not is_compliant else "No undisputed statutory dues outstanding exceeding 6 months.",
        'citation': rule.official_citation,
        'recommended_action': "Disclose in CARO 2020 Clause 3(vii)(a) specifying nature of fund, amount, and date from which payable." if not is_compliant else "Report undisputed dues as regular."
    }

def eval_tds_chapter_xvii_b(engagement, data, rule: ComplianceRule):
    """Section 40(a)(ia): 30% disallowance for non-deduction of TDS on resident payments"""
    expenses = data.get('tds_scrutiny_expenses', [])
    non_deductions = []
    tot_disallowance = Decimal('0.00')

    for e in expenses:
        if e.get('tds_applicable', True) and not e.get('tds_deducted', False):
            amt = Decimal(str(e.get('amount', 0)))
            disallow = amt * Decimal('0.30')
            tot_disallowance += disallow
            non_deductions.append(e)

    is_compliant = len(non_deductions) == 0
    return {
        'rule_id': rule.rule_id,
        'rule_version': rule.rule_version,
        'is_applicable': True,
        'status': 'COMPLIANT' if is_compliant else 'EXCEPTION_NOTED',
        'amount_involved': tot_disallowance,
        'violations_count': len(non_deductions),
        'finding': f"{len(non_deductions)} expense payments subject to TDS without tax deduction. 30% statutory disallowance = ₹{tot_disallowance:,.2f}." if not is_compliant else "TDS deduction verified across sampled expenditure.",
        'citation': rule.official_citation,
        'recommended_action': "Disallow 30% of expenditure under Section 40(a)(ia) in Form 3CD Clause 21(b)." if not is_compliant else "No disallowance required."
    }


# Register Standard Rules
ComplianceRuleRegistry.register(ComplianceRule(
    rule_id="RULE_IN_TAX_40A3_v24",
    title="Section 40A(3) Cash Payments Threshold",
    description="Prohibits aggregate cash payments exceeding ₹10,000 per person per day for business expenditure.",
    applicable_entity_types=[],
    applicable_engagement_types=['STATUTORY', 'TAX_AUDIT', 'INTERNAL', 'LLP_AUDIT'],
    relevant_fy="FY 2024-25",
    effective_from=date(2017, 4, 1),
    effective_to=None,
    statutory_act="Income Tax Act, 1961",
    section_or_clause="Section 40A(3) / Rule 6DD",
    official_citation="Income Tax Act 1961 Section 40A(3) read with Form 3CD Clause 21(d)",
    rule_version="v24.1",
    required_inputs=['cash_transactions'],
    evaluator_fn=eval_sec_40a3
))

ComplianceRuleRegistry.register(ComplianceRule(
    rule_id="RULE_IN_TAX_43BH_v24",
    title="Section 43B(h) MSMED Act Overdue Payables",
    description="Enforces actual payment to Micro and Small enterprises within 45 days (or 15 days), failing which expense is disallowed in the year of accrual.",
    applicable_entity_types=[],
    applicable_engagement_types=['STATUTORY', 'TAX_AUDIT', 'INTERNAL', 'LLP_AUDIT'],
    relevant_fy="FY 2024-25",
    effective_from=date(2023, 4, 1),
    effective_to=None,
    statutory_act="Income Tax Act, 1961 & MSMED Act, 2006",
    section_or_clause="Section 43B(h) read with MSMED Act Sec 15",
    official_citation="Finance Act 2023 insertion of Section 43B(h) and Form 3CD Clause 22",
    rule_version="v24.1",
    required_inputs=['payables_aging'],
    evaluator_fn=eval_sec_43bh_msme
))

ComplianceRuleRegistry.register(ComplianceRule(
    rule_id="RULE_IN_CO_CARO_3I_v24",
    title="CARO 2020 Clause 3(i) Fixed Assets & Title Deeds",
    description="Requires auditor to report whether proper records of PPE are kept and title deeds of immovable properties are in company name.",
    applicable_entity_types=['PVT_LTD', 'PUB_LTD'],
    applicable_engagement_types=['STATUTORY'],
    relevant_fy="FY 2024-25",
    effective_from=date(2020, 2, 25),
    effective_to=None,
    statutory_act="Companies (Auditor's Report) Order, 2020",
    section_or_clause="Clause 3(i)",
    official_citation="MCA Notification S.O. 849(E) CARO 2020 Clause 3(i)",
    rule_version="v24.1",
    required_inputs=['far_immovable_properties'],
    evaluator_fn=eval_caro_ppe_title
))

ComplianceRuleRegistry.register(ComplianceRule(
    rule_id="RULE_IN_CO_CARO_3VII_v24",
    title="CARO 2020 Clause 3(vii) Statutory Dues Aging",
    description="Requires reporting of undisputed statutory dues outstanding for more than six months from the date they became payable.",
    applicable_entity_types=['PVT_LTD', 'PUB_LTD'],
    applicable_engagement_types=['STATUTORY'],
    relevant_fy="FY 2024-25",
    effective_from=date(2020, 2, 25),
    effective_to=None,
    statutory_act="Companies (Auditor's Report) Order, 2020",
    section_or_clause="Clause 3(vii)",
    official_citation="MCA Notification S.O. 849(E) CARO 2020 Clause 3(vii)(a)",
    rule_version="v24.1",
    required_inputs=['statutory_dues'],
    evaluator_fn=eval_caro_statutory_dues
))

ComplianceRuleRegistry.register(ComplianceRule(
    rule_id="RULE_IN_TAX_40AIA_v24",
    title="Section 40(a)(ia) TDS Non-Deduction 30% Disallowance",
    description="30% of any sum payable to a resident on which TDS is deductible but not deducted is disallowed in current year.",
    applicable_entity_types=[],
    applicable_engagement_types=['STATUTORY', 'TAX_AUDIT', 'INTERNAL', 'LLP_AUDIT'],
    relevant_fy="FY 2024-25",
    effective_from=date(2014, 4, 1),
    effective_to=None,
    statutory_act="Income Tax Act, 1961",
    section_or_clause="Section 40(a)(ia) / Chapter XVII-B",
    official_citation="Income Tax Act 1961 Section 40(a)(ia) and Form 3CD Clause 21(b)",
    rule_version="v24.1",
    required_inputs=['tds_scrutiny_expenses'],
    evaluator_fn=eval_tds_chapter_xvii_b
))
