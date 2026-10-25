from decimal import Decimal
from typing import Dict, Any, List, Optional
from django.utils import timezone
from django.db.models import Q
from apps.companies.models import Engagement, EngagementStatus, EntityType
from apps.ingestion.models import Document, DocumentStatus
from apps.accounting.models import LedgerAccount, TrialBalanceSnapshot, ScheduleIIIGroup
from apps.accounting.services import TrialBalanceService
from apps.audit.models import ExceptionItem, ExceptionSeverity, ExceptionStatus, ProcedureExecution, ProcedureStatus
from apps.reporting.models import Workpaper, WorkpaperStatus, ProposedAdjustment, AdjustmentStatus
from apps.reconciliation.models import ReconciliationRun, ReconciliationType
from apps.core.models import AuditLog


class AuditFinalizationService:
    """
    AUTHORITATIVE STATUTORY AUDIT FINALIZATION GATE SERVICE
    Inspects validated financial data, evidence inventory, materiality policy,
    reconciliation results, exceptions, workpapers, and authorization records.
    Prevents finalization whenever critical conditions remain unresolved.
    """

    @classmethod
    def evaluate_finalization_readiness(
        cls,
        engagement: Engagement,
        user=None,
        ca_credentials: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive evaluation of all 9 finalization gates.
        Returns:
            {
                'can_finalize': bool,
                'blockers': list[str],
                'warnings': list[str],
                'gate_results': dict,
                'materiality': dict,
            }
        """
        if engagement.pk:
            try:
                engagement.refresh_from_db()
            except Exception:
                pass

        blockers: List[str] = []
        warnings: List[str] = []
        gate_results: Dict[str, Any] = {}

        # -------------------------------------------------------------
        # Materiality Policy Determination
        # -------------------------------------------------------------
        overall_mat = engagement.overall_materiality or Decimal('500000.00')
        perf_mat = engagement.performance_materiality or (overall_mat * Decimal('0.75')).quantize(Decimal('0.01'))
        trivial_threshold = engagement.clearly_trivial_threshold or (overall_mat * Decimal('0.05')).quantize(Decimal('0.01'))

        materiality_context = {
            'overall_materiality': str(overall_mat),
            'performance_materiality': str(perf_mat),
            'clearly_trivial_threshold': str(trivial_threshold),
            'benchmark': engagement.materiality_benchmark or 'PBT',
            'benchmark_percentage': str(engagement.benchmark_percentage or Decimal('5.00'))
        }

        # -------------------------------------------------------------
        # GATE 1: Bank Reconciliation Resolved Gate
        # -------------------------------------------------------------
        brs = ReconciliationRun.objects.filter(engagement=engagement, recon_type='BANK').first()
        brs_passed = False
        brs_details = ""

        if not brs:
            brs_details = "Bank reconciliation has not been performed (no bank statement uploaded or reconciliation run)."
            blockers.append(brs_details)
        else:
            unrec_diff = abs(Decimal(str(brs.unreconciled_difference or '0.00')))
            unmatched = brs.unmatched_count
            summary = brs.summary_data or {}
            stale_cheques = summary.get('stale_cheques_count', 0)

            # Check if stale cheques have been resolved by adjusting journal entry
            stale_resolved = False
            if stale_cheques > 0:
                stale_ajes = engagement.adjustments.filter(
                    Q(title__icontains='stale') | Q(reason__icontains='stale'),
                    is_posted=True
                )
                if stale_ajes.exists():
                    stale_resolved = True

            if brs.status != 'BALANCED' or unrec_diff >= Decimal('0.01') or unmatched > 0 or (stale_cheques > 0 and not stale_resolved):
                reasons = []
                if unrec_diff >= Decimal('0.01'):
                    reasons.append(f"unreconciled variance of ₹{unrec_diff:,.2f}")
                if unmatched > 0:
                    reasons.append(f"{unmatched} unmatched/timing items")
                if stale_cheques > 0 and not stale_resolved:
                    reasons.append(f"{stale_cheques} stale cheques (>90 days) requiring reversal")

                brs_details = f"Bank reconciliation unresolved: Status is {brs.status} with {'; '.join(reasons)}."
                blockers.append(brs_details)
            else:
                brs_passed = True
                brs_details = "Bank reconciliation fully resolved with ₹0.00 variance and zero open items."

        gate_results['bank_reconciliation'] = {
            'passed': brs_passed,
            'status': brs.status if brs else 'NOT_PERFORMED',
            'details': brs_details
        }

        # -------------------------------------------------------------
        # GATE 2: Material Ledger / Subledger Difference Gate
        # -------------------------------------------------------------
        subledger_issues = []
        tb = engagement.trial_balances.first()
        fin_statements = None
        if tb and tb.accounts_snapshot:
            fin_statements = TrialBalanceService.compile_financial_statements(tb.accounts_snapshot)

        # Check Trade Payables GL vs Creditors Subledger
        creditors_aging = engagement.aging_items.filter(item_type='PAYABLE')
        if creditors_aging.exists() and fin_statements:
            subledger_payables = sum((p.outstanding_amount for p in creditors_aging), Decimal('0.00'))
            cl = fin_statements.get('balance_sheet', {}).get('equity_and_liabilities', {}).get('current_liabilities', {})
            gl_payables = Decimal(str(cl.get('trade_payables', '0.00')))
            payables_diff = abs(gl_payables - subledger_payables)
            if payables_diff > perf_mat:
                subledger_issues.append(
                    f"Material Trade Payables subledger variance: GL control balance ₹{gl_payables:,.2f} differs from subledger total ₹{subledger_payables:,.2f} by ₹{payables_diff:,.2f} (exceeds performance materiality ₹{perf_mat:,.2f})."
                )

        # Check Trade Receivables GL vs Debtors Subledger
        debtors_aging = engagement.aging_items.filter(item_type='RECEIVABLE')
        if debtors_aging.exists() and fin_statements:
            subledger_receivables = sum((d.outstanding_amount for d in debtors_aging), Decimal('0.00'))
            ca = fin_statements.get('balance_sheet', {}).get('assets', {}).get('current_assets', {})
            gl_receivables = Decimal(str(ca.get('trade_receivables', '0.00')))
            receivables_diff = abs(gl_receivables - subledger_receivables)
            if receivables_diff > perf_mat:
                subledger_issues.append(
                    f"Material Trade Receivables subledger variance: GL control balance ₹{gl_receivables:,.2f} differs from subledger total ₹{subledger_receivables:,.2f} by ₹{receivables_diff:,.2f} (exceeds performance materiality ₹{perf_mat:,.2f})."
                )

        # Check Fixed Assets Register vs Gross Block GL
        fixed_assets = engagement.fixed_assets.all()
        if fixed_assets.exists() and fin_statements:
            far_gross = sum((fa.original_cost for fa in fixed_assets), Decimal('0.00'))
            nca = fin_statements.get('balance_sheet', {}).get('assets', {}).get('non_current_assets', {})
            gl_ppe = Decimal(str(nca.get('property_plant_and_equipment', nca.get('property_plant_equipment', '0.00'))))
            far_diff = abs(gl_ppe - far_gross)
            if far_diff > perf_mat:
                subledger_issues.append(
                    f"Material Fixed Assets Register variance: GL Gross Block ₹{gl_ppe:,.2f} differs from FAR total ₹{far_gross:,.2f} by ₹{far_diff:,.2f} (exceeds performance materiality ₹{perf_mat:,.2f})."
                )

        subledger_passed = len(subledger_issues) == 0
        if not subledger_passed:
            blockers.extend(subledger_issues)

        gate_results['control_subledger_reconciliation'] = {
            'passed': subledger_passed,
            'issues': subledger_issues,
            'details': "All control-to-subledger differences are within performance materiality." if subledger_passed else "; ".join(subledger_issues)
        }

        # -------------------------------------------------------------
        # GATE 3: Required Revenue Evidence Gate
        # -------------------------------------------------------------
        revenue_val = Decimal('0.00')
        if fin_statements:
            pl = fin_statements.get('profit_and_loss', {})
            revenue_val = Decimal(str(pl.get('total_revenue', pl.get('revenue', {}).get('revenue_from_operations', '0.00'))))

        revenue_issues = []
        uploaded_doc_records = list(engagement.documents.values('document_type', 'original_filename', 'status'))
        verified_filenames = [
            str(d.get('original_filename', '')).lower()
            for d in uploaded_doc_records
            if str(d.get('status', '')).upper() == 'VERIFIED'
        ]
        verified_types = {
            str(d.get('document_type', '')).upper()
            for d in uploaded_doc_records
            if str(d.get('status', '')).upper() == 'VERIFIED'
        }

        has_gstr1 = any('gstr-1' in f or 'gstr1' in f for f in verified_filenames)
        has_eway = any('eway' in f or 'e-way' in f or 'e_way' in f for f in verified_filenames)
        has_sales_reg = ('SALES_REGISTER' in verified_types) or any('sales' in f for f in verified_filenames)

        if revenue_val > Decimal('0.00'):
            if not (has_gstr1 or has_sales_reg):
                revenue_issues.append(
                    f"Required revenue verification evidence missing: Turnover of ₹{revenue_val:,.2f} requires GSTR-1 outward returns or verified Sales Register for substantive cut-off and occurrence testing."
                )

        revenue_passed = len(revenue_issues) == 0
        if not revenue_passed:
            blockers.extend(revenue_issues)

        gate_results['revenue_evidence'] = {
            'passed': revenue_passed,
            'revenue_amount': str(revenue_val),
            'has_gstr1': has_gstr1,
            'has_sales_register': has_sales_reg,
            'has_eway': has_eway,
            'issues': revenue_issues
        }

        # -------------------------------------------------------------
        # GATE 4: Duplicate or Unapproved Adjusting Journal Entries (AJE) Gate
        # -------------------------------------------------------------
        aje_issues = []
        all_ajes = engagement.adjustments.all()

        # Check for unapproved / pending proposed adjustments
        pending_ajes = all_ajes.filter(status=AdjustmentStatus.PROPOSED)
        if pending_ajes.exists():
            aje_issues.append(
                f"{pending_ajes.count()} proposed adjusting journal entry(ies) remain unapproved by partner."
            )

        # Check for duplicate adjustments
        seen_ajes = {}
        for aje in all_ajes:
            # Hash key based on debit amount and first account
            key = (str(aje.total_debit), aje.title.strip().lower()[:25])
            if key in seen_ajes:
                prior = seen_ajes[key]
                aje_issues.append(
                    f"Duplicate adjustment detected: '{aje.adjustment_number}' ({aje.title}) duplicates '{prior.adjustment_number}' ({prior.title}) for ₹{aje.total_debit:,.2f}."
                )
            else:
                seen_ajes[key] = aje

        aje_passed = len(aje_issues) == 0
        if not aje_passed:
            blockers.extend(aje_issues)

        gate_results['adjustments_governance'] = {
            'passed': aje_passed,
            'total_adjustments': all_ajes.count(),
            'pending_count': pending_ajes.count(),
            'issues': aje_issues
        }

        # -------------------------------------------------------------
        # GATE 5: Material Financial Statement Inconsistency Gate
        # -------------------------------------------------------------
        fs_issues = []
        tb_is_balanced = tb.is_balanced if tb else False
        tb_diff = abs(Decimal(str(tb.difference_amount or '0.00'))) if tb else Decimal('0.00')

        if not tb:
            fs_issues.append("Trial Balance record is missing.")
        elif not tb_is_balanced or tb_diff >= Decimal('0.01'):
            fs_issues.append(f"Trial Balance is unbalanced: Variance of ₹{tb_diff:,.2f} violates double-entry equality.")

        if fin_statements:
            bs = fin_statements.get('balance_sheet', {})
            tot_assets = Decimal(str(bs.get('assets', {}).get('total_assets', '0.00')))
            tot_eq_liab = Decimal(str(bs.get('equity_and_liabilities', {}).get('total_equity_and_liabilities', '0.00')))
            bs_diff = abs(tot_assets - tot_eq_liab)
            if bs_diff >= Decimal('1.00'):
                fs_issues.append(
                    f"Balance Sheet disequilibrium: Total Assets (₹{tot_assets:,.2f}) ≠ Total Equity & Liabilities (₹{tot_eq_liab:,.2f}) with variance ₹{bs_diff:,.2f}."
                )

        # Check for open critical audit exceptions
        terminal_statuses = [ExceptionStatus.RESOLVED, ExceptionStatus.AJE_POSTED]
        open_critical = engagement.exceptions.filter(
            severity=ExceptionSeverity.CRITICAL
        ).exclude(status__in=terminal_statuses).count()
        if open_critical > 0:
            fs_issues.append(f"{open_critical} critical audit exception(s) remain unresolved.")

        # Check for open material exceptions (> performance materiality)
        open_material = engagement.exceptions.filter(
            amount_involved__gte=perf_mat
        ).exclude(status__in=terminal_statuses).count()
        if open_material > 0:
            fs_issues.append(
                f"{open_material} high-value audit exception(s) exceeding performance materiality (₹{perf_mat:,.2f}) remain unresolved."
            )

        fs_passed = len(fs_issues) == 0
        if not fs_passed:
            blockers.extend(fs_issues)

        gate_results['financial_statements_consistency'] = {
            'passed': fs_passed,
            'tb_balanced': tb_is_balanced,
            'tb_difference': str(tb_diff),
            'issues': fs_issues
        }

        # -------------------------------------------------------------
        # GATE 6: Incomplete Document Extraction Gate
        # -------------------------------------------------------------
        extraction_issues = []
        failed_or_processing_docs = engagement.documents.filter(
            status__in=[DocumentStatus.UPLOADED, DocumentStatus.PROCESSING, DocumentStatus.FAILED]
        )
        if failed_or_processing_docs.exists():
            extraction_issues.append(
                f"{failed_or_processing_docs.count()} uploaded document(s) in failed, unparsed, or rejected state."
            )

        # Check if documents have zero extracted records
        empty_docs = engagement.documents.filter(status=DocumentStatus.VERIFIED, extracted_records__isnull=True)
        if empty_docs.exists():
            extraction_issues.append(
                f"{empty_docs.count()} verified document(s) contain zero extracted records."
            )

        extraction_passed = len(extraction_issues) == 0
        if not extraction_passed:
            blockers.extend(extraction_issues)

        gate_results['document_extraction'] = {
            'passed': extraction_passed,
            'total_documents': engagement.documents.count(),
            'issues': extraction_issues
        }

        # -------------------------------------------------------------
        # GATE 7: Missing Required Workpaper Review (SA 230) Gate
        # -------------------------------------------------------------
        wp_issues = []
        total_wps = engagement.workpapers.count()
        if total_wps == 0:
            wp_issues.append("No SA 230 audit working papers have been generated for this engagement.")
        else:
            unapproved_wps = engagement.workpapers.exclude(
                status__in=[WorkpaperStatus.APPROVED, WorkpaperStatus.PARTNER_AUTHORIZED]
            ).count()
            if unapproved_wps > 0:
                wp_issues.append(
                    f"{unapproved_wps} of {total_wps} SA 230 audit working papers remain unapproved by partner."
                )

        wp_passed = len(wp_issues) == 0
        if not wp_passed:
            blockers.extend(wp_issues)

        gate_results['workpaper_review'] = {
            'passed': wp_passed,
            'total_workpapers': total_wps,
            'issues': wp_issues
        }

        # -------------------------------------------------------------
        # GATE 8: Authorization & Partner Credentials Gate
        # -------------------------------------------------------------
        auth_issues = []
        is_authorized_partner = False

        if user is None or not user.is_authenticated:
            auth_issues.append("User is unauthenticated. Finalization requires an authenticated session.")
        else:
            profile = getattr(user, 'profile', None)
            user_role = getattr(profile, 'role', None) if profile else None
            is_staff = user.is_staff or user.is_superuser
            is_partner_role = user_role in ['PARTNER', 'SENIOR_AUDITOR', 'ADMIN']
            is_lead = (engagement.lead_partner_id == user.id)

            if is_staff or is_partner_role or is_lead:
                is_authorized_partner = True
            else:
                auth_issues.append(
                    f"User '{user.username}' does not hold an authorized Senior Audit Partner or Engagement Lead role."
                )

        auth_passed = is_authorized_partner and len(auth_issues) == 0
        if not auth_passed:
            blockers.extend(auth_issues)

        gate_results['authorization_gate'] = {
            'passed': auth_passed,
            'user': user.username if user and user.is_authenticated else 'Anonymous',
            'is_authorized_partner': is_authorized_partner,
            'issues': auth_issues
        }

        # -------------------------------------------------------------
        # Permitted Exceptions / Overrides Handling
        # Core accounting integrity, unresolved bank reconciliation, unbalanced TB,
        # missing mandatory revenue evidence, and material subledger variances are
        # non-overridable statutory gates per ICAI Standards on Auditing (SA 700 / SA 705).
        # -------------------------------------------------------------
        NON_OVERRIDABLE_PATTERNS = [
            'bank reconciliation unresolved',
            'unreconciled variance',
            'unmatched/timing items',
            'trial balance is unbalanced',
            'trial balance record is missing',
            'balance sheet disequilibrium',
            'required revenue verification evidence missing',
            'material trade payables subledger variance',
            'material trade receivables subledger variance',
            'material fixed assets register variance',
            'critical audit exception',
        ]

        overrides = engagement.permitted_exceptions or []
        overridden_codes = {o.get('code') for o in overrides if isinstance(o, dict)}

        # Filter out blockers that have an authorized override (if permissible)
        effective_blockers = []
        for b in blockers:
            b_lower = b.lower()
            is_non_overridable = any(pattern in b_lower for pattern in NON_OVERRIDABLE_PATTERNS)
            if is_non_overridable:
                effective_blockers.append(b)
                continue

            # Check if any permitted override code matches an overridable procedural blocker
            is_ov = False
            for code in overridden_codes:
                if code and code.lower() in b_lower:
                    is_ov = True
                    break
            if not is_ov:
                effective_blockers.append(b)

        can_finalize = (len(effective_blockers) == 0)

        return {
            'engagement_id': engagement.id,
            'company_name': engagement.company.name,
            'can_finalize': can_finalize,
            'overall_status': 'COMPLETED' if engagement.is_finalized else ('READY_TO_FINALIZE' if can_finalize else 'BLOCKED'),
            'blockers': effective_blockers,
            'raw_blockers_count': len(blockers),
            'gate_results': gate_results,
            'materiality': materiality_context,
            'permitted_exceptions': overrides
        }

    @classmethod
    def finalize_engagement(cls, engagement: Engagement, user=None, justification: str = "") -> Dict[str, Any]:
        """
        Authoritatively finalizes the audit engagement.
        Fails closed if any blocker remains.
        """
        readiness = cls.evaluate_finalization_readiness(engagement, user=user)
        if not readiness['can_finalize']:
            return {
                'success': False,
                'message': 'Cannot finalize engagement. Critical statutory audit conditions remain unresolved.',
                'blockers': readiness['blockers'],
                'gate_results': readiness['gate_results']
            }

        engagement.is_finalized = True
        engagement.finalized_at = timezone.now()
        if user and user.is_authenticated:
            engagement.finalized_by = user
        engagement.status = EngagementStatus.COMPLETED
        engagement.save(update_fields=['is_finalized', 'finalized_at', 'finalized_by', 'status'])

        # Record audit trail
        AuditLog.objects.create(
            user=user if user and user.is_authenticated else None,
            action="FINALIZE_ENGAGEMENT",
            entity_type="Engagement",
            entity_id=str(engagement.id),
            details={
                'justification': justification,
                'finalized_at': engagement.finalized_at.isoformat(),
                'lead_partner': user.username if user else 'SYSTEM',
                'blockers_checked': readiness['raw_blockers_count']
            }
        )

        return {
            'success': True,
            'message': f"Engagement '{engagement.title}' successfully finalized and certified.",
            'finalized_at': engagement.finalized_at.isoformat(),
            'finalized_by': engagement.finalized_by.username if engagement.finalized_by else None,
            'status': 'COMPLETED'
        }
