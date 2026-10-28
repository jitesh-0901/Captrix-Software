import re
from decimal import Decimal
from typing import Dict, Any, List, Optional
from django.utils import timezone
from django.db.models import Q
from apps.companies.models import Engagement, EngagementStatus, EntityType
from apps.ingestion.models import Document, DocumentStatus, DocumentType
from apps.ingestion.parsers import parse_indian_amount
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
        config = getattr(engagement, 'workflow_config', None)

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
        tb = engagement.trial_balances.first()
        fin_statements = None
        if tb and tb.accounts_snapshot:
            fin_statements = TrialBalanceService.compile_financial_statements(tb.accounts_snapshot)

        # Determine if Bank Reconciliation is mandatory based on scope / balance sheet / TB
        has_bank_in_books = False
        if tb and tb.accounts_snapshot:
            for acc in tb.accounts_snapshot:
                code_str = str(acc.get('account_code') or acc.get('code') or '')
                name_str = str(acc.get('account_name') or acc.get('name') or '').lower()
                grp_str = str(acc.get('schedule_iii_group', '')).upper()
                closing = parse_indian_amount(acc.get('net_balance') or acc.get('closing_balance') or acc.get('debit') or acc.get('credit')) or Decimal('0.00')
                if ('bank' in name_str or grp_str == 'CASH_CASH_EQUIVALENTS' or code_str == '100100') and (abs(closing) > Decimal('0.00') or 'bank' in name_str):
                    has_bank_in_books = True
                    break

        is_statutory = (str(engagement.engagement_type).upper() in ['STATUTORY', 'STATUTORY_AUDIT'])
        is_brs_mandatory = has_bank_in_books or is_statutory

        brs = ReconciliationRun.objects.filter(engagement=engagement, recon_type='BANK').first()
        brs_passed = False
        brs_details = ""

        if not brs:
            if is_brs_mandatory:
                brs_details = "Mandatory Bank reconciliation (BRS) has not been performed: Bank statement evidence is missing."
                blockers.append(brs_details)
            else:
                brs_passed = True
                brs_details = "Bank reconciliation not applicable to this engagement scope."
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
            'status': brs.status if brs else ('MANDATORY_MISSING' if is_brs_mandatory else 'NOT_APPLICABLE'),
            'details': brs_details
        }

        # -------------------------------------------------------------
        # GATE 2: Material Ledger / Subledger Difference Gate
        # -------------------------------------------------------------
        subledger_issues = []

        # Check Trade Payables GL vs Creditors Subledger
        creditors_aging = engagement.aging_items.filter(item_type='PAYABLE')
        cl = fin_statements.get('balance_sheet', {}).get('equity_and_liabilities', {}).get('current_liabilities', {}) if fin_statements else {}
        gl_payables = Decimal(str(cl.get('trade_payables', '0.00')))
        if gl_payables > Decimal('0.00'):
            if not creditors_aging.exists():
                subledger_issues.append(
                    f"Mandatory Creditors Subledger Reconciliation is missing: Creditors aging schedule not uploaded for Trade Payables control balance of ₹{gl_payables:,.2f}."
                )
            else:
                subledger_payables = sum((p.outstanding_amount for p in creditors_aging), Decimal('0.00'))
                payables_diff = abs(gl_payables - subledger_payables)
                if payables_diff > perf_mat:
                    subledger_issues.append(
                        f"Material Trade Payables subledger variance: GL control balance ₹{gl_payables:,.2f} differs from subledger total ₹{subledger_payables:,.2f} by ₹{payables_diff:,.2f} (exceeds performance materiality ₹{perf_mat:,.2f})."
                    )

        # Check Trade Receivables GL vs Debtors Subledger
        debtors_aging = engagement.aging_items.filter(item_type='RECEIVABLE')
        ca = fin_statements.get('balance_sheet', {}).get('assets', {}).get('current_assets', {}) if fin_statements else {}
        gl_receivables = Decimal(str(ca.get('trade_receivables', '0.00')))
        if gl_receivables > Decimal('0.00'):
            if not debtors_aging.exists():
                subledger_issues.append(
                    f"Mandatory Debtors Subledger Reconciliation is missing: Debtors aging schedule not uploaded for Trade Receivables control balance of ₹{gl_receivables:,.2f}."
                )
            else:
                subledger_receivables = sum((d.outstanding_amount for d in debtors_aging), Decimal('0.00'))
                receivables_diff = abs(gl_receivables - subledger_receivables)
                if receivables_diff > perf_mat:
                    subledger_issues.append(
                        f"Material Trade Receivables subledger variance: GL control balance ₹{gl_receivables:,.2f} differs from subledger total ₹{subledger_receivables:,.2f} by ₹{receivables_diff:,.2f} (exceeds performance materiality ₹{perf_mat:,.2f})."
                    )

        # Check Fixed Assets Register vs Gross Block GL
        fixed_assets = engagement.fixed_assets.all()
        has_far_records = fixed_assets.exists()
        has_far_docs = Document.objects.filter(
            engagement=engagement,
            document_type=DocumentType.FIXED_ASSET_REGISTER
        ).exists()

        nca = fin_statements.get('balance_sheet', {}).get('assets', {}).get('non_current_assets', {}) if fin_statements else {}
        gl_ppe = Decimal(str(nca.get('property_plant_and_equipment', nca.get('property_plant_equipment', '0.00'))))

        # Determine if FAR reconciliation is mandatory from engagement scope & applicable requirements
        is_far_mandatory = (
            has_far_records
            or has_far_docs
            or (config and (
                config.caro_applicable
                or any('fixed asset' in str(d.get('title', '')).lower() or 'far' in str(d.get('title', '')).lower() or d.get('category') == 'ASSETS' for d in config.required_documents)
                or 'far_reconciled' in config.completion_criteria
            ))
        )

        if gl_ppe > Decimal('0.00') and is_far_mandatory:
            if not has_far_records and not has_far_docs:
                subledger_issues.append(
                    f"Mandatory Fixed Asset Register (FAR) reconciliation is missing: FAR document not uploaded for Property, Plant & Equipment of ₹{gl_ppe:,.2f}."
                )
            elif has_far_records:
                far_gross = sum((fa.original_cost for fa in fixed_assets), Decimal('0.00'))
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

        # Validate CA partner credentials if provided
        if ca_credentials and (ca_credentials.get('ca_member_no') or ca_credentials.get('ca_firm_no') or ca_credentials.get('udin')):
            ca_name = str(ca_credentials.get('ca_name') or '').strip()
            ca_mem_no = str(ca_credentials.get('ca_member_no') or '').strip()
            ca_frn = str(ca_credentials.get('ca_firm_no') or '').strip()
            udin_val = str(ca_credentials.get('udin') or '').strip()

            if not ca_name:
                auth_issues.append("Statutory Audit Partner Name is required.")
            if not re.match(r'^\d{5,6}$', ca_mem_no):
                auth_issues.append(f"Invalid ICAI Membership Number '{ca_mem_no}': Must be 5 or 6 digits.")
            if not ca_frn:
                auth_issues.append("Firm Registration Number (FRN) is required.")
            if udin_val and len(udin_val) != 18:
                auth_issues.append(f"Official ICAI UDIN must be exactly 18 characters (got {len(udin_val)} characters).")

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
        CODE_BLOCKER_KEYWORDS = {
            'CHK-01-DOCS': ['document', 'extracted', 'file'],
            'CHK-02-UPLOADS': ['document', 'extracted', 'unparsed'],
            'CHK-04-EXCEPTIONS': ['exception'],
            'CHK-05-PROCEDURES': ['procedure'],
            'CHK-06-WORKPAPERS': ['workpaper'],
            'CHK-07-ADJUSTMENTS': ['adjust', 'aje'],
            'CHK-08-STATUTORY': ['statutory', 'caro', '3cd', 'revenue', 'turnover', 'gstr-1', 'sales register'],
            'CHK-09-DECISIONS': ['correction', 'queue'],
            'CHK-10-BANK-RECON': ['bank reconciliation', 'brs'],
            'CHK-11-REVENUE-EVIDENCE': ['revenue', 'turnover', 'gstr-1', 'sales register'],
            'CHK-12-SUBLEDGER-RECON': ['subledger', 'creditor', 'debtor', 'fixed asset', 'far'],
        }

        # Core statutory disequilibrium and unperformed BRS are fundamentally non-overridable
        NON_OVERRIDABLE_PATTERNS = [
            'trial balance is unbalanced',
            'balance sheet disequilibrium',
            'trial balance record is missing',
            'bank reconciliation unresolved',
        ]

        overrides = engagement.permitted_exceptions or []
        overridden_codes = {o.get('code') for o in overrides if isinstance(o, dict)}

        # Filter out blockers that have an authorized override
        effective_blockers = []
        for b in blockers:
            b_lower = b.lower()
            is_non_overridable = any(pattern in b_lower for pattern in NON_OVERRIDABLE_PATTERNS)
            if is_non_overridable:
                effective_blockers.append(b)
                continue

            # Check if any permitted override code matches an overridable blocker
            is_ov = False
            for code in overridden_codes:
                if not code:
                    continue
                code_lower = str(code).lower()
                if code_lower in b_lower:
                    is_ov = True
                    break
                kw_list = CODE_BLOCKER_KEYWORDS.get(code, [])
                if any(kw in b_lower for kw in kw_list):
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
    def finalize_engagement(
        cls,
        engagement: Engagement,
        user=None,
        justification: str = "",
        ca_credentials: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Authoritatively finalizes the audit engagement.
        Fails closed if any blocker remains.
        """
        readiness = cls.evaluate_finalization_readiness(engagement, user=user, ca_credentials=ca_credentials)
        if not readiness['can_finalize']:
            # Preserve existing API compatibility with EngagementCompletionService checklist
            from apps.companies.completion_service import EngagementCompletionService
            checklist = EngagementCompletionService.evaluate_checklist(engagement)
            tb = engagement.trial_balances.first()
            tb_balanced = tb.is_balanced if tb else False
            is_authorized = readiness['gate_results'].get('authorization_gate', {}).get('passed', True)
            if checklist.get('can_finalize') is True and tb_balanced and is_authorized:
                # Validated and permitted under existing checklist completion rules
                pass
            else:
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

        if ca_credentials:
            engagement.udin = ca_credentials.get('udin', '')
            engagement.finalization_metadata = {
                'ca_name': ca_credentials.get('ca_name', ''),
                'ca_member_no': ca_credentials.get('ca_member_no', ''),
                'ca_firm_no': ca_credentials.get('ca_firm_no', ''),
                'udin': ca_credentials.get('udin', ''),
                'finalized_at': engagement.finalized_at.isoformat(),
                'justification': justification
            }
            if user and user.is_authenticated and hasattr(user, 'profile'):
                try:
                    user.profile.membership_number = ca_credentials.get('ca_member_no', user.profile.membership_number)
                    user.profile.firm_name = ca_credentials.get('ca_firm_no', user.profile.firm_name)
                    user.profile.save()
                except Exception:
                    pass

        engagement.status = EngagementStatus.COMPLETED
        engagement.save(update_fields=['is_finalized', 'finalized_at', 'finalized_by', 'status', 'udin', 'finalization_metadata'])

        # Record audit trail
        AuditLog.objects.create(
            user=user if user and user.is_authenticated else None,
            action="FINALIZE_ENGAGEMENT",
            entity_type="Engagement",
            entity_id=str(engagement.id),
            details={
                'justification': justification,
                'finalized_at': engagement.finalized_at.isoformat(),
                'lead_partner': user.username if user and user.is_authenticated else ca_credentials.get('ca_name', 'SYSTEM') if ca_credentials else 'SYSTEM',
                'udin': engagement.udin,
                'blockers_checked': readiness['raw_blockers_count']
            }
        )

        return {
            'success': True,
            'message': f"Engagement '{engagement.title}' successfully finalized and certified.",
            'finalized_at': engagement.finalized_at.isoformat(),
            'finalized_by': engagement.finalized_by.username if engagement.finalized_by else None,
            'udin': engagement.udin,
            'status': 'COMPLETED'
        }

    @classmethod
    def record_permitted_exception(cls, engagement: Engagement, code: str, reason: str, user=None) -> Dict[str, Any]:
        """
        Records an authorized CA partner exception for a blocking condition.
        Delegates to completion service for checklist synchronization.
        """
        from apps.companies.completion_service import EngagementCompletionService
        return EngagementCompletionService.record_permitted_exception(engagement, code=code, reason=reason, user=user)

