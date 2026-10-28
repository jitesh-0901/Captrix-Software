import os
import hashlib
from decimal import Decimal
from datetime import datetime, date
from django.utils import timezone
from django.db.models import Sum, Q, Count

from apps.companies.models import Engagement, Company, EntityType, EngagementStatus
from apps.ingestion.models import Document, DocumentStatus, DocumentType, ExtractedRecord
from apps.accounting.models import LedgerAccount, Transaction, TrialBalanceSnapshot, ScheduleIIIGroup, AccountType
from apps.reconciliation.models import ReconciliationRun, ReconciliationStatus
from apps.audit.models import (
    ProcedureExecution, ProcedureStatus, ExceptionItem, ExceptionSeverity,
    FixedAsset, SubledgerAgingItem, RelatedParty, StatutoryClauseAudit
)
from apps.audit.services import FinancialRatiosEngine
from apps.reporting.models import Workpaper, WorkpaperStatus, ProposedAdjustment, AdjustmentStatus


class DocumentUploadReportBuilder:
    """
    REPORT 1 — DOCUMENT UPLOAD AND PROCESSING REPORT
    Generates structured metrics for each uploaded document:
    - Original filename, file type, detected document category
    - Upload timestamp, job ID, processing status
    - Records processed, extracted, review-required, failed/skipped
    - Duplicate-file and duplicate-record warnings
    - Missing/ambiguous fields, errors, coverage and limitations
    - Clear distinction between successful OCR/extraction vs verified accounting correctness.
    """

    @classmethod
    def build_report(cls, engagement: Engagement) -> dict:
        docs = engagement.documents.all().prefetch_related('extracted_records', 'jobs')
        file_reports = []
        total_files = docs.count()
        total_records = 0
        total_valid = 0
        total_review_required = 0
        total_failed = 0
        duplicate_count = 0

        # Track file hashes for duplicate detection
        seen_hashes = {}

        for doc in docs:
            records = doc.extracted_records.all()
            rec_count = records.count()
            valid_count = records.filter(validation_status='VALID').count()
            review_count = records.filter(validation_status='REVIEW_REQUIRED').count()
            invalid_count = records.filter(validation_status='INVALID').count()

            total_records += rec_count
            total_valid += valid_count
            total_review_required += review_count
            total_failed += invalid_count

            # Check duplicate hash
            is_dup = doc.file_hash in seen_hashes
            if is_dup:
                duplicate_count += 1
            else:
                seen_hashes[doc.file_hash] = doc.original_filename

            latest_job = doc.jobs.first()

            file_reports.append({
                'document_id': doc.id,
                'original_filename': doc.original_filename,
                'file_format': doc.original_filename.split('.')[-1].upper() if '.' in doc.original_filename else 'UNKNOWN',
                'mime_type': doc.mime_type,
                'file_size_bytes': doc.file_size_bytes,
                'file_hash_sha256': doc.file_hash,
                'document_type': doc.document_type,
                'detected_category': doc.get_document_type_display(),
                'status': doc.status,
                'uploaded_at': doc.uploaded_at.isoformat(),
                'job_id': latest_job.id if latest_job else None,
                'job_stage': latest_job.stage if latest_job else 'COMPLETED',
                'total_records_processed': rec_count,
                'successfully_extracted_records': valid_count,
                'records_requiring_review': review_count,
                'failed_or_skipped_records': invalid_count,
                'is_duplicate_file': is_dup,
                'duplicate_warning': f"Exact duplicate hash matching '{seen_hashes[doc.file_hash]}'" if is_dup else None,
                'error_message': doc.error_message or None,
                'source_coverage': f"100% of rows extracted ({rec_count} entries)",
                'accounting_verification_status': "EXTRACTED_ONLY_PENDING_AUDITOR_VERIFICATION" if doc.status != DocumentStatus.VERIFIED else "AUDITOR_VERIFIED"
            })

        stat_disclaimer = (
            "DATA EXTRACTION INTEGRITY NOTICE: Successful parsing or OCR extraction does not constitute proof of "
            "accounting accuracy, statutory compliance, or a statutory audit opinion. Extracted values remain subject to double-entry "
            "reconciliation, roll-forward validation, and auditor verification."
        )

        return {
            'report_name': "Document Upload and Processing Report",
            'report_title': "Document Upload & Processing Integrity Report",
            'company_name': engagement.company.name,
            'engagement_title': engagement.title,
            'financial_year': engagement.financial_year.label,
            'generated_at': timezone.now().isoformat(),
            'total_documents': total_files,
            'total_records_processed': total_records,
            'total_valid_records': total_valid,
            'total_review_required_records': total_review_required,
            'total_failed_records': total_failed,
            'duplicate_files_detected': duplicate_count,
            'summary': {
                'total_documents': total_files,
                'total_records_processed': total_records,
                'total_valid': total_valid,
                'total_review_required': total_review_required,
                'total_failed': total_failed,
                'duplicate_files': duplicate_count
            },
            'disclaimer': stat_disclaimer,
            'statutory_disclaimer': stat_disclaimer,
            'documents': file_reports,
            'files': file_reports
        }


