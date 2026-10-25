"""
Dedicated API Views for Audit Corrections & Adjustments.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from apps.companies.models import Engagement
from .engine import AuditCorrectionEngine
from .registry import correction_rule_registry

class AuditCorrectionsScheduleView(APIView):
    """
    GET /api/audit/corrections/schedule/?engagement=<id>
    Returns the comprehensive schedule of proposed audit corrections,
    journal entries, and P&L/Balance Sheet impact for an engagement.
    """
    def get(self, request):
        engagement_id = request.query_params.get('engagement')
        engagement = None
        if engagement_id:
            engagement = Engagement.objects.filter(id=engagement_id).first()
        if not engagement:
            engagement = Engagement.objects.first()

        if not engagement:
            return Response({
                "error": "No engagement found",
                "proposed_journal_entries": [],
                "financial_impact": {"net_profit_impact": 0.0, "balance_sheet_impact": 0.0}
            }, status=status.HTTP_200_OK)

        data = AuditCorrectionEngine.evaluate_engagement(engagement)
        return Response(data, status=status.HTTP_200_OK)


class AuditCorrectionRulesView(APIView):
    """
    GET /api/audit/corrections/rules/
    Returns list of all active statutory correction rules in the registry.
    """
    def get(self, request):
        rules = correction_rule_registry.get_all_rules()
        data = [
            {
                "rule_id": r.rule_id,
                "title": r.title,
                "statutory_reference": r.statutory_reference,
                "category": r.category
            }
            for r in rules
        ]
        return Response({"active_rules_count": len(data), "rules": data}, status=status.HTTP_200_OK)
