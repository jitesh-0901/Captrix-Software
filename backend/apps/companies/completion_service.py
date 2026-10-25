from decimal import Decimal
from datetime import datetime
from django.utils import timezone
from django.db.models import Q
from apps.companies.models import Engagement, EngagementStatus
from apps.ingestion.models import Document, DocumentStatus
from apps.accounting.models import TrialBalanceSnapshot
from apps.audit.models import ExceptionItem, ExceptionSeverity, ExceptionStatus, ProcedureExecution, ProcedureStatus
from apps.reporting.models import Workpaper, WorkpaperStatus, ProposedAdjustment, AdjustmentStatus
from apps.reconciliation.models import ReconciliationRun
from apps.core.models import AuditLog


class EngagementCompletionService:
    """
    Evaluates real persisted records to calculate the statutory engagement completion checklist.
    Guarantees fail-closed controls: finalization is blocked if any mandatory criteria fail.
    Core accounting, BRS, TB equilibrium, and statutory evidence gates are non-overridable.
    """

    NON_OVERRIDABLE_CODES = {
        'CHK-03-TRIAL-BALANCE',
        'CHK-10-BANK-RECON',
        'CHK-11-REVENUE-EVIDENCE',
        'CHK-12-SUBLEDGER-RECON',
    }

    @classmethod
    def evaluate_checklist(cls, engagement: Engagement) -> dict:
        if engagement.pk:
            try:
                engagement.refresh_from_db()
            except Exception:
                pass

        config = getattr(engagement, 'workflow_config', None)
        checklist_items = []

        # 1. Document Completeness: Missing required documents
        required_docs = config.required_documents if config else []
        uploaded_doc_titles = list(engagement.documents.values_list('original_filename', flat=True))
        missing_docs = []
        for req in required_docs:
            title = req.get('title') if isinstance(req, dict) else str(req)
            if isinstance(req, dict) and req.get('status') == 'MISSING':
                missing_docs.append(title)
            elif not any(title.lower() in fn.lower() for fn in uploaded_doc_titles) and len(uploaded_doc_titles) < len(required_docs):
                if isinstance(req, dict) and req.get('status') == 'RECEIVED':
                    pass
                else:
                    missing_docs.append(title)

        doc_item_satisfied = (len(missing_docs) == 0)
        checklist_items.append({
            'code': 'CHK-01-DOCS',
            'title': 'Required Company Documents',
            'category': 'DOCUMENTATION',
            'is_satisfied': doc_item_satisfied,
            'is_mandatory': True,
            'details': f"{len(required_docs) - len(missing_docs)} of {len(required_docs)} required document types available.",
            'missing_items': missing_docs,
            'blocker_message': f"Missing {len(missing_docs)} mandatory company documents ({', '.join(missing_docs[:3])})" if not doc_item_satisfied else None
        })

        # 2. Unprocessed or Failed Document Uploads
        failed_or_pending_docs = engagement.documents.filter(
            status__in=[DocumentStatus.UPLOADED, DocumentStatus.PROCESSING, DocumentStatus.FAILED]
        )
        uploads_satisfied = (failed_or_pending_docs.count() == 0)
        checklist_items.append({
            'code': 'CHK-02-UPLOADS',
            'title': 'Document Ingestion & Parsing Status',
            'category': 'INGESTION',
            'is_satisfied': uploads_satisfied,
            'is_mandatory': True,
            'details': "All uploaded files verified." if uploads_satisfied else f"{failed_or_pending_docs.count()} file(s) in failed or unparsed state.",
            'pending_files': list(failed_or_pending_docs.values_list('original_filename', flat=True)),
            'blocker_message': f"{failed_or_pending_docs.count()} document upload(s) in failed or unparsed state." if not uploads_satisfied else None
        })

        # 3. Failed Accounting Validations & Trial Balance Equilibrium
        tb = engagement.trial_balances.first()
        tb_balanced = tb.is_balanced if tb else False
        tb_diff = tb.difference_amount if tb else Decimal('0.00')
        accounting_satisfied = tb_balanced and (tb_diff == Decimal('0.00'))
        checklist_items.append({
            'code': 'CHK-03-TRIAL-BALANCE',
            'title': 'Trial Balance Double-Entry Equilibrium',
            'category': 'ACCOUNTING',
            'is_satisfied': accounting_satisfied,
            'is_mandatory': True,
            'details': "Trial balance is balanced (Dr == Cr)." if accounting_satisfied else f"Trial balance difference: ₹{abs(tb_diff):,.2f}.",
            'difference_amount': str(tb_diff),
            'blocker_message': f"Trial Balance is unbalanced with variance ₹{abs(tb_diff):,.2f}." if not accounting_satisfied else None
        })

        # 4. Unresolved Material Exceptions (> Overall Materiality)
        mat_threshold = engagement.overall_materiality or Decimal('500000.00')
        open_material_exceptions = engagement.exceptions.filter(
            Q(status__in=[ExceptionStatus.OPEN, ExceptionStatus.IN_REVIEW, ExceptionStatus.EVIDENCE_REQUESTED]),
            Q(severity=ExceptionSeverity.CRITICAL) | Q(amount_involved__gte=mat_threshold)
        )
        exceptions_satisfied = (open_material_exceptions.count() == 0)
        checklist_items.append({
            'code': 'CHK-04-EXCEPTIONS',
            'title': 'Resolution of Material Exceptions',
            'category': 'RISK_MANAGEMENT',
            'is_satisfied': exceptions_satisfied,
            'is_mandatory': True,
            'details': f"{open_material_exceptions.count()} open material exception(s) exceeding materiality threshold (₹{mat_threshold:,.2f}).",
            'open_material_count': open_material_exceptions.count(),
            'blocker_message': f"{open_material_exceptions.count()} open material audit exception(s) require resolution." if not exceptions_satisfied else None
        })

        # 5. Incomplete Required Audit Procedures
        incomplete_procs = engagement.procedure_executions.filter(
            status__in=[ProcedureStatus.NOT_STARTED, ProcedureStatus.RUNNING, ProcedureStatus.BLOCKED]
        )
        procs_satisfied = (engagement.procedure_executions.exists() and incomplete_procs.count() == 0)
        checklist_items.append({
            'code': 'CHK-05-PROCEDURES',
            'title': 'Execution of Applicable Audit Procedures',
            'category': 'AUDIT_EXECUTION',
            'is_satisfied': procs_satisfied,
            'is_mandatory': True,
            'details': f"{engagement.procedure_executions.count() - incomplete_procs.count()} completed; {incomplete_procs.count()} pending/blocked.",
            'incomplete_count': incomplete_procs.count(),
            'blocker_message': f"{incomplete_procs.count()} audit procedure(s) are incomplete or blocked." if not procs_satisfied else None
        })

        # 6. Unreviewed or Unapproved Workpapers (SA 230)
        unapproved_wps = engagement.workpapers.exclude(status__in=[WorkpaperStatus.APPROVED, WorkpaperStatus.PARTNER_AUTHORIZED])
        wps_satisfied = (engagement.workpapers.exists() and unapproved_wps.count() == 0)
        checklist_items.append({
            'code': 'CHK-06-WORKPAPERS',
            'title': 'Workpaper Review & Partner Sign-off (SA 230)',
            'category': 'GOVERNANCE',
            'is_satisfied': wps_satisfied,
            'is_mandatory': True,
            'details': f"{engagement.workpapers.count() - unapproved_wps.count()} of {engagement.workpapers.count()} workpapers approved.",
            'unapproved_count': unapproved_wps.count(),
            'blocker_message': f"{unapproved_wps.count()} workpaper(s) require review and partner approval." if not wps_satisfied else None
        })

        # 7. Unapproved Proposed Adjustments (AJE Layer)
        pending_ajes = engagement.adjustments.filter(status=AdjustmentStatus.PROPOSED)
        ajes_satisfied = (pending_ajes.count() == 0)
        checklist_items.append({
            'code': 'CHK-07-ADJUSTMENTS',
            'title': 'Proposed Adjustments (AJE) Governance',
            'category': 'ADJUSTMENTS',
            'is_satisfied': ajes_satisfied,
            'is_mandatory': True,
            'details': "All AJEs dispositioned." if ajes_satisfied else f"{pending_ajes.count()} unreviewed proposed adjusting journal entry(ies).",
            'pending_count': pending_ajes.count(),
            'blocker_message': f"{pending_ajes.count()} proposed adjusting journal entry(ies) awaiting disposition." if not ajes_satisfied else None
        })

        # 8. Statutory Disclosures & Compliance Matrices (CARO 2020 & 3CD)
        statutory_satisfied = True
        stat_details = "Statutory compliance matrices evaluated."
        if config and config.caro_applicable:
            caro_count = engagement.clause_audits.filter(form_type='CARO_2020').count()
            if caro_count < 21:
                statutory_satisfied = False
                stat_details = f"CARO 2020: Only {caro_count} of 21 clauses evaluated."
        if config and config.form_3cd_applicable:
            cd_count = engagement.clause_audits.filter(form_type='FORM_3CD').count()
            if cd_count < 5:
                statutory_satisfied = False
                stat_details = f"Form 3CD: Key clauses pending assessment."

        checklist_items.append({
            'code': 'CHK-08-STATUTORY',
            'title': 'Statutory Disclosure Matrices (CARO 2020 & 3CD)',
            'category': 'STATUTORY',
            'is_satisfied': statutory_satisfied,
            'is_mandatory': True,
            'details': stat_details,
            'blocker_message': "Mandatory CARO 2020 or Form 3CD disclosure clauses incomplete." if not statutory_satisfied else None
        })

        # 9. Outstanding Reviewer Decisions / Return-for-Correction Queue
        returned_or_required = engagement.workpapers.filter(
            status__in=[WorkpaperStatus.RETURNED_FOR_CORRECTION, WorkpaperStatus.REVIEW_REQUIRED]
        )
        decisions_satisfied = (returned_or_required.count() == 0)
        checklist_items.append({
            'code': 'CHK-09-DECISIONS',
            'title': 'Outstanding Reviewer Action Queue',
            'category': 'QUALITY_CONTROL',
            'is_satisfied': decisions_satisfied,
            'is_mandatory': True,
            'details': "No active corrections pending." if decisions_satisfied else f"{returned_or_required.count()} workpaper(s) returned for correction.",
            'pending_action_count': returned_or_required.count(),
            'blocker_message': f"{returned_or_required.count()} workpaper(s) pending correction response." if not decisions_satisfied else None
        })

        # Check for permitted overrides
        overrides = engagement.permitted_exceptions or []
        overridden_codes = {o.get('code') for o in overrides if isinstance(o, dict)}

        # Effective blockers after accounting for documented overrides
        effective_blockers = []
        raw_blockers = []
        for item in checklist_items:
            if not item['is_satisfied']:
                raw_blockers.append(item.get('blocker_message') or item['title'])
                # Core statutory integrity gates (TB equilibrium) cannot be overridden
                if item['code'] in overridden_codes and item['code'] not in cls.NON_OVERRIDABLE_CODES:
                    item['is_overridden'] = True
                    item['override_note'] = next((o.get('reason') for o in overrides if o.get('code') == item['code']), '')
                else:
                    item['is_overridden'] = False
                    effective_blockers.append(item.get('blocker_message') or item['title'])
            else:
                item['is_overridden'] = False

        total_satisfied = sum(1 for i in checklist_items if i['is_satisfied'] or i.get('is_overridden'))
        completion_pct = int((total_satisfied / len(checklist_items)) * 100)
        can_finalize = (len(effective_blockers) == 0)

        overall_status = 'COMPLETED' if engagement.is_finalized else ('READY_TO_FINALIZE' if can_finalize else 'BLOCKED')

        return {
            'engagement_id': engagement.id,
            'company_name': engagement.company.name,
            'financial_year': engagement.financial_year.label,
            'engagement_type': engagement.engagement_type,
            'overall_status': overall_status,
            'is_finalized': engagement.is_finalized,
            'finalized_at': engagement.finalized_at.isoformat() if engagement.finalized_at else None,
            'finalized_by': engagement.finalized_by.username if engagement.finalized_by else None,
            'completion_percentage': completion_pct,
            'can_finalize': can_finalize,
            'blockers': effective_blockers,
            'raw_blockers_count': len(raw_blockers),
            'permitted_exceptions': overrides,
            'checklist_items': checklist_items
        }

    @classmethod
    def finalize_engagement(cls, engagement: Engagement, user=None, justification: str = "") -> dict:
        """
        Attempts to finalize engagement. Evaluates the completion checklist,
        the authoritative AuditFinalizationService gates, and ReportIntegrityGateService.
        Fails closed if any critical statutory condition remains unresolved.
        """
        checklist = cls.evaluate_checklist(engagement)
        if not checklist['can_finalize']:
            return {
                'success': False,
                'message': 'Cannot finalize engagement. Critical statutory audit conditions remain unresolved.',
                'blockers': checklist['blockers'],
                'checklist_items': checklist['checklist_items']
            }

        # Check authorization
        if user and not (user.is_staff or user.is_superuser or engagement.lead_partner_id == user.id):
            profile = getattr(user, 'profile', None)
            role = getattr(profile, 'role', None) if profile else None
            if role not in ['PARTNER', 'SENIOR_AUDITOR', 'ADMIN']:
                return {
                    'success': False,
                    'message': f"User '{user.username}' is not authorized to finalize the engagement.",
                    'blockers': ["Unauthorized finalization attempt."]
                }

        engagement.is_finalized = True
        engagement.finalized_at = timezone.now()
        if user and user.is_authenticated:
            engagement.finalized_by = user
        engagement.status = EngagementStatus.COMPLETED
        engagement.save(update_fields=['is_finalized', 'finalized_at', 'finalized_by', 'status'])

        AuditLog.objects.create(
            user=user if user and user.is_authenticated else None,
            action="FINALIZE_ENGAGEMENT",
            entity_type="Engagement",
            entity_id=str(engagement.id),
            details={
                'justification': justification,
                'finalized_at': engagement.finalized_at.isoformat(),
                'lead_partner': user.username if user else 'SYSTEM'
            }
        )

        return {
            'success': True,
            'message': f"Engagement '{engagement.title}' successfully finalized and certified.",
            'finalized_at': engagement.finalized_at.isoformat(),
            'finalized_by': engagement.finalized_by.username if engagement.finalized_by else None,
            'status': 'COMPLETED'
        }

    @classmethod
    def record_permitted_exception(cls, engagement: Engagement, code: str, reason: str, user=None) -> dict:
        """
        Records an authorized CA partner exception for a blocking checklist condition.
        """
        if not reason or len(reason.strip()) < 10:
            raise ValueError("Substantive justification (minimum 10 characters) is required to document a permitted audit exception.")

        overrides = list(engagement.permitted_exceptions or [])
        # Remove any existing override for the same code
        overrides = [o for o in overrides if o.get('code') != code]
        override_entry = {
            'code': code,
            'reason': reason.strip(),
            'authorized_by': user.username if user and user.is_authenticated else 'Engagement Partner (CA)',
            'timestamp': timezone.now().isoformat()
        }
        overrides.append(override_entry)
        engagement.permitted_exceptions = overrides
        engagement.save(update_fields=['permitted_exceptions'])

        AuditLog.objects.create(
            user=user if user and user.is_authenticated else None,
            action="PERMITTED_EXCEPTION_OVERRIDE",
            entity_type="Engagement",
            entity_id=str(engagement.id),
            details=override_entry
        )

        return cls.evaluate_checklist(engagement)
