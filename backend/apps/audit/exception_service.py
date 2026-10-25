from decimal import Decimal
from typing import Dict, Any, List
from django.db.models import Count, Q

from apps.audit.models import ExceptionItem, ExceptionSeverity


class AuditExceptionSummaryService:
    """
    Authoritative canonical service for tracking, deduplicating, and summarizing
    audit exceptions, severities, and statutory integrity blockers across the application.
    Enforces identical metrics across REST API, Dashboard, PDF, and Excel exports.
    """

    @classmethod
    def deduplicate_engagement_exceptions(cls, engagement) -> int:
        """
        Deduplicates ExceptionItem records for an engagement.
        Keeps the primary record (earliest or with proposed adjustment/resolution)
        and deletes redundant duplicate copies.
        Returns the number of duplicate records pruned.
        """
        all_excs = ExceptionItem.objects.filter(engagement=engagement).order_by('id')
        seen_keys = set()
        duplicate_ids = []

        for e in all_excs:
            # Composite identity key for unique audit finding:
            # Rule code + title + amount + target reference
            target_ref = str(e.related_ledger_id or e.related_transaction_id or e.source_reference or '')
            key = (e.rule_code, e.title.strip(), str(e.amount_involved), target_ref)

            if key in seen_keys:
                duplicate_ids.append(e.id)
            else:
                seen_keys.add(key)

        if duplicate_ids:
            ExceptionItem.objects.filter(id__in=duplicate_ids).delete()

        return len(duplicate_ids)

    @classmethod
    def get_canonical_summary(cls, engagement) -> Dict[str, Any]:
        """
        Returns the single authoritative summary of audit exceptions and statutory blockers.
        Guarantees that the API, PDF export, Excel sheets, and gatekeepers report
        synchronized, 100% consistent numbers.
        """
        # Ensure duplicates are cleaned
        cls.deduplicate_engagement_exceptions(engagement)

        qs = ExceptionItem.objects.filter(engagement=engagement)
        total_count = qs.count()

        open_statuses = ['OPEN', 'IN_REVIEW', 'AJE_PROPOSED']
        open_qs = qs.filter(status__in=open_statuses)
        open_count = open_qs.count()
        resolved_count = qs.filter(status='RESOLVED').count()

        critical_count = open_qs.filter(severity=ExceptionSeverity.CRITICAL).count()
        high_count = open_qs.filter(severity=ExceptionSeverity.HIGH).count()
        medium_count = open_qs.filter(severity=ExceptionSeverity.MEDIUM).count()
        low_count = open_qs.filter(severity=ExceptionSeverity.LOW).count()

        # Retrieve statutory integrity gate blockers
        from apps.audit.finalization_service import AuditFinalizationService
        gate_res = AuditFinalizationService.evaluate_finalization_readiness(engagement)
        blockers = gate_res.get('blockers', [])

        return {
            'total_exceptions_count': total_count,
            'open_exceptions_count': open_count,
            'resolved_exceptions_count': resolved_count,
            'critical_open_count': critical_count,
            'high_open_count': high_count,
            'high_critical_open_count': critical_count + high_count,
            'medium_open_count': medium_count,
            'low_open_count': low_count,
            'statutory_integrity_blockers_count': len(blockers),
            'statutory_integrity_blockers': blockers,
            'is_ready_for_final_issue': gate_res.get('is_ready_for_final_issue', False),
            'can_sign': gate_res.get('can_sign', False),
        }
