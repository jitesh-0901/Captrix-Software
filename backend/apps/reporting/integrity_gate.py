import re
from decimal import Decimal
from typing import Dict, Any, List
from django.utils import timezone
from apps.companies.models import Engagement, EntityType
from apps.audit.models import ExceptionItem, ExceptionSeverity, ExceptionStatus
from apps.reporting.models import Workpaper, WorkpaperStatus
from apps.reconciliation.models import ReconciliationRun


class ReportIntegrityGateService:
    """
    CRITICAL STATUTORY REPORT INTEGRITY GATE
    Enforces strict ICAI, SA (Standards on Auditing), and Companies Act 2013 rules
    to prevent contradictory totals, open high-risk exceptions, unsupported procedures,
    and unauthorized statutory opinions from appearing in finalized audit reports.
    """

    @classmethod
    def evaluate_integrity(cls, engagement: Engagement, ca_credentials: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Evaluates the 6 mandatory integrity gates for an engagement report:
        1. Balance Sheet Footing & Double-Entry Equilibrium Gate
        2. Unresolved Critical & High Risk Exceptions Gate
        3. Bank Reconciliation Consistency Gate
        4. Procedure Evidence Grounding Gate (GSTR-1, e-way bills, FAR, inventory)
        5. SA 240 Fraud Analytical Review Gate (no overstatement of Benford's Law)
        6. CA Partner Credential & UDIN Verification Gate
        """
        ca_credentials = ca_credentials or {}
        blockers: List[str] = []
        warnings: List[str] = []
        gate_statuses: Dict[str, Any] = {}

        # -------------------------------------------------------------
        # GATE 0: Legal entity identity consistency
        # -------------------------------------------------------------
        company = engagement.company
        identity_issues = []
        if not (company.name or '').strip():
            identity_issues.append("Legal entity name is missing.")
        if company.entity_type in [EntityType.PVT_LTD, EntityType.PUB_LTD]:
            if not (company.cin or '').strip():
                identity_issues.append("CIN is missing for a company engagement.")
            if not (company.pan or '').strip():
                identity_issues.append("PAN is missing for the company engagement.")
        gate_statuses['entity_identity_gate'] = {
            'passed': not identity_issues,
            'issues': identity_issues,
        }
        blockers.extend(identity_issues)

        # -------------------------------------------------------------
        # GATE 1: Balance Sheet & Double-Entry Equilibrium
        # -------------------------------------------------------------
        tb = engagement.trial_balances.first()
        tb_is_balanced = tb.is_balanced if tb else False
        tb_diff = abs(Decimal(str(tb.difference_amount))) if tb else Decimal('0.00')

        # Check Balance Sheet equilibrium from saved reports or accounts
        accounts = engagement.company.ledger_accounts.all()
        bs_variance = Decimal('0.00')
        bs_is_balanced = False

        if tb and tb.accounts_snapshot:
            from apps.accounting.services import TrialBalanceService
            fs = TrialBalanceService.compile_financial_statements(tb.accounts_snapshot)
            tot_assets = Decimal(str(fs['balance_sheet']['assets']['total_assets']))
            tot_eq_liab = Decimal(str(fs['balance_sheet']['equity_and_liabilities']['total_equity_and_liabilities']))
            bs_variance = abs(tot_assets - tot_eq_liab)
            bs_is_balanced = bs_variance < Decimal('1.00')
        elif tb_is_balanced:
            bs_is_balanced = True

        gate_1_pass = tb_is_balanced and bs_is_balanced
        if not gate_1_pass:
            reason = f"Balance Sheet disequilibrium detected: Variance of ₹{bs_variance:,.2f} (TB Difference: ₹{tb_diff:,.2f})."
            blockers.append(reason)
            gate_statuses['equilibrium_gate'] = {'passed': False, 'details': reason}
        else:
            gate_statuses['equilibrium_gate'] = {'passed': True, 'details': "Double-entry debits match credits and Balance Sheet footings are in 100% equilibrium."}

        # -------------------------------------------------------------
        # GATE 2: Unresolved Critical / High Exceptions
        # -------------------------------------------------------------
        # Treat every non-terminal state as unresolved, including IN_REVIEW,
        # EVIDENCE_REQUESTED and ACCEPTED_RISK until a documented approval workflow
        # has actually closed the exception.
        terminal_exception_states = [ExceptionStatus.RESOLVED, ExceptionStatus.AJE_POSTED]
        open_crit = engagement.exceptions.filter(
            severity=ExceptionSeverity.CRITICAL,
        ).exclude(status__in=terminal_exception_states).count()
        open_high = engagement.exceptions.filter(
            severity=ExceptionSeverity.HIGH,
        ).exclude(status__in=terminal_exception_states).count()

        gate_2_pass = (open_crit == 0) and (open_high == 0)
        if not gate_2_pass:
            reason = f"{open_crit} critical and {open_high} high severity audit exceptions remain open/unposted."
            blockers.append(reason)
            gate_statuses['exceptions_gate'] = {
                'passed': False,
                'open_critical': open_crit,
                'open_high': open_high,
                'details': reason
            }
        else:
            gate_statuses['exceptions_gate'] = {'passed': True, 'details': "Zero unresolved high-risk or critical audit exceptions."}

        # -------------------------------------------------------------
        # GATE 3: Bank Reconciliation Consistency
        # -------------------------------------------------------------
        brs = ReconciliationRun.objects.filter(engagement=engagement, recon_type='BANK').first()
        brs_unresolved_count = 0
        brs_unreconciled_diff = Decimal('0.00')
        brs_status = brs.status if brs else 'NOT_PERFORMED'

        if brs:
            brs_unresolved_count = brs.unmatched_count
            brs_unreconciled_diff = abs(Decimal(str(brs.unreconciled_difference)))

        gate_3_contradiction = (
            brs is None
            or brs_status != 'BALANCED'
            or brs_unresolved_count > 0
            or brs_unreconciled_diff > Decimal('0.00')
        )
        gate_statuses['reconciliation_gate'] = {
            'passed': not gate_3_contradiction,
            'brs_status': brs_status,
            'unmatched_items': brs_unresolved_count,
            'unreconciled_difference': str(brs_unreconciled_diff),
            'allows_zero_unverified_claim': not gate_3_contradiction,
            'details': (
                "Bank reconciliation fully reconciled with zero timing differences."
                if not gate_3_contradiction else
                f"Bank reconciliation status is {brs_status} with {brs_unresolved_count} unmatched items and ₹{brs_unreconciled_diff:,.2f} variance. Cannot assert zero unverified reconciling items."
            )
        }
        if gate_3_contradiction:
            # A report cannot be finalized while reconciliation is unresolved.
            # This is a release blocker even when the arithmetic residual is zero:
            # unmatched/timing items still require documented auditor disposition.
            blockers.append(gate_statuses['reconciliation_gate']['details'])

        # -------------------------------------------------------------
        # GATE 4: Procedure Evidence Grounding Gate
        # -------------------------------------------------------------
        uploaded_docs = list(engagement.documents.values('document_type', 'original_filename', 'status'))
        uploaded_doc_types = [str(d.get('document_type', '')).upper() for d in uploaded_docs]
        verified_filenames = [
            str(d.get('original_filename', '')).lower()
            for d in uploaded_docs
            if str(d.get('status', '')).upper() == 'VERIFIED'
        ]
        verified_doc_types = {
            str(d.get('document_type', '')).upper()
            for d in uploaded_docs
            if str(d.get('status', '')).upper() == 'VERIFIED'
        }

        has_gstr1 = any('gstr-1' in f or 'gstr1' in f for f in verified_filenames)
        has_eway = any('eway' in f or 'e-way' in f or 'e_way' in f for f in verified_filenames)
        has_far = 'FIXED_ASSET_REGISTER' in verified_doc_types or any('far' in f or 'asset' in f for f in verified_filenames)
        has_aging = 'SUBLEDGER_AGING' in verified_doc_types or any('aging' in f or 'debtor' in f or 'creditor' in f for f in verified_filenames)

        procedure_evidence = {
            'revenue_cutoff_gstr1_eway': {
                'has_evidence': has_gstr1 and has_eway,
                'status': 'VERIFIED' if (has_gstr1 and has_eway) else 'EVIDENCE_MISSING',
                'description': 'Cross-testing sales invoices against GSTR-1 outward returns and e-way bill logistics'
            },
            'fixed_asset_register': {
                'has_evidence': has_far,
                'status': 'VERIFIED' if has_far else 'EVIDENCE_MISSING',
                'description': 'CARO 3(i) Fixed Asset Register records and title deed inspection'
            },
            'msme_subledger_aging': {
                'has_evidence': has_aging,
                'status': 'VERIFIED' if has_aging else 'EVIDENCE_MISSING',
                'description': 'Form 3CD Clause 22 MSME aging subledger and Section 43B(h) compliance'
            }
        }
        gate_statuses['procedure_evidence_gate'] = procedure_evidence
        for evidence_key, evidence_result in procedure_evidence.items():
            if not evidence_result['has_evidence']:
                blockers.append(
                    f"Required evidence missing for {evidence_key}: "
                    f"{evidence_result['description']}."
                )

        # -------------------------------------------------------------
        # GATE 5: SA 240 Fraud Analytical Review Gate
        # -------------------------------------------------------------
        gate_statuses['sa240_fraud_gate'] = {
            'first_digit_test_valid': True,
            'permits_fraud_absence_claim': False, # Strict SA 240 rule: Benford's Law alone cannot claim fraud is absent
            'statutory_notice': (
                "Standard on Auditing (SA) 240 Mandate: First-digit distribution (Benford's Law) is an analytical review "
                "procedure evaluating statistical digit dispersion. It does not evaluate management integrity, undisclosed "
                "related party arrangements, or unrecorded transactions, and CANNOT establish that fraud is absent."
            )
        }

        # -------------------------------------------------------------
        # GATE 6: CA Partner Credential & UDIN Verification Gate
        # -------------------------------------------------------------
        mem_no = str(ca_credentials.get('membership_no', '')).strip()
        frn = str(ca_credentials.get('firm_reg_no', '')).strip().upper()
        udin = str(ca_credentials.get('udin', '')).strip().upper()
        affirmation = bool(ca_credentials.get('partner_affirmation', False))
        # Format checks are not identity verification. Final issuance requires
        # trusted verification evidence supplied by an authorized server-side workflow.
        membership_externally_verified = ca_credentials.get('membership_externally_verified') is True
        frn_externally_verified = ca_credentials.get('frn_externally_verified') is True
        udin_externally_verified = ca_credentials.get('udin_externally_verified') is True
        authorization_record_id = str(ca_credentials.get('authorization_record_id', '')).strip()

        is_valid_membership = bool(re.match(r'^\d{6}$', mem_no)) and (mem_no not in ['000000', '999999'])
        is_valid_frn = bool(re.match(r'^[0-9A-Z]{5,8}$', frn)) and (frn not in ['XXXXXX'])

        # UDIN structure per ICAI: 2-digit FY (e.g., 25) + 6-digit Membership No + 10-digit doc code = 18 alphanumeric chars
        is_valid_udin = False
        udin_error = None
        if len(udin) == 18 and udin.isalnum():
            # Check if middle 6 digits match membership number
            if is_valid_membership and udin[2:8] == mem_no:
                is_valid_udin = True
            elif not is_valid_membership:
                udin_error = "UDIN cannot be validated without an authentic 6-digit ICAI Membership Number."
            else:
                udin_error = f"UDIN characters 3-8 ('{udin[2:8]}') do not match the signing CA Membership Number ('{mem_no}')."
        else:
            udin_error = "UDIN must be exactly 18 alphanumeric characters in accordance with ICAI Gazette Notification."

        total_wps = engagement.workpapers.count()
        unreviewed_wps = engagement.workpapers.exclude(status__in=[WorkpaperStatus.APPROVED, WorkpaperStatus.PARTNER_AUTHORIZED]).count()
        all_wps_approved = (total_wps > 0) and (unreviewed_wps == 0)

        if not all_wps_approved:
            blockers.append(f"{unreviewed_wps} of {total_wps} SA 230 audit working papers remain unapproved.")

        gate_6_pass = (
            is_valid_membership and is_valid_frn and is_valid_udin and affirmation
            and all_wps_approved and membership_externally_verified
            and frn_externally_verified and udin_externally_verified
            and bool(authorization_record_id)
        )
        if not (membership_externally_verified and frn_externally_verified and udin_externally_verified and authorization_record_id):
            blockers.append(
                "CA identity, firm registration, UDIN, and partner authorization must be verified "
                "through a trusted server-side workflow; format checks alone are insufficient."
            )
        gate_statuses['credentials_and_signoff_gate'] = {
            'passed': gate_6_pass,
            'is_valid_membership_format': is_valid_membership,
            'is_valid_frn_format': is_valid_frn,
            'is_valid_udin_format_and_membership_match': is_valid_udin,
            'membership_externally_verified': membership_externally_verified,
            'frn_externally_verified': frn_externally_verified,
            'udin_externally_verified': udin_externally_verified,
            'authorization_record_id_present': bool(authorization_record_id),
            'udin_error': udin_error,
            'all_wps_approved': all_wps_approved,
            'partner_affirmation': affirmation,
            'allows_official_opinion': gate_6_pass and gate_1_pass and gate_2_pass and not gate_3_contradiction
        }

        # -------------------------------------------------------------
        # AUTHORITATIVE FINALIZATION GATES CROSS-CHECK
        # -------------------------------------------------------------
        from apps.audit.finalization_service import AuditFinalizationService
        fin_readiness = AuditFinalizationService.evaluate_finalization_readiness(
            engagement, user=engagement.lead_partner, ca_credentials=ca_credentials
        )
        for b in fin_readiness.get('blockers', []):
            if b not in blockers:
                blockers.append(b)

        # -------------------------------------------------------------
        # OVERALL VERDICT & REPORT FINALIZATION READINESS
        # -------------------------------------------------------------
        evidence_gate_pass = all(item['has_evidence'] for item in procedure_evidence.values())
        is_ready_for_final_issue = (
            gate_1_pass and gate_2_pass and not gate_3_contradiction
            and evidence_gate_pass and gate_6_pass and len(blockers) == 0
        )

        return {
            'is_ready_for_final_issue': is_ready_for_final_issue,
            'report_mode': 'FINAL_CERTIFIED_REPORT' if is_ready_for_final_issue else 'DRAFT_AUDIT_WORKPAPER_ONLY',
            'opinion_allowed': is_ready_for_final_issue,
            'blockers': blockers,
            'warnings': warnings,
            'gate_statuses': gate_statuses,
            'evaluated_at': timezone.now().isoformat(),
            'financial_year_label': engagement.financial_year.label,
            'financial_year_end_date': engagement.financial_year.end_date.strftime('%d-%b-%Y'),
        }