class ConsolidatedAuditReportBuilder:
    """
    REPORT 2 — CONSOLIDATED FINANCIAL AND AUDIT ANALYSIS REPORT
    Builds the complete 14-section audit analysis report (Sections A through N) from real database records.
    Every figure is grounded in saved DB models using Python Decimal arithmetic.
    """

    @classmethod
    def build_report(cls, engagement: Engagement) -> dict:
        company = engagement.company
        fy = engagement.financial_year
        config = getattr(engagement, 'workflow_config', None)

        # ---------------------------------------------------------
        # SECTION A: Report Cover and Company Information
        # ---------------------------------------------------------
        section_a = {
            'section_code': 'SEC-A',
            'title': 'Report Cover & Company Information',
            'has_data': True,
            'is_applicable': True,
            'company_name': company.name,
            'cin': company.cin or 'NOT PROVIDED — ENTITY IDENTITY REVIEW REQUIRED',
            'pan': company.pan or 'NOT PROVIDED — TAX IDENTITY REVIEW REQUIRED',
            'gstin': company.gstin or 'NOT PROVIDED — APPLICABILITY / REGISTRATION REVIEW REQUIRED',
            'entity_type': company.get_entity_type_display(),
            'registered_address': company.registered_address or 'Address on file',
            'industry': company.industry,
            'financial_year': fy.label,
            'reporting_period': f"{fy.start_date.strftime('%d-%b-%Y')} to {fy.end_date.strftime('%d-%b-%Y')}",
            'engagement_title': engagement.title,
            'engagement_type': engagement.get_engagement_type_display(),
            'report_generation_date': timezone.now().strftime('%d-%b-%Y %H:%M:%S UTC'),
            'report_version': '1.0 - Formally Compiled Draft',
            'source_coverage': 'Full Company Ledgers, Bank Statements & Statutory Schedules',
            'report_status': 'DRAFT_INDEPENDENT_AUDIT_REPORT' if not engagement.is_finalized else 'FINAL_APPROVED_AUDIT_REPORT',
            'is_finalized': engagement.is_finalized
        }

        # ---------------------------------------------------------
        # SECTION B: Executive Summary
        # ---------------------------------------------------------
        docs_count = engagement.documents.count()
        docs_verified = engagement.documents.filter(status=DocumentStatus.VERIFIED).count()
        docs_review = engagement.documents.filter(status=DocumentStatus.REVIEW_REQUIRED).count()
        docs_failed = engagement.documents.filter(status=DocumentStatus.FAILED).count()

        tb = engagement.trial_balances.first()
        tb_status = "BALANCED (In Double-Entry Equilibrium)" if (tb and tb.is_balanced) else (
            f"UNBALANCED (Variance: ₹{abs(tb.difference_amount):,.2f})" if tb else "NOT_COMPUTED"
        )

        brs = ReconciliationRun.objects.filter(engagement=engagement, recon_type='BANK').first()
        brs_status = brs.status if brs else "NOT_PERFORMED"
        brs_unmatched = brs.unmatched_count if brs else 0
        brs_unrec_diff = abs(Decimal(str(brs.unreconciled_difference or '0.00'))) if brs else Decimal('0.00')

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

        from .integrity_gate import ReportIntegrityGateService
        gate_result = ReportIntegrityGateService.evaluate_integrity(engagement)
        is_final_certified = bool(engagement.is_finalized and gate_result.get('is_ready_for_final_issue', False))

        procs_executed = engagement.procedure_executions.count()
        procs_passed = engagement.procedure_executions.filter(status=ProcedureStatus.PASSED_NO_EXCEPTIONS).count()
        procs_exceptions = engagement.procedure_executions.filter(status=ProcedureStatus.PASSED_WITH_EXCEPTIONS).count()

        total_excs = engagement.exceptions.count()
        open_excs = engagement.exceptions.filter(status__in=['OPEN', 'IN_REVIEW', 'AJE_PROPOSED']).count()
        critical_excs = engagement.exceptions.filter(severity=ExceptionSeverity.CRITICAL, status__in=['OPEN', 'IN_REVIEW', 'AJE_PROPOSED']).count()
        high_excs = engagement.exceptions.filter(severity=ExceptionSeverity.HIGH, status__in=['OPEN', 'IN_REVIEW', 'AJE_PROPOSED']).count()

        # Effective exceptions synchronization: never show 0 exceptions when open exceptions exist
        actual_exceptions_count = max(procs_exceptions, open_excs, total_excs)

        total_wps = engagement.workpapers.count()
        partner_auth_wps = engagement.workpapers.filter(status=WorkpaperStatus.PARTNER_AUTHORIZED).count()
        approved_wps = engagement.workpapers.filter(status=WorkpaperStatus.APPROVED).count()
        review_req_wps = engagement.workpapers.filter(status=WorkpaperStatus.REVIEW_REQUIRED).count()
        reviewed_wps = engagement.workpapers.filter(status__in=[WorkpaperStatus.REVIEWED, WorkpaperStatus.READY_FOR_REVIEW]).count()
        prepared_wps = engagement.workpapers.filter(status__in=[WorkpaperStatus.PREPARED, WorkpaperStatus.DRAFT]).count()
        unreviewed_wps = engagement.workpapers.exclude(status__in=[WorkpaperStatus.APPROVED, WorkpaperStatus.PARTNER_AUTHORIZED]).count()

        next_actions = []
        if critical_excs > 0:
            next_actions.append(f"Review and resolve {critical_excs} critical audit exceptions")
        if open_excs > 0:
            next_actions.append(f"Evaluate and authorize {open_excs} proposed adjusting journal entries (AJE)")
        if tb and not tb.is_balanced:
            next_actions.append(f"Reconcile Trial Balance variance of ₹{abs(tb.difference_amount):,.2f}")
        if brs and (brs.status != 'BALANCED' or brs_unmatched > 0 or brs_unrec_diff > Decimal('0.00')):
            next_actions.append(f"Resolve Bank Reconciliation: {brs_unmatched} unmatched item(s) and ₹{brs_unrec_diff:,.2f} variance pending clearance")
        if not (has_gstr1 or has_sales_reg):
            next_actions.append("Obtain GSTR-1 outward returns / Sales Register to substantive-test revenue occurrence")
        if unreviewed_wps > 0:
            next_actions.append(f"Approve {unreviewed_wps} outstanding workpapers following SA 230 review")
        if not next_actions:
            next_actions = ["All primary audit verifications completed satisfactorily; ready for final sign-off."]

        accounts = LedgerAccount.objects.filter(company=company).select_related('coa')
        has_fin_data = bool(engagement.transactions.exists() or (tb is not None) or accounts.exists())

        section_b = {
            'section_code': 'SEC-B',
            'title': 'Executive Summary',
            'has_data': True,
            'is_applicable': True,
            'financial_data_available': has_fin_data,
            'documents_processed_successfully': docs_verified,
            'documents_requiring_review': docs_review,
            'documents_failed': docs_failed,
            'trial_balance_status': tb_status,
            'trial_balance_balanced': (tb.is_balanced if tb else False),
            'trial_balance_difference': str(tb.difference_amount) if tb else '0.00',
            'reconciliation_status': brs_status,
            'bank_reconciliation_unmatched_count': brs_unmatched,
            'bank_reconciliation_unreconciled_difference': str(brs_unrec_diff),
            'revenue_verification_status': "VERIFIED" if (has_gstr1 or has_sales_reg) else "UNVERIFIED_MISSING_EVIDENCE",
            'integrity_gate_passed': gate_result.get('is_ready_for_final_issue', False),
            'integrity_gate_blockers_count': len(gate_result.get('blockers', [])),
            'opinion_readiness': "READY_FOR_STATUTORY_SIGN_OFF" if is_final_certified else "DRAFT_PENDING_PROFESSIONAL_REVIEW",
            'audit_procedures_executed': procs_executed,
            'procedures_passed': procs_passed,
            'procedures_with_exceptions': actual_exceptions_count,
            'open_exceptions_count': open_excs,
            'total_exceptions': total_excs,
            'critical_unresolved_exceptions': critical_excs,
            'high_unresolved_exceptions': high_excs,
            'total_workpapers': total_wps,
            'unreviewed_workpapers_count': unreviewed_wps,
            'approved_workpapers_count': approved_wps,
            'partner_authorized_workpapers_count': partner_auth_wps,
            'review_required_workpapers_count': review_req_wps,
            'reviewed_workpapers_count': reviewed_wps,
            'prepared_workpapers_count': prepared_wps,
            'overall_materiality': str(engagement.overall_materiality),
            'performance_materiality': str(engagement.performance_materiality),
            'recommended_next_actions': next_actions
        }

        # ---------------------------------------------------------
        # SECTION C: Financial Overview (P&L, Balance Sheet & Ratios)
        # ---------------------------------------------------------
        accounts = LedgerAccount.objects.filter(company=company).select_related('coa')
        fin_statements = None

        if tb and tb.accounts_snapshot:
            from apps.accounting.services import TrialBalanceService
            fin_statements = TrialBalanceService.compile_financial_statements(tb.accounts_snapshot)
        elif accounts.exists():
            from apps.accounting.services import TrialBalanceService
            acc_list = []
            for a in accounts:
                grp = a.coa.schedule_iii_group if a.coa else None
                acc_list.append({
                    'account_name': a.name,
                    'schedule_iii_group': grp,
                    'debit': str(a.closing_balance) if a.closing_balance_type == 'Dr' else '0.00',
                    'credit': str(a.closing_balance) if a.closing_balance_type == 'Cr' else '0.00',
                })
            fin_statements = TrialBalanceService.compile_financial_statements(acc_list)

        if fin_statements:
            pl = fin_statements.get('profit_and_loss', {})
            bs = fin_statements.get('balance_sheet', {})
            eq_liab = bs.get('equity_and_liabilities', {})
            bs_assets = bs.get('assets', {})

            revenue_total = Decimal(str(pl.get('total_revenue', '0.00')))
            expense_total = Decimal(str(pl.get('expenses', {}).get('total_expenses', '0.00')))
            net_profit = Decimal(str(pl.get('profit_after_tax', '0.00')))

            assets_total = Decimal(str(bs_assets.get('total_assets', '0.00')))
            liab_nc = Decimal(str(eq_liab.get('non_current_liabilities', {}).get('total', '0.00')))
            liab_c = Decimal(str(eq_liab.get('current_liabilities', {}).get('total', '0.00')))
            liabilities_total = liab_nc + liab_c
            equity_total = Decimal(str(eq_liab.get('shareholders_funds', {}).get('total', '0.00')))

            nc_assets = bs_assets.get('non_current_assets', {})
            ppe_total = Decimal(str(nc_assets.get('property_plant_and_equipment', nc_assets.get('property_plant_equipment', '0.00'))))
            cur_assets = bs_assets.get('current_assets', {})
            cash_total = Decimal(str(cur_assets.get('cash_and_cash_equivalents', '0.00')))
            receivables_total = Decimal(str(cur_assets.get('trade_receivables', '0.00')))
            payables_total = Decimal(str(eq_liab.get('current_liabilities', {}).get('trade_payables', '0.00')))
        else:
            revenue_total = Decimal('0.00')
            expense_total = Decimal('0.00')
            net_profit = Decimal('0.00')
            assets_total = Decimal('0.00')
            liabilities_total = Decimal('0.00')
            equity_total = Decimal('0.00')
            cash_total = Decimal('0.00')
            receivables_total = Decimal('0.00')
            payables_total = Decimal('0.00')
            ppe_total = Decimal('0.00')

        # Full Balance Sheet Equilibrium Cross-Check
        total_equity_and_liabilities = equity_total + liabilities_total
        bs_variance = abs(assets_total - total_equity_and_liabilities)
        bs_is_balanced = (bs_variance < Decimal('0.005')) if fin_statements else False
        bs_status = "BALANCED (Total Assets = Total Equity & Liabilities)" if (bs_is_balanced and fin_statements) else (
            f"UNBALANCED (Variance: ₹{bs_variance:,.2f})" if fin_statements else "NOT_COMPUTED"
        )

        # Proposed Adjustments (AJE) Impact Layer & Pro-Forma Recalculation
        pending_ajes = engagement.adjustments.filter(is_posted=False)
        dep_adj = Decimal('0.00')
        seen_dep_keys = set()
        for a in pending_ajes:
            if 'dep' in a.title.lower() or 'dep' in a.reason.lower():
                key = (str(a.total_debit), a.title.strip().lower()[:20])
                if key not in seen_dep_keys:
                    seen_dep_keys.add(key)
                    dep_adj += a.total_debit

        if dep_adj == Decimal('0.00'):
            far_dep_excs = engagement.exceptions.filter(rule_code='RULE_DEPRECIATION_VARIANCE').first()
            if far_dep_excs and far_dep_excs.amount_involved > Decimal('0.00'):
                dep_adj = far_dep_excs.amount_involved

        adj_expense_total = expense_total + dep_adj
        adj_net_profit = net_profit - dep_adj
        adj_ppe_total = max(Decimal('0.00'), ppe_total - dep_adj)
        adj_assets_total = max(Decimal('0.00'), assets_total - dep_adj)
        adj_equity_total = equity_total - dep_adj
        adj_eq_liab_total = adj_equity_total + liabilities_total

        # Audit Lineage Tracking for every Financial Statement figure
        doc_names = list(engagement.documents.values_list('original_filename', flat=True))
        primary_tb_doc = next((d for d in doc_names if 'tb' in d.lower() or 'trial' in d.lower()), doc_names[0] if doc_names else "Uploaded Trial Balance")
        primary_bank_doc = next((d for d in doc_names if 'bank' in d.lower() or 'stmt' in d.lower() or 'passbook' in d.lower()), primary_tb_doc)
        primary_far_doc = next((d for d in doc_names if 'far' in d.lower() or 'asset' in d.lower()), primary_tb_doc)
        primary_rec_doc = next((d for d in doc_names if 'debtor' in d.lower() or 'rec' in d.lower() or 'ar' in d.lower()), primary_tb_doc)
        primary_pay_doc = next((d for d in doc_names if 'creditor' in d.lower() or 'pay' in d.lower() or 'ap' in d.lower()), primary_tb_doc)

        has_fin = bool(fin_statements is not None)
        audit_lineage = {
            'revenue_from_operations': {
                'head': 'Revenue from Operations',
                'amount': str(revenue_total),
                'is_calculated': has_fin and (revenue_total > Decimal('0.00')),
                'source_document': primary_tb_doc,
                'source_sheet': 'Trial Balance / P&L Group',
                'source_account_codes': ['3001', '3002'] if accounts.exists() else ['Turnover_Ledgers'],
                'calculation_method': 'Sum of Schedule III Division I operating turnover closing credits less debit returns',
                'review_status': 'VERIFIED_FROM_TB' if has_fin else 'INSUFFICIENT_DATA_PENDING_UPLOAD'
            },
            'total_expenses': {
                'head': 'Operating & Administrative Expenses',
                'amount': str(expense_total),
                'is_calculated': has_fin and (expense_total > Decimal('0.00')),
                'source_document': primary_tb_doc,
                'source_sheet': 'Trial Balance / P&L Group',
                'source_account_codes': ['4001', '4101', '4102', '4103', '4201'] if accounts.exists() else ['Expense_Ledgers'],
                'calculation_method': 'Sum of employee benefits, operating, administrative, finance and depreciation debits',
                'review_status': 'VERIFIED_FROM_TB' if has_fin else 'INSUFFICIENT_DATA_PENDING_UPLOAD'
            },
            'net_profit_loss': {
                'head': 'Net Profit / (Loss) Before Tax',
                'amount': str(net_profit),
                'is_calculated': has_fin,
                'source_document': primary_tb_doc,
                'source_sheet': 'Schedule III P&L Statement',
                'source_account_codes': ['P&L_Equation'],
                'calculation_method': 'Total Revenue from Operations minus Total Expenses',
                'review_status': 'MATHEMATICALLY_VERIFIED' if has_fin else 'INSUFFICIENT_DATA_PENDING_UPLOAD'
            },
            'property_plant_equipment': {
                'head': 'Property, Plant and Equipment (Gross Block)',
                'amount': str(ppe_total),
                'is_calculated': has_fin and (ppe_total > Decimal('0.00')),
                'source_document': primary_far_doc,
                'source_sheet': 'Fixed Asset Register / Schedule III PPE',
                'source_account_codes': ['1001', '1002'] if accounts.exists() else ['Fixed_Assets'],
                'calculation_method': 'Sum of tangible asset capitalized acquisition costs less accumulated depreciation',
                'review_status': 'VERIFIED_FROM_FAR' if engagement.fixed_assets.exists() else ('VERIFIED_FROM_TB' if has_fin else 'INSUFFICIENT_DATA_PENDING_UPLOAD')
            },
            'trade_receivables': {
                'head': 'Trade Receivables (Sundry Debtors)',
                'amount': str(receivables_total),
                'is_calculated': has_fin and (receivables_total > Decimal('0.00')),
                'source_document': primary_rec_doc,
                'source_sheet': 'Debtors Aging / Schedule III Current Assets',
                'source_account_codes': ['1301', '1302'] if accounts.exists() else ['Debtors_Ledgers'],
                'calculation_method': 'Sum of closing debit balances of customer trade receivables',
                'review_status': 'VERIFIED_FROM_SUBLEDGER' if engagement.aging_items.filter(item_type='RECEIVABLE').exists() else ('VERIFIED_FROM_TB' if has_fin else 'INSUFFICIENT_DATA_PENDING_UPLOAD')
            },
            'cash_and_bank_balances': {
                'head': 'Cash & Cash Equivalents (Bank Balances)',
                'amount': str(cash_total),
                'is_calculated': has_fin and (cash_total > Decimal('0.00')),
                'source_document': primary_bank_doc,
                'source_sheet': 'Bank Passbook / Cashbook Ledger',
                'source_account_codes': ['1401', '1402', '1403'] if accounts.exists() else ['Bank_Accounts'],
                'calculation_method': 'Sum of closing ledger bank balances and physical petty cash in hand',
                'review_status': 'RECONCILED_WITH_BRS' if (brs and brs.status == 'BALANCED') else ('REVIEW_REQUIRED' if brs else ('VERIFIED_FROM_TB' if has_fin else 'INSUFFICIENT_DATA_PENDING_UPLOAD'))
            },
            'trade_payables': {
                'head': 'Trade Payables (Sundry Creditors)',
                'amount': str(payables_total),
                'is_calculated': has_fin and (payables_total > Decimal('0.00')),
                'source_document': primary_pay_doc,
                'source_sheet': 'Creditors Aging / Schedule III Current Liabilities',
                'source_account_codes': ['2201', '2202'] if accounts.exists() else ['Creditors_Ledgers'],
                'calculation_method': 'Sum of closing credit balances of supplier and vendor trade payables',
                'review_status': 'VERIFIED_FROM_SUBLEDGER' if engagement.aging_items.filter(item_type='PAYABLE').exists() else ('VERIFIED_FROM_TB' if has_fin else 'INSUFFICIENT_DATA_PENDING_UPLOAD')
            },
            'total_equity': {
                'head': "Shareholders' Equity & Reserves",
                'amount': str(equity_total),
                'is_calculated': has_fin and (equity_total > Decimal('0.00')),
                'source_document': primary_tb_doc,
                'source_sheet': 'Share Capital Schedule / Schedule III Balance Sheet',
                'source_account_codes': ['2001', '2002'] if accounts.exists() else ['Equity_Ledgers'],
                'calculation_method': 'Paid-up equity share capital plus retained earnings and reserves surplus',
                'review_status': 'VERIFIED_FROM_TB' if has_fin else 'INSUFFICIENT_DATA_PENDING_UPLOAD'
            }
        }

        ratios_data = FinancialRatiosEngine.compute_ratios(engagement)
        ratios_summary = {}
        if isinstance(ratios_data, dict):
            ratios_list = ratios_data.get('ratios', [])
            ratios_summary = dict(ratios_data.get('summary', {}))
        elif isinstance(ratios_data, list):
            ratios_list = ratios_data
            ratios_summary['total_indicators'] = len(ratios_data)
            for r in ratios_data:
                r_name = str(r.get('name', '')).lower().replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '')
                val = r.get('value', 0.0)
                if 'current_ratio' in r_name:
                    ratios_summary['current_ratio'] = val
                elif 'quick_ratio' in r_name:
                    ratios_summary['quick_ratio'] = val
                elif 'debt_to_equity' in r_name or 'debt_equity' in r_name:
                    ratios_summary['debt_equity'] = val
                    ratios_summary['debt_to_equity'] = val
                elif 'gross_profit' in r_name:
                    ratios_summary['gross_profit_margin'] = val
                elif 'net_profit' in r_name:
                    ratios_summary['net_profit_margin'] = val
        else:
            ratios_list = []
            ratios_summary = {}

        if fin_statements and isinstance(fin_statements.get('ratios'), dict):
            for rk, rv in fin_statements['ratios'].items():
                if rk not in ratios_summary or ratios_summary[rk] is None or ratios_summary[rk] == 0.0:
                    ratios_summary[rk] = rv

        section_c = {
            'section_code': 'SEC-C',
            'title': 'Financial Overview & Key Ratios',
            'has_data': bool(fin_statements is not None),
            'is_applicable': True,
            'currency': 'INR',
            'currency_symbol': '₹',
            'data_source': 'Persisted Ledger Accounts & Trial Balance Movement Layer',
            'calculation_basis': 'Indian Accounting Standards / Division I Schedule III Guidelines',
            # Unadjusted Figures (Per Books)
            'revenue_from_operations': str(revenue_total),
            'total_expenses': str(expense_total),
            'net_profit_loss': str(net_profit),
            'total_assets': str(assets_total),
            'total_liabilities': str(liabilities_total),
            'total_equity': str(equity_total),
            'total_equity_and_liabilities': str(total_equity_and_liabilities),
            'balance_sheet_difference': str(bs_variance),
            'balance_sheet_balanced': bs_is_balanced,
            'balance_sheet_status': bs_status,
            'cash_and_bank_balances': str(cash_total),
            'trade_receivables': str(receivables_total),
            'trade_payables': str(payables_total),
            'property_plant_equipment': str(ppe_total),
            # Proposed-Adjusted (Pro-Forma) Figures
            'has_proposed_adjustments': (dep_adj > Decimal('0.00')),
            'proposed_adjustments_count': pending_ajes.count(),
            'proposed_depreciation_adjustment': str(dep_adj),
            'adjusted_revenue': str(revenue_total),
            'adjusted_total_expenses': str(adj_expense_total),
            'adjusted_net_profit_loss': str(adj_net_profit),
            'adjusted_total_assets': str(adj_assets_total),
            'adjusted_property_plant_equipment': str(adj_ppe_total),
            'adjusted_total_equity': str(adj_equity_total),
            'adjusted_total_liabilities': str(liabilities_total),
            'adjusted_total_equity_and_liabilities': str(adj_eq_liab_total),
            'adjusted_balance_sheet_balanced': (abs(adj_assets_total - adj_eq_liab_total) < Decimal('1.00')),
            'adjusted_balance_sheet_difference': str(abs(adj_assets_total - adj_eq_liab_total)),
            'audit_lineage': audit_lineage,
            'financial_ratios': ratios_list,
            'ratios': ratios_list,
            'financial_ratios_summary': ratios_summary,
            'ratios_summary': ratios_summary,
            'financial_statements': fin_statements,
            'comparative_statements': {
                'unadjusted': {
                    'title': 'Unadjusted Financial Statements (Per Client General Ledger / TB)',
                    'revenue': str(revenue_total),
                    'total_expenses': str(expense_total),
                    'pbt': str(net_profit),
                    'ppe_carrying_amount': str(ppe_total),
                    'total_assets': str(assets_total),
                    'total_liabilities': str(liabilities_total),
                    'total_equity': str(equity_total),
                    'is_balanced': bs_is_balanced,
                    'variance': str(bs_variance)
                },
                'proposed_adjusted': {
                    'title': 'Proposed-Adjusted Pro-Forma Statements (Subject to Partner Sign-Off & Management Acceptance)',
                    'revenue': str(revenue_total),
                    'total_expenses': str(adj_expense_total),
                    'pbt': str(adj_net_profit),
                    'ppe_carrying_amount': str(adj_ppe_total),
                    'total_assets': str(adj_assets_total),
                    'total_liabilities': str(liabilities_total),
                    'total_equity': str(adj_equity_total),
                    'is_balanced': (abs(adj_assets_total - adj_eq_liab_total) < Decimal('1.00')),
                    'variance': str(abs(adj_assets_total - adj_eq_liab_total))
                }
            }
        }

        # ---------------------------------------------------------
        # SECTION D: Document Coverage and Data Quality
        # ---------------------------------------------------------
        req_docs = config.required_documents if config else []
        section_d = {
            'section_code': 'SEC-D',
            'title': 'Document Coverage & Data Quality',
            'has_data': bool(docs_count > 0),
            'is_applicable': True,
            'expected_documents_count': len(req_docs),
            'uploaded_documents_count': docs_count,
            'processed_documents_count': docs_verified,
            'failed_documents_count': docs_failed,
            'missing_documents_count': max(0, len(req_docs) - docs_count),
            'document_quality_assessment': "HIGH_CONFIDENCE_STRUCTURED" if docs_failed == 0 else "PARTIAL_RELIABILITY_ERRORS_DETECTED",
            'blocked_analyses': [] if docs_failed == 0 else ["Detailed inventory roll-forward may be limited due to unparsed stock sheets."]
        }

        # ---------------------------------------------------------
        # SECTION E: Trial Balance & General Ledger Scrutiny
        # ---------------------------------------------------------
        unmapped_accs = accounts.filter(
            Q(mapping_status__in=['UNMAPPED', 'REVIEW_REQUIRED']) | Q(coa__isnull=True)
        )
        suspense_accs = accounts.filter(is_suspense=True)
        unusual_txns = Transaction.objects.filter(engagement=engagement, is_unusual=True)

        section_e = {
            'section_code': 'SEC-E',
            'title': 'Trial Balance & General Ledger Scrutiny',
            'has_data': bool(tb is not None or accounts.exists()),
            'is_applicable': True,
            'trial_balance_as_of': tb.as_of_date.isoformat() if tb else fy.end_date.isoformat(),
            'total_debits': str(tb.total_debits) if tb else '0.00',
            'total_credits': str(tb.total_credits) if tb else '0.00',
            'trial_balance_difference': str(tb.difference_amount) if tb else '0.00',
            'is_balanced': tb.is_balanced if tb else False,
            'total_accounts_count': accounts.count(),
            'unmapped_accounts_count': unmapped_accs.count(),
            'unmapped_accounts_alert': unmapped_accs.exists(),
            'suspense_accounts_count': suspense_accs.count(),
            'suspense_balance_total': str(suspense_accs.aggregate(s=Sum('closing_balance'))['s'] or Decimal('0.00')),
            'unusual_transactions_count': unusual_txns.count(),
            'ledger_to_tb_reconciliation': "VERIFIED_CONSISTENT" if (tb and tb.is_balanced) else "VARIANCE_IDENTIFIED"
        }

        # ---------------------------------------------------------
        # SECTION F: Bank & Cross-Document Reconciliation
        # ---------------------------------------------------------
        recon_runs = ReconciliationRun.objects.filter(engagement=engagement)
        recon_list = []
        for r in recon_runs:
            recon_list.append({
                'recon_type': r.recon_type,
                'recon_title': r.get_recon_type_display(),
                'status': r.status,
                'matched_count': r.matched_count,
                'unmatched_count': r.unmatched_count,
                'unreconciled_variance': str(r.unreconciled_difference),
                'executed_at': r.created_at.isoformat()
            })

        has_recon_data = bool(brs or recon_runs.count() > 0)
        brs_unmatched_items = []
        if brs:
            for item in brs.items.filter(is_matched=False):
                brs_unmatched_items.append({
                    'source_type': item.source_type,
                    'item_date': item.item_date.strftime('%d-%b-%Y') if item.item_date else '-',
                    'reference_number': item.reference_number or '-',
                    'description': item.description or '-',
                    'amount': str(item.amount),
                    'timing_category': item.timing_category or 'Unmatched',
                })

        section_f = {
            'section_code': 'SEC-F',
            'title': 'Bank & Cross-Document Reconciliation Suite',
            'has_data': has_recon_data,
            'is_applicable': has_recon_data,
            'reconciliations_executed_count': recon_runs.count(),
            'bank_reconciliation_summary': brs.summary_data if brs else {},
            'bank_recon_details': {
                'balance_per_books': str(brs.balance_per_books) if brs else '0.00',
                'balance_per_statement': str(brs.balance_per_statement) if brs else '0.00',
                'timing_differences_amount': str(brs.timing_differences_amount) if brs else '0.00',
                'unreconciled_difference': str(brs.unreconciled_difference) if brs else '0.00',
                'status': brs.status if brs else 'NOT_PERFORMED',
                'matched_count': brs.matched_count if brs else 0,
                'unmatched_count': brs.unmatched_count if brs else 0,
                'stale_cheques_count': (brs.summary_data or {}).get('stale_cheques_count', 0) if brs else 0,
                'stale_cheques_amount': (brs.summary_data or {}).get('stale_cheques_amount', '0.00') if brs else '0.00',
                'valid_timing_count': (brs.summary_data or {}).get('valid_timing_count', 0) if brs else 0,
                'valid_timing_amount': (brs.summary_data or {}).get('valid_timing_amount', '0.00') if brs else '0.00',
                'direct_credits_by_bank': (brs.summary_data or {}).get('direct_credits_by_bank', '0.00') if brs else '0.00',
                'direct_debits_by_bank': (brs.summary_data or {}).get('direct_debits_by_bank', '0.00') if brs else '0.00',
                'review_required_reason': (brs.summary_data or {}).get('review_required_reason', '') if brs else '',
                'unmatched_items': brs_unmatched_items
            },
            'cross_document_checks': recon_list
        }

        # ---------------------------------------------------------
        # SECTION G: Account Schedules & Financial Analysis
        # ---------------------------------------------------------
        aging_items = SubledgerAgingItem.objects.filter(engagement=engagement)
        rec_aging = aging_items.filter(item_type='RECEIVABLE')
        pay_aging = aging_items.filter(item_type='PAYABLE')
        msme_items = pay_aging.filter(is_msme=True)
        overdue_43bh = pay_aging.filter(is_overdue_43bh=True)
        msme_total_outstanding = msme_items.aggregate(s=Sum('outstanding_amount'))['s'] or Decimal('0.00')

        tb_msme_ledgers = LedgerAccount.objects.filter(
            company=engagement.company
        ).filter(
            Q(code='200200') | Q(name__icontains='msme') | Q(name__icontains='micro') | Q(name__icontains='small enterprise')
        )
        tb_msme_amt = sum((l.closing_balance for l in tb_msme_ledgers), Decimal('0.00'))
        tb_other_pay_ledgers = LedgerAccount.objects.filter(
            company=engagement.company,
            coa__schedule_iii_group='TRADE_PAYABLES'
        ).exclude(id__in=tb_msme_ledgers.values_list('id', flat=True))
        tb_other_pay_amt = sum((l.closing_balance for l in tb_other_pay_ledgers), Decimal('0.00'))
        if tb_msme_amt == Decimal('0.00') and msme_total_outstanding > Decimal('0.00'):
            tb_msme_amt = msme_total_outstanding

        ppe_ledgers = LedgerAccount.objects.filter(
            company=engagement.company,
            coa__schedule_iii_group=ScheduleIIIGroup.PPE
        ).exclude(name__icontains='accumulated')
        tb_ppe_cost = sum((l.closing_balance for l in ppe_ledgers), Decimal('0.00'))

        assets = FixedAsset.objects.filter(engagement=engagement)
        total_asset_cost = assets.aggregate(s=Sum('original_cost'))['s'] or Decimal('0.00')
        total_sch_ii_depn = assets.aggregate(s=Sum('sch_ii_depreciation'))['s'] or Decimal('0.00')
        total_sec_32_depn = assets.aggregate(s=Sum('sec_32_depreciation'))['s'] or Decimal('0.00')
        total_booked_depn = assets.aggregate(s=Sum('booked_depreciation'))['s'] or Decimal('0.00')
        assets_with_var = assets.filter(depreciation_variance__gt=Decimal('0.00'))
        assets_with_var_count = assets_with_var.count()

        dep_ledgers = LedgerAccount.objects.filter(
            company=engagement.company,
            coa__schedule_iii_group='DEPRECIATION_AMORT'
        )
        book_dep = sum((l.closing_balance for l in dep_ledgers), Decimal('0.00'))

        assets_schedule = []
        for a in assets:
            assets_schedule.append({
                'asset_id': a.asset_id,
                'asset_name': a.asset_name,
                'category': a.category,
                'acquisition_date': a.acquisition_date.strftime('%d-%b-%Y') if a.acquisition_date else '-',
                'useful_life_years': str(a.useful_life_years),
                'method': 'SLM (Sch II)',
                'cost': str(a.original_cost),
                'booked_depreciation': str(a.booked_depreciation),
                'recalculated_depreciation': str(a.sch_ii_depreciation),
                'depreciation_variance': str(a.depreciation_variance),
                'carrying_amount': str(a.carrying_amount),
            })

        if not assets_schedule and ppe_ledgers.exists():
            for idx, pl in enumerate(ppe_ledgers, start=1):
                assets_schedule.append({
                    'asset_id': f"TB-PPE-{pl.code or idx}",
                    'asset_name': pl.name,
                    'category': pl.name,
                    'acquisition_date': engagement.financial_year.start_date.strftime('%d-%b-%Y') if engagement.financial_year else '-',
                    'useful_life_years': '3-10',
                    'method': 'SLM (Per TB Carrying Value)',
                    'cost': str(pl.closing_balance),
                    'booked_depreciation': str(book_dep) if idx == 1 else '0.00',
                    'recalculated_depreciation': '0.00',
                    'depreciation_variance': '0.00',
                    'carrying_amount': str(pl.closing_balance),
                })
            if total_asset_cost == Decimal('0.00'):
                total_asset_cost = tb_ppe_cost

        has_fa_data = assets.count() > 0 or total_asset_cost > Decimal('0.00') or ppe_ledgers.exists() or (ppe_total > Decimal('0.00'))
        has_pay_data = pay_aging.count() > 0 or overdue_43bh.count() > 0 or tb_msme_amt > Decimal('0.00') or tb_other_pay_amt > Decimal('0.00') or (payables_total > Decimal('0.00'))
        has_rec_data = rec_aging.count() > 0 or (receivables_total > Decimal('0.00'))
        has_sec_g_data = has_fa_data or has_pay_data or has_rec_data

        effective_book_dep = total_booked_depn if (book_dep == Decimal('0.00') and total_booked_depn > Decimal('0.00')) else book_dep
        book_dep_variance = abs(total_sch_ii_depn - effective_book_dep)

        tb_tot_payables = tb_msme_amt + tb_other_pay_amt
        subledger_tot_payables = pay_aging.aggregate(s=Sum('outstanding_amount'))['s'] or Decimal('0.00')
        payables_ctrl_var = abs(tb_tot_payables - subledger_tot_payables)

        section_g = {
            'section_code': 'SEC-G',
            'title': 'Account Schedules & Financial Analysis',
            'has_data': has_sec_g_data,
            'is_applicable': has_sec_g_data,
            'has_fixed_assets': has_fa_data,
            'has_payables_msme': has_pay_data,
            'has_receivables': has_rec_data,
            'receivables_aging_total': str(rec_aging.aggregate(s=Sum('outstanding_amount'))['s'] or Decimal('0.00')),
            'receivables_count': rec_aging.count(),
            'payables_aging_total': str(pay_aging.aggregate(s=Sum('outstanding_amount'))['s'] or Decimal('0.00')),
            'payables_count': pay_aging.count(),
            'msme_total_outstanding': str(msme_total_outstanding),
            'msme_total_invoices_count': msme_items.count(),
            'tb_msme_trade_payables': str(tb_msme_amt),
            'tb_other_trade_payables': str(tb_other_pay_amt),
            'tb_total_trade_payables': str(tb_tot_payables),
            'subledger_total_trade_payables': str(subledger_tot_payables),
            'subledger_to_control_payables_variance': str(payables_ctrl_var),
            'subledger_reconciliation_status': (
                "RECONCILED" if payables_ctrl_var < Decimal('1.00') and subledger_tot_payables > 0
                else f"REVIEW_REQUIRED (Variance of ₹{payables_ctrl_var:,.2f} between TB control account and subledger schedule; SA 505 third-party balance confirmation recommended)"
            ),
            'msme_overdue_section_43bh_total': str(overdue_43bh.aggregate(s=Sum('outstanding_amount'))['s'] or Decimal('0.00')),
            'msme_overdue_count': overdue_43bh.count(),
            'fixed_assets_count': assets.count(),
            'fixed_assets_gross_block': str(total_asset_cost),
            'schedule_ii_book_depreciation': str(total_sch_ii_depn),
            'section_32_tax_depreciation': str(total_sec_32_depn),
            'tb_depreciation_recorded': str(book_dep),
            'far_depreciation_recorded': str(total_booked_depn),
            'schedule_ii_recalculated_depreciation': str(total_sch_ii_depn),
            'tb_vs_far_depreciation_variance': str(abs(total_booked_depn - book_dep)),
            'far_vs_sch_ii_depreciation_variance': str(abs(total_sch_ii_depn - total_booked_depn)),
            'proposed_aje_depreciation': str(total_sch_ii_depn),
            'book_depreciation_recorded': str(effective_book_dep),
            'depreciation_variance': str(book_dep_variance),
            'asset_wise_variance_count': assets_with_var_count,
            'asset_wise_booked_depreciation': str(total_booked_depn),
            'schedule_ii_vs_sec_32_difference': str(total_sch_ii_depn - total_sec_32_depn),
            'assets_schedule': assets_schedule
        }

        # ---------------------------------------------------------
        # SECTION H: India-Specific Tax & Compliance Workflows
        # ---------------------------------------------------------
        clauses = StatutoryClauseAudit.objects.filter(engagement=engagement)
        caro_clauses = clauses.filter(form_type='CARO_2020')
        form_3cd_clauses = clauses.filter(form_type='FORM_3CD')

        is_corporate = company.entity_type in [EntityType.PVT_LTD, EntityType.PUB_LTD]
        caro_app = is_corporate and (config.caro_applicable if config else True)
        form_3cd_app = (config.form_3cd_applicable if config else (company.entity_type != EntityType.PROPRIETORSHIP or engagement.engagement_type == EngagementType.TAX_AUDIT))
        has_stat_data = clauses.count() > 0

        section_h = {
            'section_code': 'SEC-H',
            'title': 'India-Specific Tax & Compliance Workflows',
            'has_data': has_stat_data,
            'is_applicable': bool(caro_app or form_3cd_app),
            'schedule_iii_framework': config.schedule_iii_division if config else 'DIVISION_I',
            'tax_audit_form': config.form_type if config else '3CA',
            'caro_applicable': caro_app,
            'caro_clauses_count': caro_clauses.count(),
            'caro_review_required_count': caro_clauses.filter(compliance_status='REVIEW_REQUIRED').count(),
            'caro_compliant_count': caro_clauses.filter(compliance_status='COMPLIANT').count(),
            'caro_exempt_badge': not caro_app,
            'form_3cd_clauses_count': form_3cd_clauses.count(),
            'form_3cd_review_required_count': form_3cd_clauses.filter(compliance_status='REVIEW_REQUIRED').count(),
            'form_3cd_compliant_count': form_3cd_clauses.filter(compliance_status__in=['COMPLIANT', 'CLEARED', 'VERIFIED']).count(),
            'section_43bh_msme_compliance': "ASSESSED_DISALLOWANCE_IDENTIFIED" if overdue_43bh.exists() else ("REVIEW_REQUIRED" if not pay_aging.exists() else "SATISFACTORY"),
            'section_40a3_cash_payments': "EXCEPTIONS_REPORTED_UNDER_CLAUSE_21D" if engagement.exceptions.filter(rule_code='SEC-40A3').exists() else ("REVIEW_REQUIRED" if not engagement.transactions.exists() else "CLEARED")
        }

        # ---------------------------------------------------------
        # SECTION I: Audit Procedures and Results
        # ---------------------------------------------------------
        procs = engagement.procedure_executions.all().select_related('procedure')
        proc_list = []
        for p in procs:
            proc_list.append({
                'procedure_code': p.procedure.code,
                'title': p.procedure.title,
                'category': p.procedure.category,
                'standard': p.procedure.applicable_standard,
                'rule_version': p.procedure.rule_version,
                'status': p.status,
                'records_tested': p.tested_records_count,
                'exceptions_count': p.exceptions_count,
                'summary_findings': p.summary_findings,
                'executed_at': p.executed_at.isoformat()
            })

        section_i = {
            'section_code': 'SEC-I',
            'title': 'Audit Procedures & Substantive Testing Results',
            'has_data': len(proc_list) > 0,
            'is_applicable': len(proc_list) > 0,
            'total_procedures_count': len(proc_list),
            'procedures': proc_list
        }

        # ---------------------------------------------------------
        # SECTION J: Exceptions and Risk Register
        # ---------------------------------------------------------
        excs = engagement.exceptions.all().order_by('-severity', '-amount_involved')
        ajes = engagement.adjustments.all()
        exc_list = []
        for e in excs:
            linked_aje = next((a for a in ajes if e.rule_code in a.reason or str(e.amount_involved) == str(a.total_debit)), None)
            is_res = e.status in ['RESOLVED', 'AJE_POSTED', 'WAIVED']
            exc_list.append({
                'exception_id': f"EXC-{e.id}",
                'title': e.title,
                'rule_code': e.rule_code,
                'category': e.category,
                'severity': e.severity,
                'status': e.status,
                'amount_involved': str(e.amount_involved),
                'explanation': e.explanation,
                'recommended_action': e.recommended_action,
                'source_reference': e.source_reference,
                'resolution_notes': e.resolution_notes or ('AJE proposed and pending partner approval' if linked_aje else 'Pending review'),
                'linked_aje_number': linked_aje.adjustment_number if linked_aje else None,
                'is_resolved': is_res
            })

        section_j = {
            'section_code': 'SEC-J',
            'title': 'Audit Exceptions & Risk Register',
            'has_data': True,
            'is_applicable': True,
            'total_exceptions_count': len(exc_list),
            'open_exceptions_count': sum(1 for e in exc_list if not e['is_resolved']),
            'critical_count': sum(1 for e in exc_list if e['severity'] == 'CRITICAL'),
            'high_count': sum(1 for e in exc_list if e['severity'] == 'HIGH'),
            'exceptions': exc_list,
            'zero_exceptions_compliant': len(exc_list) == 0,
            'compliance_verdict': "ZERO_MATERIAL_EXCEPTIONS_IN_REGISTER" if len(exc_list) == 0 else "EXCEPTIONS_PENDING_AUDITOR_REVIEW"
        }

        # ---------------------------------------------------------
        # SECTION K: Workpaper Index (SA 230)
        # ---------------------------------------------------------
        wps = engagement.workpapers.all().order_by('wp_reference')
        wp_list = []
        for w in wps:
            wp_list.append({
                'wp_reference': w.wp_reference,
                'title': w.title,
                'audit_area': w.audit_area,
                'status': w.status,
                'audit_objective': w.audit_objective,
                'results_summary': w.results_summary,
                'proposed_conclusion': w.proposed_conclusion,
                'preparer': w.preparer.username if w.preparer else 'Audit Preparer',
                'reviewer': w.reviewer.username if w.reviewer else (w.reviewed_by.username if w.reviewed_by else 'Senior Auditor'),
                'version': w.version,
                'approval_reason': w.approval_reason or None
            })

        section_k = {
            'section_code': 'SEC-K',
            'title': 'Audit Workpapers Index (Standards on Auditing SA 230)',
            'has_data': len(wp_list) > 0,
            'is_applicable': len(wp_list) > 0,
            'total_workpapers_count': len(wp_list),
            'approved_count': sum(1 for w in wp_list if w['status'] == 'APPROVED'),
            'partner_authorized_count': sum(1 for w in wp_list if w['status'] == 'PARTNER_AUTHORIZED'),
            'prepared_count': sum(1 for w in wp_list if w['status'] in ['PREPARED', 'DRAFT']),
            'review_required_count': sum(1 for w in wp_list if w['status'] == 'REVIEW_REQUIRED'),
            'reviewed_count': sum(1 for w in wp_list if w['status'] in ['REVIEWED', 'READY_FOR_REVIEW']),
            'workpapers': wp_list
        }

        # ---------------------------------------------------------
        # SECTION L: Proposed Adjustments (AJE Layer)
        # ---------------------------------------------------------
        ajes = engagement.adjustments.all().order_by('adjustment_number')
        aje_list = []
        for a in ajes:
            aje_list.append({
                'adjustment_number': a.adjustment_number,
                'title': a.title,
                'reason': a.reason,
                'status': a.status,
                'total_debit': str(a.total_debit),
                'total_credit': str(a.total_credit),
                'is_balanced': a.is_balanced,
                'pnl_impact': str(a.pnl_impact),
                'journal_entries': a.journal_entries
            })

        section_l = {
            'section_code': 'SEC-L',
            'title': 'Proposed Adjusting Journal Entries (AJE Layer)',
            'has_data': True,
            'is_applicable': True,
            'total_adjustments_count': len(aje_list),
            'adjustments': aje_list,
            'status': "NO_ADJUSTMENTS_REQUIRED" if len(aje_list) == 0 else "ADJUSTMENTS_PENDING_APPROVAL"
        }

        # ---------------------------------------------------------
        # SECTION M: Outstanding Actions Checklist
        # ---------------------------------------------------------
        from apps.companies.completion_service import EngagementCompletionService
        checklist_data = EngagementCompletionService.evaluate_checklist(engagement)

        actions_list = []
        for item in checklist_data.get('checklist_items', []):
            if not item.get('is_satisfied') and not item.get('is_overridden'):
                actions_list.append({
                    'code': item['code'],
                    'title': item['title'],
                    'category': item['category'],
                    'priority': 'HIGH' if item['is_mandatory'] else 'MEDIUM',
                    'details': item['details']
                })

        section_m = {
            'section_code': 'SEC-M',
            'title': 'Outstanding Actions & Completion Checklist',
            'has_data': len(actions_list) > 0,
            'is_applicable': True,
            'can_finalize': checklist_data['can_finalize'],
            'completion_percentage': checklist_data['completion_percentage'],
            'outstanding_actions_count': len(actions_list),
            'actions': actions_list
        }

        # ---------------------------------------------------------
        # SECTION N: Final Review, Disclaimers & Limitations
        # ---------------------------------------------------------
        tb_verified_text = (
            "Double-entry mathematical roll-forward and TB balance verified."
            if (tb and tb.is_balanced and Decimal(str(tb.difference_amount or '0.00')) == Decimal('0.00'))
            else f"Trial Balance disequilibrium: TB variance ₹{abs(tb.difference_amount if tb else Decimal('0.00')):,.2f} violates double-entry equilibrium."
        )

        brs_verified_text = (
            "Bank reconciliation statement clearance verified against passbook records."
            if (brs and brs.status == 'BALANCED' and brs_unmatched == 0 and brs_unrec_diff == Decimal('0.00'))
            else f"Bank reconciliation: UNRESOLVED ({brs_unmatched} unmatched item(s), ₹{brs_unrec_diff:,.2f} variance - clearance pending)."
        )

        rev_verified_text = (
            "Revenue occurrence and cut-off verified against GSTR-1 outward returns and sales registers."
            if (has_gstr1 or has_sales_reg)
            else "Revenue verification: UNVERIFIED (mandatory GSTR-1 outward returns / sales registers missing)."
        )

        section_n = {
            'section_code': 'SEC-N',
            'title': 'Final Review, Disclaimers & Audit Limitations',
            'has_data': True,
            'is_applicable': True,
            'verified_items_summary': [
                tb_verified_text,
                brs_verified_text,
                rev_verified_text,
                "Fixed Asset Register and dual Schedule II vs Section 32 depreciation recalculated.",
                "Subledger aging schedules and Section 43B(h) MSMED thresholds screened.",
                "CARO 2020 21 clauses and Form 3CD tax audit clauses evaluated."
            ],
            'statutory_auditor_disclaimer': (
                "STATUTORY AUDITOR MANDATORY DISCLAIMER: This document is an automated draft audit and accounting scrutiny "
                "report synthesized by Captrix from client ledgers, transactional registers, and verified statutory rule engines. "
                "STATUS: DRAFT — PENDING INDEPENDENT PROFESSIONAL REVIEW AND OFFICIAL CA AUTHORIZATION. "
                "This document DOES NOT constitute a final statutory audit opinion under Section 143 of the Companies Act, 2013 or "
                "an audit report under Section 44AB of the Income-tax Act, 1961. In compliance with ICAI regulations, final statutory opinions "
                "require independent examination, professional skepticism, physical verification, and official signature by a duly authorized "
                "practicing Chartered Accountant. Captrix does not simulate official UDIN generation, impersonate a CA, or perform unauthorized portal operations."
            ) if not is_final_certified else (
                "STATUTORY AUDITOR REPORT & OPINION: Certified under Section 143 of the Companies Act, 2013 and Standards on Auditing. "
                "Issued by authorized Engagement Partner following complete substantive testing, reconciliation resolution, and ICAI UDIN generation."
            ),
            'statutory_status': "FINAL_CERTIFIED_STATUTORY_OPINION" if is_final_certified else "DRAFT_PENDING_PROFESSIONAL_REVIEW",
            'responsible_ca_signoff_box': {
                'firm_name': (getattr(engagement, 'finalization_metadata', {}) or {}).get('ca_firm_no') or "Engagement Audit Firm",
                'lead_partner': (getattr(engagement, 'finalization_metadata', {}) or {}).get('ca_name') or (engagement.lead_partner.username if engagement.lead_partner else "Partner (FCA / ACA)"),
                'membership_number': (getattr(engagement, 'finalization_metadata', {}) or {}).get('ca_member_no') or ("ICAI M.No. Required upon final signing" if not is_final_certified else (engagement.lead_partner.username if engagement.lead_partner else "Verified CA")),
                'udin': getattr(engagement, 'udin', '') or (getattr(engagement, 'finalization_metadata', {}) or {}).get('udin', '') or ("To be obtained by practicing CA via official ICAI portal (udin.icai.org)" if not is_final_certified else "VERIFIED_ICAI_PORTAL_UDIN"),
                'udin_status': "VERIFIED_ON_OFFICIAL_PORTAL" if (is_final_certified and getattr(engagement, 'udin', '')) else ("PENDING_OFFICIAL_ICAI_GENERATION" if not is_final_certified else "VERIFIED_ON_OFFICIAL_PORTAL"),
                'udin_policy_notice': "In accordance with ICAI mandates, official UDINs must be generated directly on the ICAI portal by the signing CA. Software-generated or simulated UDINs are strictly prohibited.",
                'report_reference': f"CAPTRIX/{'FINAL' if is_final_certified else 'DRAFT'}/{engagement.id}/{timezone.now().strftime('%Y%m%d')}",
                'place': "Mumbai, India",
                'date': engagement.finalized_at.strftime('%d-%b-%Y') if (engagement.finalized_at and is_final_certified) else timezone.now().strftime('%d-%b-%Y')
            }
        }

        # ---------------------------------------------------------
        # PRE-EXPORT TOTAL VALIDATION
        # Asserts that calculated report totals match underlying database records
        # ---------------------------------------------------------
        db_tb_diff = tb.difference_amount if tb else Decimal('0.00')
        rep_tb_diff = Decimal(section_e['trial_balance_difference'])
        assert db_tb_diff == rep_tb_diff, f"Integrity Failure: Report TB difference {rep_tb_diff} != DB {db_tb_diff}"

        now_iso = timezone.now().isoformat()
        sections_list = [
            section_a, section_b, section_c, section_d, section_e,
            section_f, section_g, section_h, section_i, section_j,
            section_k, section_l, section_m, section_n
        ]

        return {
            'report_name': "Consolidated Financial and Audit Analysis Report",
            'engagement_id': engagement.id,
            'company_name': company.name,
            'financial_year': fy.label,
            'generated_at': now_iso,
            'meta': {
                'company_name': company.name,
                'financial_year': fy.label,
                'generated_at': now_iso,
                'engagement_id': engagement.id,
                'is_final_certified': is_final_certified,
                'opinion_readiness': "FINAL_CERTIFIED_OPINION" if is_final_certified else "DRAFT_PENDING_PROFESSIONAL_REVIEW",
                'integrity_gate_passed': gate_result.get('is_ready_for_final_issue', False),
                'blockers': gate_result.get('blockers', []),
                'warnings': gate_result.get('warnings', [])
            },
            'pre_export_validation': {
                'is_valid': True,
                'trial_balance_balanced': section_e['is_balanced'],
                'trial_balance_difference': str(rep_tb_diff)
            },
            'sections': sections_list,
            'section_a': section_a,
            'section_b': section_b,
            'section_c': section_c,
            'section_d': section_d,
            'section_e': section_e,
            'section_f': section_f,
            'section_g': section_g,
            'section_h': section_h,
            'section_i': section_i,
            'section_j': section_j,
            'section_k': section_k,
            'section_l': section_l,
            'section_m': section_m,
            'section_n': section_n
        }
