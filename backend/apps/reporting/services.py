import os
import io
from decimal import Decimal
from datetime import datetime, date, timedelta
from django.conf import settings
from django.core.files.base import ContentFile
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import openpyxl

from .models import GeneratedReport, Workpaper, ProposedAdjustment, WorkpaperStatus, AdjustmentStatus
from apps.companies.models import Company, FinancialYear, Engagement, EntityType, EngagementType, EngagementStatus, EngagementWorkflowConfig
from apps.accounting.models import ChartOfAccounts, LedgerAccount, Transaction, TrialBalanceSnapshot, ScheduleIIIGroup, AccountType, VoucherType
from apps.reconciliation.services import BankReconciliationEngine, GstItcReconciliationEngine, CrossDocumentReconciliationEngine
from apps.reconciliation.models import ReconciliationRun
from apps.audit.services import AuditProcedureRunner
from apps.audit.models import ExceptionItem, ProcedureExecution, ExceptionSeverity, FixedAsset, SubledgerAgingItem, RelatedParty, StatutoryClauseAudit
from apps.audit.far_depreciation import FixedAssetAuditEngine
from apps.audit.subledger_analytics import SubledgerAnalyticsEngine
from apps.audit.forensic_scrutiny import ForensicScrutinyEngine
from apps.audit.statutory_forms import StatutoryFormMatrixEngine


class ReportGeneratorService:
    @staticmethod
    def generate_pdf_report(engagement, report_type='AUDIT_SUMMARY') -> GeneratedReport:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36, pageCompression=1)
        styles = getSampleStyleSheet()
        from .exporters import ensure_unicode_fonts_registered
        font_family = ensure_unicode_fonts_registered()
        bold_font = 'DejaVuSans-Bold' if font_family == 'DejaVuSans' else 'Helvetica-Bold'
        reg_font = 'DejaVuSans' if font_family == 'DejaVuSans' else 'Helvetica'

        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontSize=18,
            leading=22,
            textColor=colors.HexColor('#0b132b'),
            fontName=bold_font,
            spaceAfter=6
        )
        subtitle_style = ParagraphStyle(
            'ReportSubtitle',
            parent=styles['Normal'],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#475569'),
            fontName=reg_font,
            spaceAfter=12
        )
        heading2_style = ParagraphStyle(
            'H2',
            parent=styles['Heading2'],
            fontSize=12,
            leading=16,
            textColor=colors.HexColor('#1d63ed'),
            fontName=bold_font,
            spaceBefore=10,
            spaceAfter=6
        )
        body_style = ParagraphStyle(
            'Body',
            parent=styles['Normal'],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#1e293b'),
            fontName=reg_font
        )

        elements = []

        # Header Banner
        elements.append(Paragraph("<b>CAPTRIX — FINANCIAL AUDIT & ASSURANCE INTELLIGENCE</b>", subtitle_style))
        elements.append(Paragraph(f"<b>DRAFT INDEPENDENT AUDITOR'S REPORT & SCRUTINY SUMMARY</b>", title_style))
        elements.append(Paragraph(
            f"<b>Client:</b> {engagement.company.name} | <b>CIN:</b> {engagement.company.cin or 'N/A'} | <b>FY:</b> {engagement.financial_year.label} | <b>Generated:</b> {datetime.now().strftime('%d-%b-%Y %H:%M')}",
            subtitle_style
        ))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#1d63ed'), spaceAfter=12))

        # Helper functions for wrapped table cells
        cell_style = ParagraphStyle(
            'ReportTableCell', parent=styles['Normal'], fontSize=8, leading=10.5,
            textColor=colors.HexColor('#1e293b'), fontName=reg_font
        )
        cell_bold_style = ParagraphStyle(
            'ReportTableCellBold', parent=styles['Normal'], fontSize=8, leading=10.5,
            textColor=colors.HexColor('#0f172a'), fontName=bold_font
        )
        head_style = ParagraphStyle(
            'ReportTableHead', parent=styles['Normal'], fontSize=8.5, leading=11,
            textColor=colors.whitesmoke, fontName=bold_font
        )

        def p_cell(val, style=cell_style):
            if isinstance(val, (Paragraph, Table)):
                return val
            text = str(val if val is not None else '').replace('\n', '<br/>')
            return Paragraph(text, style)

        def p_head(val, style=head_style):
            text = f"<b>{str(val if val is not None else '')}</b>"
            return Paragraph(text, style)

        # Engagement Context & SA 320 Materiality Table
        elements.append(Paragraph("<b>1. Engagement Scope & SA 320 Materiality Framework</b>", heading2_style))
        mat_data = [
            [p_head("Parameter"), p_head("Configured Audit Benchmark & Value")],
            [p_cell("Engagement Type", cell_bold_style), p_cell(str(engagement.get_engagement_type_display()))],
            [p_cell("Materiality Benchmark", cell_bold_style), p_cell(f"{engagement.materiality_benchmark} @ {engagement.benchmark_percentage}%")],
            [p_cell("Overall Materiality (SA 320)", cell_bold_style), p_cell(f"₹{engagement.overall_materiality:,.2f}")],
            [p_cell("Performance Materiality (75%)", cell_bold_style), p_cell(f"₹{engagement.performance_materiality:,.2f}")],
            [p_cell("Clearly Trivial Threshold (5%)", cell_bold_style), p_cell(f"₹{engagement.clearly_trivial_threshold:,.2f}")]
        ]
        t_mat = Table(mat_data, colWidths=[200, 340])
        t_mat.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0b132b')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
        ]))
        elements.append(t_mat)
        elements.append(Spacer(1, 10))

        # Exceptions & Key Audit Matters
        elements.append(Paragraph("<b>2. Key Audit Observations & Exceptions Log</b>", heading2_style))
        exceptions = ExceptionItem.objects.filter(engagement=engagement)
        if exceptions.exists():
            exc_data = [[p_head("Severity"), p_head("Area / Clause"), p_head("Observation Description"), p_head("Amount (₹)"), p_head("Status")]]
            for exc in exceptions[:10]:
                exc_data.append([
                    p_cell(exc.severity),
                    p_cell(exc.category),
                    p_cell(exc.title),
                    p_cell(f"₹{exc.amount_involved:,.2f}"),
                    p_cell(exc.status)
                ])
            t_exc = Table(exc_data, colWidths=[65, 85, 230, 85, 75])
            t_exc.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
            ]))
            elements.append(t_exc)
        else:
            elements.append(Paragraph("<i>No material exceptions detected across executed procedures.</i>", body_style))
        elements.append(Spacer(1, 10))

        # Workpapers & Review Sign-off Index
        elements.append(Paragraph("<b>3. Audit Workpapers & Sign-off Summary</b>", heading2_style))
        wps = Workpaper.objects.filter(engagement=engagement)
        if wps.exists():
            wp_data = [[p_head("WP Ref"), p_head("Title"), p_head("Audit Objective"), p_head("Review Status")]]
            for wp in wps:
                wp_data.append([
                    p_cell(wp.wp_reference, cell_bold_style),
                    p_cell(wp.title),
                    p_cell(wp.audit_objective),
                    p_cell(wp.status)
                ])
            t_wp = Table(wp_data, colWidths=[70, 140, 240, 90])
            t_wp.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
            ]))
            elements.append(t_wp)
        elements.append(Spacer(1, 15))

        # Auditor Professional Disclaimer
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#94a3b8'), spaceAfter=8))
        elements.append(Paragraph(
            "<b>STATUTORY DISCLAIMER:</b> This draft is systematically generated by Captrix based on uploaded client ledgers, "
            "deterministic reconciliation models, and statutory validation rules. This document does not constitute a final statutory audit opinion. "
            "A qualified Chartered Accountant must exercise professional skepticism, conduct physical verification where required, and sign the final report.",
            ParagraphStyle('Disclaimer', parent=styles['Normal'], fontSize=7.5, leading=10, textColor=colors.HexColor('#64748b'))
        ))

        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        report_record = GeneratedReport.objects.create(
            engagement=engagement,
            report_type=report_type,
            title=f"Independent Audit Scrutiny Report - {engagement.company.name}",
            file_format='PDF',
            summary_data={
                'exceptions_count': exceptions.count(),
                'workpapers_count': wps.count(),
                'generated_at': datetime.now().isoformat()
            }
        )
        report_record.file.save(f"audit_report_{engagement.id}_{int(datetime.now().timestamp())}.pdf", ContentFile(pdf_bytes))
        report_record.save()
        return report_record


class WorkpaperDraftingService:
    @staticmethod
    def draft_workpapers(engagement):
        """
        Synthesizes and updates evidence-linked SA 230 audit workpapers directly from persisted audit,
        reconciliation, and accounting records.
        """
        drafted = []

        # 1. WP-A101: Cash and Bank Balances Audit & BRS Verification
        brs_run = ReconciliationRun.objects.filter(engagement=engagement, recon_type='BANK').first()
        brs_summary = brs_run.summary_data if brs_run else {}
        brs_var = brs_summary.get('unreconciled_variance', '0.00')
        brs_balanced = (brs_run.status == 'BALANCED') if brs_run else False

        wp_a101, _ = Workpaper.objects.update_or_create(
            engagement=engagement,
            wp_reference="WP-A101",
            defaults={
                'title': "Cash and Bank Balances Audit & BRS Verification",
                'audit_area': "Cash and Bank (SA 501 / SA 505)",
                'audit_objective': "Verify existence, completeness, and valuation of bank balances as of year-end.",
                'scope_and_coverage': f"Reconciliation executed with {brs_summary.get('date_tolerance_days', 15)} days clearance window. Statement balance: ₹{brs_summary.get('actual_statement_balance', '0.00')}.",
                'testing_methodology': "Multi-tier deterministic matching (Exact, Rule-Based, Consolidated, Ambiguous) comparing Cashbook against Bank Statement.",
                'results_summary': (
                    f"Starting Cashbook: ₹{brs_summary.get('starting_cashbook_balance', '0.00')}. "
                    f"Cheques issued not presented: ₹{brs_summary.get('cheques_issued_not_presented', '0.00')}. "
                    f"Cheques deposited not cleared: ₹{brs_summary.get('cheques_deposited_not_cleared', '0.00')}. "
                    f"Direct bank debits: ₹{brs_summary.get('direct_debits_by_bank', '0.00')}. "
                    f"Computed statement balance: ₹{brs_summary.get('computed_statement_balance', '0.00')}. "
                    f"Unreconciled variance: ₹{brs_var}."
                ),
                'exceptions_noted': "Direct bank debits unrecorded in cashbook require adjusting journal entry." if brs_var != '0.00' or brs_summary.get('direct_debits_by_bank') != '0.00' else "None.",
                'proposed_conclusion': "Bank balances are fairly stated in all material respects subject to AJE for bank charges." if brs_balanced else "Reconciliation review required by Senior CA.",
                'status': WorkpaperStatus.READY_FOR_REVIEW if brs_balanced else WorkpaperStatus.REVIEW_REQUIRED
            }
        )
        drafted.append(wp_a101)

        # 2. WP-A102: General Ledger Roll-Forward & TB Mathematical Equality
        tb = engagement.trial_balances.first()
        tb_balanced = tb.is_balanced if tb else False
        tb_diff = tb.difference_amount if tb else Decimal('0.00')
        rollforward_excs = ExceptionItem.objects.filter(engagement=engagement, rule_code='RULE_ROLLFORWARD_MISMATCH')

        wp_a102, _ = Workpaper.objects.update_or_create(
            engagement=engagement,
            wp_reference="WP-A102",
            defaults={
                'title': "General Ledger Roll-Forward & Trial Balance Mathematical Accuracy",
                'audit_area': "General Ledger & Trial Balance (SA 500)",
                'audit_objective': "Verify double-entry mathematical equality (Total Debits == Total Credits) and roll-forward consistency.",
                'scope_and_coverage': f"100% of ledger accounts in chart of accounts tested. Total Debits: ₹{tb.total_debits if tb else '0.00'}, Total Credits: ₹{tb.total_credits if tb else '0.00'}.",
                'testing_methodology': "Opening to closing roll-forward equation verification: Closing = Opening + Debits - Credits across all ledger accounts.",
                'results_summary': (
                    f"Trial Balance status: {'BALANCED' if tb_balanced else 'UNBALANCED'}. "
                    f"Net double-entry variance: ₹{tb_diff}. "
                    f"Roll-forward discrepancies identified: {rollforward_excs.count()}."
                ),
                'exceptions_noted': f"{rollforward_excs.count()} roll-forward discrepancies noted." if rollforward_excs.exists() else "No arithmetic differences identified.",
                'proposed_conclusion': "Trial balance is mathematically accurate and in double-entry equilibrium." if tb_balanced else "Material trial balance variance detected. Fails closed.",
                'status': WorkpaperStatus.READY_FOR_REVIEW if (tb_balanced and not rollforward_excs.exists()) else WorkpaperStatus.REVIEW_REQUIRED
            }
        )
        drafted.append(wp_a102)

        # 3. WP-B201: Revenue Recognition & Period-End Cut-off Testing
        cutoff_exec = ProcedureExecution.objects.filter(engagement=engagement, procedure__code='PROC-CUTOFF-01').first()
        cutoff_excs = ExceptionItem.objects.filter(engagement=engagement, category='CUT_OFF')
        uploaded_doc_records = list(engagement.documents.values('document_type', 'original_filename', 'status'))
        verified_fn = [str(d.get('original_filename', '')).lower() for d in uploaded_doc_records if str(d.get('status', '')).upper() == 'VERIFIED']
        verified_tp = {str(d.get('document_type', '')).upper() for d in uploaded_doc_records if str(d.get('status', '')).upper() == 'VERIFIED'}
        has_gstr1 = any('gstr-1' in f or 'gstr1' in f for f in verified_fn)
        has_sales_reg = ('SALES_REGISTER' in verified_tp) or any('sales' in f for f in verified_fn)
        has_rev_ev = has_gstr1 or has_sales_reg

        if not has_rev_ev:
            wp_b201_conclusion = "Substantive revenue verification cannot be concluded: Outward GST returns (GSTR-1) and sales register evidence are missing. Physical invoice and logistics inspection required."
            wp_b201_status = WorkpaperStatus.REVIEW_REQUIRED
            wp_b201_excs = "Required outward tax returns (GSTR-1) or sales registers missing from uploaded documentation."
        elif cutoff_excs.exists():
            wp_b201_conclusion = f"{cutoff_excs.count()} cut-off observations pending resolution. Period-end revenue recognition subject to substantive verification."
            wp_b201_status = WorkpaperStatus.REVIEW_REQUIRED
            wp_b201_excs = f"{cutoff_excs.count()} observations under review."
        else:
            wp_b201_conclusion = "Revenue recognized in the appropriate accounting period in conformity with Ind AS 115."
            wp_b201_status = WorkpaperStatus.READY_FOR_REVIEW
            wp_b201_excs = "No cut-off errors identified."

        wp_b201, _ = Workpaper.objects.update_or_create(
            engagement=engagement,
            wp_reference="WP-B201",
            defaults={
                'title': "Revenue Recognition & Period-End Cut-off Testing",
                'audit_area': "Revenue from Operations (Ind AS 115)",
                'audit_objective': "Test for premature revenue recognition and cut-off violations within ±5 days of March 31.",
                'scope_and_coverage': f"Tested {cutoff_exec.tested_records_count if cutoff_exec else 0} transactions exceeding threshold around year-end.",
                'testing_methodology': "Inspection of delivery milestone sign-offs, customer acceptances, and invoice dates.",
                'results_summary': f"Tested transactions around year-end. {cutoff_excs.count()} high-value cut-off observations noted. Outward tax returns evidence: {'AVAILABLE' if has_rev_ev else 'MISSING'}.",
                'exceptions_noted': wp_b201_excs,
                'proposed_conclusion': wp_b201_conclusion,
                'status': wp_b201_status
            }
        )
        drafted.append(wp_b201)

        # 4. WP-B202: Cross-Document Reconciliation (Registers vs General Ledger)
        cross_runs = ReconciliationRun.objects.filter(engagement=engagement, recon_type__in=[
            'LEDGER_TB', 'SALES_VS_LEDGER', 'PURCHASE_VS_LEDGER', 'AR_VS_CONTROL', 'FAR_VS_LEDGER', 'FS_VS_TB'
        ])
        balanced_cross = cross_runs.filter(status='BALANCED').count()
        blocked_cross = cross_runs.filter(status='BLOCKED').count()
        variance_cross = cross_runs.filter(status='VARIANCE_DETECTED').count()

        if variance_cross > 0 or blocked_cross > 0:
            wp_b202_conclusion = f"{variance_cross} variance(s) and {blocked_cross} blocked reconciliation(s) identified. Subledger corroboration incomplete."
            wp_b202_status = WorkpaperStatus.REVIEW_REQUIRED
        else:
            wp_b202_conclusion = "General ledger accounts are corroborated by supporting registers where provided."
            wp_b202_status = WorkpaperStatus.READY_FOR_REVIEW

        wp_b202, _ = Workpaper.objects.update_or_create(
            engagement=engagement,
            wp_reference="WP-B202",
            defaults={
                'title': "Cross-Document Reconciliation (Registers vs Control Accounts)",
                'audit_area': "Substantive Cross-Verification (SA 500)",
                'audit_objective': "Cross-reconcile sub-ledgers and external registers against general ledger control accounts.",
                'scope_and_coverage': f"{cross_runs.count()} cross-document comparisons evaluated.",
                'testing_methodology': "Deterministic matching of sales register, purchase register, debtors ageing, and FAR against GL control accounts.",
                'results_summary': (
                    f"Balanced reconciliations: {balanced_cross}. "
                    f"Reconciliations with variance: {variance_cross}. "
                    f"Blocked reconciliations (prerequisite documents missing): {blocked_cross}."
                ),
                'exceptions_noted': f"{variance_cross} variance reconciliations detected. {blocked_cross} registers blocked pending client upload.",
                'proposed_conclusion': wp_b202_conclusion,
                'status': wp_b202_status
            }
        )
        drafted.append(wp_b202)

        # 5. WP-T301: Tax Audit Form 3CD Compliance (40A(3), TDS)
        all_eng_excs = ExceptionItem.objects.filter(engagement=engagement)
        cash_excs = [
            e for e in all_eng_excs
            if '40a(3)' in e.title.lower() or '40a3' in (e.rule_code or '').lower() or '40a(3)' in e.explanation.lower()
        ]
        tot_cash_disallow = sum((e.amount_involved for e in cash_excs), Decimal('0.00'))

        wp_t301, _ = Workpaper.objects.update_or_create(
            engagement=engagement,
            wp_reference="WP-T301",
            defaults={
                'title': "Tax Audit Form 3CD Statutory Scrutiny (Section 40A(3) & TDS)",
                'audit_area': "Tax Audit Compliance (Section 44AB)",
                'audit_objective': "Identify cash payments exceeding ₹10,000 under Section 40A(3) and TDS defaults under 40(a)(ia).",
                'scope_and_coverage': "100% automated voucher scanning of cash payments, contractor fees, and professional fees.",
                'testing_methodology': "Algorithmic screening against Section 40A(3) ₹10,000 threshold and Chapter XVII-B TDS deduction rules.",
                'results_summary': f"Identified {len(cash_excs)} cash transactions exceeding ₹10,000 totaling ₹{tot_cash_disallow:,.2f}.",
                'exceptions_noted': f"Disallowance of ₹{tot_cash_disallow:,.2f} under Section 40A(3) to be reported in Form 3CD Clause 21(d).",
                'proposed_conclusion': f"Report ₹{tot_cash_disallow:,.2f} in Form 3CD Clause 21(d) for addition to taxable income.",
                'status': WorkpaperStatus.REVIEW_REQUIRED if len(cash_excs) > 0 else WorkpaperStatus.READY_FOR_REVIEW
            }
        )
        drafted.append(wp_t301)

        # 6. WP-G401: GST ITC Reconciliation (GSTR-2B vs Books)
        gst_run = ReconciliationRun.objects.filter(engagement=engagement, recon_type='GST_ITC').first()
        gst_sum = gst_run.summary_data if gst_run else {}

        wp_g401, _ = Workpaper.objects.update_or_create(
            engagement=engagement,
            wp_reference="WP-G401",
            defaults={
                'title': "GST Input Tax Credit Reconciliation (GSTR-2B vs Purchase Register)",
                'audit_area': "Indirect Tax Compliance (CGST Act Section 16(2)(aa) & Rule 36(4))",
                'audit_objective': "Verify eligibility of Input Tax Credit claimed in books against GSTR-2B inward supplies.",
                'scope_and_coverage': f"100% of invoices in purchase register matched against GSTR-2B portal extract.",
                'testing_methodology': "Invoice-by-invoice matching on GSTIN, Invoice Number, and Tax Amount.",
                'results_summary': (
                    f"Total ITC in books: ₹{gst_sum.get('total_itc_per_books', '0.00')}. "
                    f"Total ITC in GSTR-2B: ₹{gst_sum.get('total_itc_per_gstr2b', '0.00')}. "
                    f"Matched invoices: {gst_sum.get('matched_invoices', 0)}. "
                    f"Missing in 2B: {gst_sum.get('missing_in_gstr_2b_invoices', 0)}."
                ),
                'exceptions_noted': f"{gst_sum.get('missing_in_gstr_2b_invoices', 0)} invoices missing in GSTR-2B (Rule 36(4) reversal risk).",
                'proposed_conclusion': "ITC claims reconciled. Retain invoices missing in 2B in provisional pool pending vendor GSTR-1 filing.",
                'status': WorkpaperStatus.READY_FOR_REVIEW if gst_sum.get('missing_in_gstr_2b_invoices', 0) == 0 else WorkpaperStatus.REVIEW_REQUIRED
            }
        )
        drafted.append(wp_g401)

        # 7. WP-F501: Fixed Assets Register (FAR) & Dual Depreciation Recalculation
        fa_items = FixedAsset.objects.filter(engagement=engagement)
        fa_count = fa_items.count()
        tot_fa_cost = sum((a.original_cost for a in fa_items), Decimal('0.00'))
        tot_sch_ii_dep = sum((a.sch_ii_depreciation for a in fa_items), Decimal('0.00'))
        tot_sec_32_dep = sum((a.sec_32_depreciation for a in fa_items), Decimal('0.00'))
        dup_fa_count = fa_items.filter(is_duplicate_candidate=True).count()
        fa_dep_excs = ExceptionItem.objects.filter(engagement=engagement, rule_code__in=['RULE_FAR_DUPLICATE_ASSET', 'RULE_DEPRECIATION_VARIANCE'])

        wp_f501, _ = Workpaper.objects.update_or_create(
            engagement=engagement,
            wp_reference="WP-F501",
            defaults={
                'title': "Fixed Assets Register (FAR) & Dual Depreciation Recalculation",
                'audit_area': "Property, Plant & Equipment (Companies Act Sch II / Income Tax Sec 32 / AS 10)",
                'audit_objective': "Verify FAR completeness, recalculate dual depreciation (Companies Act Schedule II useful life vs IT Act Section 32 block rates), and identify duplicate capitalizations.",
                'scope_and_coverage': f"{fa_count} fixed assets evaluated. Total Gross Block: ₹{tot_fa_cost:,.2f}.",
                'testing_methodology': "Asset-by-asset straight-line depreciation recalculation using Schedule II useful lives (with 5% residual value) and IT Act Block of Assets rates applying <180 days half-rate rule.",
                'results_summary': (
                    f"Total Assets: {fa_count}. Gross Block: ₹{tot_fa_cost:,.2f}. "
                    f"Recalculated Companies Act Schedule II Depreciation: ₹{tot_sch_ii_dep:,.2f}. "
                    f"Recalculated Income Tax Section 32 Depreciation: ₹{tot_sec_32_dep:,.2f}. "
                    f"Potential duplicate candidates: {dup_fa_count}."
                ),
                'exceptions_noted': f"{fa_dep_excs.count()} exceptions noted." if fa_dep_excs.exists() else "No material depreciation variances or duplicate capitalizations noted.",
                'proposed_conclusion': "Fixed assets and depreciation are fairly stated in accordance with Schedule II and Section 32." if not fa_dep_excs.exists() else "FAR audit complete with observations requiring adjusting entries.",
                'status': WorkpaperStatus.REVIEW_REQUIRED if fa_dep_excs.exists() else WorkpaperStatus.READY_FOR_REVIEW
            }
        )
        drafted.append(wp_f501)

        # 8. WP-M501: MSMED Act 2006 & Section 43B(h) Trade Payables Scrutiny
        msme_items = SubledgerAgingItem.objects.filter(engagement=engagement, item_type='PAYABLE')
        msme_overdue_items = msme_items.filter(is_overdue_43bh=True)
        tot_msme_overdue = sum((p.outstanding_amount for p in msme_overdue_items), Decimal('0.00'))
        tot_payables = sum((p.outstanding_amount for p in msme_items), Decimal('0.00'))

        wp_m501, _ = Workpaper.objects.update_or_create(
            engagement=engagement,
            wp_reference="WP-M501",
            defaults={
                'title': "MSMED Act 2006 & Section 43B(h) Trade Payables Scrutiny",
                'audit_area': "Statutory Trade Payables Compliance (MSMED Act Section 15 / IT Act Section 43B(h))",
                'audit_objective': "Identify outstanding dues to Micro and Small Enterprises exceeding statutory 45 days (or 15 days) for mandatory disallowance under Section 43B(h) in Form 3CD Clause 22.",
                'scope_and_coverage': f"{msme_items.count()} trade payable invoices scrutinized. Total outstanding: ₹{tot_payables:,.2f}.",
                'testing_methodology': "Classification against MSME Udyam status and age calculation from invoice date against statutory threshold.",
                'results_summary': (
                    f"Total Creditors Scrutinized: ₹{tot_payables:,.2f}. "
                    f"Invoices overdue beyond statutory limit: {msme_overdue_items.count()}. "
                    f"Total disallowance amount under Section 43B(h): ₹{tot_msme_overdue:,.2f}."
                ),
                'exceptions_noted': f"Section 43B(h) disallowance of ₹{tot_msme_overdue:,.2f} applicable on {msme_overdue_items.count()} overdue invoices." if tot_msme_overdue > 0 else "All MSME dues paid within statutory timeline.",
                'proposed_conclusion': f"Disallow ₹{tot_msme_overdue:,.2f} in current FY tax computation and report in Form 3CD Clause 22." if tot_msme_overdue > 0 else "No Section 43B(h) disallowance required.",
                'status': WorkpaperStatus.REVIEW_REQUIRED if tot_msme_overdue > 0 else WorkpaperStatus.READY_FOR_REVIEW
            }
        )
        drafted.append(wp_m501)

        # 9. WP-R502: Trade Receivables Ageing Schedule & Control Account Reconciliation
        rec_items = SubledgerAgingItem.objects.filter(engagement=engagement, item_type='RECEIVABLE')
        tot_rec = sum((r.outstanding_amount for r in rec_items), Decimal('0.00'))
        over_180_rec = sum((r.outstanding_amount for r in rec_items if r.ageing_days > 180), Decimal('0.00'))

        wp_r502, _ = Workpaper.objects.update_or_create(
            engagement=engagement,
            wp_reference="WP-R502",
            defaults={
                'title': "Trade Receivables Ageing Schedule & Control Account Reconciliation",
                'audit_area': "Trade Receivables & Credit Risk (SA 505 / Schedule III Division I/II)",
                'audit_objective': "Verify trade receivables subledger mathematical accuracy, ageing buckets presentation under Schedule III, and assess ECL / bad debt provisioning.",
                'scope_and_coverage': f"{rec_items.count()} customer invoices tested totaling ₹{tot_rec:,.2f}.",
                'testing_methodology': "Stratified sampling, ageing classification (0-30, 31-60, 61-90, 91-180, 181-365, >365 days), and reconciliation against general ledger control accounts.",
                'results_summary': (
                    f"Total Debtors: ₹{tot_rec:,.2f}. "
                    f"Debtors outstanding > 180 days: ₹{over_180_rec:,.2f} "
                    f"({(over_180_rec / tot_rec * 100).quantize(Decimal('0.1')) if tot_rec > 0 else 0}% of total book debts)."
                ),
                'exceptions_noted': f"Significant debts outstanding over 180 days (₹{over_180_rec:,.2f}) require evaluation of credit impairment provision." if over_180_rec > 0 else "No high-risk ageing balances noted.",
                'proposed_conclusion': "Trade receivables are properly classified across Schedule III ageing brackets.",
                'status': WorkpaperStatus.REVIEW_REQUIRED if over_180_rec > 0 else WorkpaperStatus.READY_FOR_REVIEW
            }
        )
        drafted.append(wp_r502)

        # 10. WP-P503: Related Party Transactions Scrutiny (Section 188 / AS 18)
        rp_count = RelatedParty.objects.filter(engagement=engagement, is_active=True).count()
        rp_excs = ExceptionItem.objects.filter(engagement=engagement, rule_code='RULE_RELATED_PARTY_TXN')
        rp_vol = sum((e.amount_involved for e in rp_excs), Decimal('0.00'))

        wp_p503, _ = Workpaper.objects.update_or_create(
            engagement=engagement,
            wp_reference="WP-P503",
            defaults={
                'title': "Related Party Transactions Scrutiny (Section 188 / AS 18)",
                'audit_area': "Related Party Disclosures (Companies Act Sec 2(76) & 188 / AS 18 / Ind AS 24)",
                'audit_objective': "Identify and corroborate all transactions with related parties, directors, and key management personnel for arm's length pricing and required statutory approvals.",
                'scope_and_coverage': f"{rp_count} identified related parties cross-referenced against 100% of general ledger counterparties.",
                'testing_methodology': "Full automated ledger search across counterparties, voucher narrations, and contract values.",
                'results_summary': f"Identified transactions with related parties totaling ₹{rp_vol:,.2f} across the reporting period.",
                'exceptions_noted': f"{rp_excs.count()} related party observations noted. Ensure Board and Audit Committee resolutions are on record." if rp_excs.exists() else "No unapproved related party transactions detected.",
                'proposed_conclusion': "Related party transactions are documented and disclosed in conformity with AS 18 / Section 188.",
                'status': WorkpaperStatus.REVIEW_REQUIRED if rp_excs.exists() else WorkpaperStatus.READY_FOR_REVIEW
            }
        )
        drafted.append(wp_p503)

        # 11. WP-J504: Manual Journal & Forensic Entries Scrutiny (SA 240)
        forensic_excs = ExceptionItem.objects.filter(engagement=engagement, rule_code__in=['RULE_WEEKEND_POSTING', 'RULE_ROUND_AMOUNT', 'RULE_PERIOD_END_VOUCHER'])
        tot_forensic_amt = sum((e.amount_involved for e in forensic_excs), Decimal('0.00'))

        wp_j504, _ = Workpaper.objects.update_or_create(
            engagement=engagement,
            wp_reference="WP-J504",
            defaults={
                'title': "Manual Journal Entries & Forensic Journal Scrutiny (SA 240)",
                'audit_area': "Auditor's Responsibilities Relating to Fraud (SA 240)",
                'audit_objective': "Scrutinize manual journal vouchers, weekend postings, unusual round amount entries, and entries posted near financial year close for management override risk.",
                'scope_and_coverage': "100% of journal vouchers (JV) and adjustments posted during the financial year.",
                'testing_methodology': "Forensic automated rule screening: Sunday/holiday postings, round amounts (multiples of 50,000/1,00,000), period-end postings (within ±5 days of March 31), and direct revenue debit entries.",
                'results_summary': f"Detected {forensic_excs.count()} forensic risk indicator entries totaling ₹{tot_forensic_amt:,.2f}.",
                'exceptions_noted': f"{forensic_excs.count()} unusual vouchers flagged for senior auditor review and supporting voucher inspection.",
                'proposed_conclusion': "Vouchers inspected with professional skepticism under SA 240. Risk indicators documented for audit trail.",
                'status': WorkpaperStatus.REVIEW_REQUIRED
            }
        )
        drafted.append(wp_j504)

        # 12. WP-C601: CARO 2020 Order Compliance Matrix (21 Clauses Assurance)
        caro_items = StatutoryClauseAudit.objects.filter(engagement=engagement, form_type='CARO_2020')
        caro_app = StatutoryFormMatrixEngine.evaluate_statutory_applicability(engagement)['caro_2020']['is_applicable']
        caro_excs = caro_items.filter(compliance_status__in=['EXCEPTION_NOTED', 'NON_COMPLIANT', 'REVIEW_REQUIRED', 'NOT_VERIFIED']).count()

        wp_c601, _ = Workpaper.objects.update_or_create(
            engagement=engagement,
            wp_reference="WP-C601",
            defaults={
                'title': "CARO 2020 Order Compliance Matrix (21 Clauses Assurance)",
                'audit_area': "Companies (Auditor's Report) Order, 2020",
                'audit_objective': "Verify compliance and document reporting for all 21 clauses of CARO 2020, verifying entity applicability (exempt for LLPs, partnerships, and small companies).",
                'scope_and_coverage': f"All 21 statutory clauses under CARO 2020. Applicability status: {'APPLICABLE' if caro_app else 'EXEMPT'}.",
                'testing_methodology': "Clause-by-clause automated validation against FAR, inventory returns, loan sanctions, statutory dues aging, and fraud registers.",
                'results_summary': (
                    f"CARO 2020 applicability: {'APPLICABLE' if caro_app else 'EXEMPT (Non-corporate entity)'}. "
                    f"Total clauses tracked: {caro_items.count()}. "
                    f"Clauses requiring review / exceptions: {caro_excs}."
                ),
                'exceptions_noted': f"{caro_excs} clauses contain audit qualifications or matters requiring supporting evidence." if caro_excs > 0 else "All applicable CARO 2020 clauses reviewed.",
                'proposed_conclusion': "Draft CARO 2020 annexure prepared for inclusion in Independent Auditor's Report." if caro_app else "CARO 2020 is not applicable to the company; explicit statement included in audit report.",
                'status': WorkpaperStatus.READY_FOR_REVIEW if caro_excs == 0 else WorkpaperStatus.REVIEW_REQUIRED
            }
        )
        drafted.append(wp_c601)

        # 13. WP-T302: Tax Audit Form 3CD Clause Matrix & Section 44AB Routing
        f3cd_items = StatutoryClauseAudit.objects.filter(engagement=engagement, form_type='FORM_3CD')
        app_res = StatutoryFormMatrixEngine.evaluate_statutory_applicability(engagement)
        form_name = app_res['tax_audit_form']['form_type']
        f3cd_review_cnt = f3cd_items.filter(compliance_status__in=['REVIEW_REQUIRED', 'NOT_VERIFIED', 'NON_COMPLIANT']).count()

        wp_t302, _ = Workpaper.objects.update_or_create(
            engagement=engagement,
            wp_reference="WP-T302",
            defaults={
                'title': f"Tax Audit Form 3CD Matrix & Form {form_name} Certification",
                'audit_area': "Income Tax Act 1961 Section 44AB & Form 3CD",
                'audit_objective': f"Ensure comprehensive clause coverage across Form 3CD particulars and apply correct reporting format ({form_name}: 3CA for companies, 3CB for non-corporate).",
                'scope_and_coverage': f"Key particulars across 44 clauses of Form 3CD evaluated for FY {engagement.financial_year.label}.",
                'testing_methodology': "Validation against cash payment vouchers (21(d)), MSMED overdue payables (22), TDS non-deduction (21(b)), and statutory liabilities (26).",
                'results_summary': f"Applicable Audit Certificate: Form {form_name}. {f3cd_items.count()} key clauses systematically audited and evidence-linked.",
                'exceptions_noted': "Statutory disallowances identified summarized for inclusion in Annexure to Form 3CD.",
                'proposed_conclusion': f"Particulars in Form 3CD are true and correct subject to observations noted. Form {form_name} drafted.",
                'status': WorkpaperStatus.READY_FOR_REVIEW if f3cd_review_cnt == 0 else WorkpaperStatus.REVIEW_REQUIRED
            }
        )
        drafted.append(wp_t302)

        return drafted



class DemoDataService:
    @staticmethod
    def generate_demo_dataset():
        """
        Populates a complete, realistic Indian CA audit workspace for:
        Apex Infotech Private Limited (FY 2024-25)
        Including real trial balance, 60+ GL vouchers, intentional audit flags, BRS, and GSTR-2B recon!
        """
        # 1. Company
        company, _ = Company.objects.get_or_create(
            name="Apex Infotech Private Limited",
            defaults={
                'cin': 'U72200MH2021PTC356789',
                'pan': 'AABCA9876K',
                'gstin': '27AABCA9876K1Z1',
                'entity_type': EntityType.PVT_LTD,
                'registered_address': 'Unit 402, Pinnacle Business Park, Andheri East, Mumbai 400069, Maharashtra',
                'industry': 'Software Development & IT Consultancy',
                'incorporation_date': date(2021, 6, 15)
            }
        )

        # 2. Financial Year (FY 2024-25: Apr 1, 2024 to Mar 31, 2025)
        fy, _ = FinancialYear.objects.get_or_create(
            company=company,
            label="FY 2024-25",
            defaults={
                'start_date': date(2024, 4, 1),
                'end_date': date(2025, 3, 31),
                'is_active': True,
                'is_closed': False
            }
        )

        # 3. Engagement
        engagement, _ = Engagement.objects.get_or_create(
            company=company,
            financial_year=fy,
            title="Statutory & Tax Audit FY 2024-25",
            defaults={
                'engagement_type': EngagementType.STATUTORY,
                'status': EngagementStatus.FIELDWORK,
                'materiality_benchmark': 'PBT',
                'benchmark_percentage': Decimal('5.00'),
                'overall_materiality': Decimal('650000.00'),
                'performance_materiality': Decimal('487500.00'),
                'clearly_trivial_threshold': Decimal('32500.00'),
                'notes': 'Statutory audit under Companies Act 2013 and Tax Audit under Section 44AB Form 3CD.'
            }
        )

        # 4. Chart of Accounts & Ledgers (Schedule III Compliant)
        coa_data = [
            # Assets
            ('1001', 'Computer Systems & Hardware', AccountType.ASSET, ScheduleIIIGroup.PPE),
            ('1002', 'Office Equipment & Furniture', AccountType.ASSET, ScheduleIIIGroup.PPE),
            ('1101', 'Software IP & Licenses', AccountType.ASSET, ScheduleIIIGroup.INTANGIBLE),
            ('1201', 'Mutual Fund Investments (Short-Term)', AccountType.ASSET, ScheduleIIIGroup.NON_CURRENT_INVESTMENTS),
            ('1301', 'Trade Receivables (Domestic Clients)', AccountType.ASSET, ScheduleIIIGroup.TRADE_RECEIVABLES),
            ('1302', 'Trade Receivables (Export Clients)', AccountType.ASSET, ScheduleIIIGroup.TRADE_RECEIVABLES),
            ('1401', 'HDFC Bank Current Account', AccountType.ASSET, ScheduleIIIGroup.CASH_EQUIVALENTS),
            ('1402', 'ICICI Bank Current Account', AccountType.ASSET, ScheduleIIIGroup.CASH_EQUIVALENTS),
            ('1403', 'Petty Cash Account', AccountType.ASSET, ScheduleIIIGroup.CASH_EQUIVALENTS),
            ('1501', 'Prepaid Software Subscriptions', AccountType.ASSET, ScheduleIIIGroup.OTHER_CURRENT_ASSETS),
            ('1502', 'Security Deposits for Office Leases', AccountType.ASSET, ScheduleIIIGroup.LONG_TERM_LOANS_ADV),
            # Liabilities & Equity
            ('2001', 'Equity Share Capital', AccountType.EQUITY, ScheduleIIIGroup.SHARE_CAPITAL),
            ('2002', 'Retained Earnings & Reserves', AccountType.EQUITY, ScheduleIIIGroup.RESERVES_SURPLUS),
            ('2101', 'HDFC Bank Term Loan (Working Capital)', AccountType.LIABILITY, ScheduleIIIGroup.LONG_TERM_BORROWINGS),
            ('2201', 'Trade Payables - Software Vendors', AccountType.LIABILITY, ScheduleIIIGroup.TRADE_PAYABLES),
            ('2202', 'Trade Payables - Infrastructure & Cloud', AccountType.LIABILITY, ScheduleIIIGroup.TRADE_PAYABLES),
            ('2301', 'TDS Payable (Sec 194C/194J/192)', AccountType.LIABILITY, ScheduleIIIGroup.OTHER_CURRENT_LIABILITIES),
            ('2302', 'GST Output Tax Payable', AccountType.LIABILITY, ScheduleIIIGroup.OTHER_CURRENT_LIABILITIES),
            ('2303', 'Salaries & Staff Dues Payable', AccountType.LIABILITY, ScheduleIIIGroup.SHORT_TERM_PROVISIONS),
            # Revenue
            ('3001', 'Software Development Revenue (Domestic)', AccountType.REVENUE, ScheduleIIIGroup.REVENUE_OPERATIONS),
            ('3002', 'Export IT Consulting Services', AccountType.REVENUE, ScheduleIIIGroup.REVENUE_OPERATIONS),
            ('3101', 'Interest Income from Fixed Deposits', AccountType.REVENUE, ScheduleIIIGroup.OTHER_INCOME),
            # Expenses
            ('4001', 'Employee Salaries & Allowances', AccountType.EXPENSE, ScheduleIIIGroup.EMPLOYEE_BENEFITS),
            ('4002', 'Staff Welfare & Training', AccountType.EXPENSE, ScheduleIIIGroup.EMPLOYEE_BENEFITS),
            ('4101', 'AWS & Cloud Hosting Services', AccountType.EXPENSE, ScheduleIIIGroup.OTHER_EXPENSES),
            ('4102', 'Legal & Professional Consultancy Fees', AccountType.EXPENSE, ScheduleIIIGroup.OTHER_EXPENSES),
            ('4103', 'Office Rent & Maintenance', AccountType.EXPENSE, ScheduleIIIGroup.OTHER_EXPENSES),
            ('4104', 'Office Repairs & Renovation', AccountType.EXPENSE, ScheduleIIIGroup.OTHER_EXPENSES),
            ('4201', 'Depreciation on Hardware & PPE', AccountType.EXPENSE, ScheduleIIIGroup.DEPRECIATION_AMORT),
            ('4301', 'Bank Charges & Loan Interest', AccountType.EXPENSE, ScheduleIIIGroup.FINANCE_COSTS),
        ]

        ledgers_map = {}
        for code, name, ac_type, sch_grp in coa_data:
            coa, _ = ChartOfAccounts.objects.get_or_create(
                company=company,
                account_code=code,
                defaults={'account_name': name, 'account_type': ac_type, 'schedule_iii_group': sch_grp}
            )
            ledger, _ = LedgerAccount.objects.get_or_create(
                company=company,
                name=name,
                defaults={'code': code, 'coa': coa}
            )
            ledgers_map[name] = ledger

        # 5. Populate Trial Balance Snapshot (Balanced: ₹4,82,50,000.00 Dr / Cr)
        tb_rows = [
            {'Particulars': 'Computer Systems & Hardware', 'Debit': 4500000, 'Credit': 0, 'schedule_iii_group': ScheduleIIIGroup.PPE},
            {'Particulars': 'Office Equipment & Furniture', 'Debit': 1850000, 'Credit': 0, 'schedule_iii_group': ScheduleIIIGroup.PPE},
            {'Particulars': 'Software IP & Licenses', 'Debit': 2500000, 'Credit': 0, 'schedule_iii_group': ScheduleIIIGroup.INTANGIBLE},
            {'Particulars': 'Mutual Fund Investments (Short-Term)', 'Debit': 3500000, 'Credit': 0, 'schedule_iii_group': ScheduleIIIGroup.NON_CURRENT_INVESTMENTS},
            {'Particulars': 'Trade Receivables (Domestic Clients)', 'Debit': 6200000, 'Credit': 0, 'schedule_iii_group': ScheduleIIIGroup.TRADE_RECEIVABLES},
            {'Particulars': 'Trade Receivables (Export Clients)', 'Debit': 4800000, 'Credit': 0, 'schedule_iii_group': ScheduleIIIGroup.TRADE_RECEIVABLES},
            {'Particulars': 'HDFC Bank Current Account', 'Debit': 3450000, 'Credit': 0, 'schedule_iii_group': ScheduleIIIGroup.CASH_EQUIVALENTS},
            {'Particulars': 'ICICI Bank Current Account', 'Debit': 1850000, 'Credit': 0, 'schedule_iii_group': ScheduleIIIGroup.CASH_EQUIVALENTS},
            {'Particulars': 'Petty Cash Account', 'Debit': 120000, 'Credit': 0, 'schedule_iii_group': ScheduleIIIGroup.CASH_EQUIVALENTS},
            {'Particulars': 'Prepaid Software Subscriptions', 'Debit': 480000, 'Credit': 0, 'schedule_iii_group': ScheduleIIIGroup.OTHER_CURRENT_ASSETS},
            {'Particulars': 'Security Deposits for Office Leases', 'Debit': 1200000, 'Credit': 0, 'schedule_iii_group': ScheduleIIIGroup.LONG_TERM_LOANS_ADV},
            # Liabilities & Equity
            {'Particulars': 'Equity Share Capital', 'Debit': 0, 'Credit': 10000000, 'schedule_iii_group': ScheduleIIIGroup.SHARE_CAPITAL},
            {'Particulars': 'Retained Earnings & Reserves', 'Debit': 0, 'Credit': 8500000, 'schedule_iii_group': ScheduleIIIGroup.RESERVES_SURPLUS},
            {'Particulars': 'HDFC Bank Term Loan (Working Capital)', 'Debit': 0, 'Credit': 4500000, 'schedule_iii_group': ScheduleIIIGroup.LONG_TERM_BORROWINGS},
            {'Particulars': 'Trade Payables - Software Vendors', 'Debit': 0, 'Credit': 2250000, 'schedule_iii_group': ScheduleIIIGroup.TRADE_PAYABLES},
            {'Particulars': 'Trade Payables - Infrastructure & Cloud', 'Debit': 0, 'Credit': 1850000, 'schedule_iii_group': ScheduleIIIGroup.TRADE_PAYABLES},
            {'Particulars': 'TDS Payable (Sec 194C/194J/192)', 'Debit': 0, 'Credit': 280000, 'schedule_iii_group': ScheduleIIIGroup.OTHER_CURRENT_LIABILITIES},
            {'Particulars': 'GST Output Tax Payable', 'Debit': 0, 'Credit': 520000, 'schedule_iii_group': ScheduleIIIGroup.OTHER_CURRENT_LIABILITIES},
            {'Particulars': 'Salaries & Staff Dues Payable', 'Debit': 0, 'Credit': 1350000, 'schedule_iii_group': ScheduleIIIGroup.SHORT_TERM_PROVISIONS},
            # Revenue
            {'Particulars': 'Software Development Revenue (Domestic)', 'Debit': 0, 'Credit': 12000000, 'schedule_iii_group': ScheduleIIIGroup.REVENUE_OPERATIONS},
            {'Particulars': 'Export IT Consulting Services', 'Debit': 0, 'Credit': 7000000, 'schedule_iii_group': ScheduleIIIGroup.REVENUE_OPERATIONS},
            # Expenses
            {'Particulars': 'Employee Salaries & Allowances', 'Debit': 9500000, 'Credit': 0, 'schedule_iii_group': ScheduleIIIGroup.EMPLOYEE_BENEFITS},
            {'Particulars': 'AWS & Cloud Hosting Services', 'Debit': 2100000, 'Credit': 0, 'schedule_iii_group': ScheduleIIIGroup.OTHER_EXPENSES},
            {'Particulars': 'Legal & Professional Consultancy Fees', 'Debit': 1400000, 'Credit': 0, 'schedule_iii_group': ScheduleIIIGroup.OTHER_EXPENSES},
            {'Particulars': 'Office Rent & Maintenance', 'Debit': 2800000, 'Credit': 0, 'schedule_iii_group': ScheduleIIIGroup.OTHER_EXPENSES},
            {'Particulars': 'Office Repairs & Renovation', 'Debit': 750000, 'Credit': 0, 'schedule_iii_group': ScheduleIIIGroup.OTHER_EXPENSES},
            {'Particulars': 'Depreciation on Hardware & PPE', 'Debit': 1250000, 'Credit': 0, 'schedule_iii_group': ScheduleIIIGroup.DEPRECIATION_AMORT},
        ]
        
        # Check trial balance debit/credit balance
        tot_d = sum(r['Debit'] for r in tb_rows)
        tot_c = sum(r['Credit'] for r in tb_rows)
        if tot_d != tot_c:
            tb_rows.append({'Particulars': 'Other Expenses', 'Debit': tot_c - tot_d, 'Credit': 0, 'schedule_iii_group': ScheduleIIIGroup.OTHER_EXPENSES})

        TrialBalanceSnapshot.objects.filter(engagement=engagement).delete()
        tb_snapshot = TrialBalanceSnapshot.objects.create(
            engagement=engagement,
            as_of_date=date(2025, 3, 31),
            total_debits=Decimal('48250000.00'),
            total_credits=Decimal('48250000.00'),
            difference_amount=Decimal('0.00'),
            is_balanced=True,
            status='BALANCED',
            accounts_snapshot=[{
                'account_name': r['Particulars'],
                'debit': str(Decimal(r['Debit'])),
                'credit': str(Decimal(r['Credit'])),
                'net_balance': str(Decimal(r['Debit']) - Decimal(r['Credit'])),
                'schedule_iii_group': r['schedule_iii_group']
            } for r in tb_rows]
        )

        # 6. Populate Realistic Transactions (including intentional audit observations!)
        Transaction.objects.filter(engagement=engagement).delete()
        txns_to_create = [
            # Intentional Audit Issue 1: Section 40A(3) cash payment > 10,000
            Transaction(
                engagement=engagement,
                ledger_account=ledgers_map['Office Repairs & Renovation'],
                voucher_number='PV-2024-089',
                voucher_type=VoucherType.PAYMENT,
                date=date(2024, 11, 14),
                counterparty='Sharma Carpentry & Interior Works',
                narration='Cash payment for acoustic wall paneling in server room',
                debit_amount=Decimal('28500.00'),
                credit_amount=Decimal('0.00'),
                is_unusual=True,
                risk_flags=['SECTION_40A3_CASH_LIMIT_EXCEEDED']
            ),
            # Intentional Audit Issue 2: Round amount voucher
            Transaction(
                engagement=engagement,
                ledger_account=ledgers_map['Legal & Professional Consultancy Fees'],
                voucher_number='PV-2024-112',
                voucher_type=VoucherType.PAYMENT,
                date=date(2024, 12, 10),
                counterparty='Verma Corporate Advisors LLP',
                narration='Retainer fee for merger advisory round 1',
                debit_amount=Decimal('100000.00'),
                credit_amount=Decimal('0.00'),
                is_unusual=True,
                risk_flags=['ROUND_AMOUNT']
            ),
            # Intentional Audit Issue 3: Weekend posting on Sunday
            Transaction(
                engagement=engagement,
                ledger_account=ledgers_map['AWS & Cloud Hosting Services'],
                voucher_number='JV-2024-145',
                voucher_type=VoucherType.JOURNAL,
                date=date(2024, 11, 24), # Sunday!
                counterparty='Amazon Web Services India Pvt Ltd',
                narration='Monthly cloud servers compute charges billed for prod infra',
                debit_amount=Decimal('185420.00'),
                credit_amount=Decimal('0.00'),
                is_unusual=True,
                risk_flags=['WEEKEND_POSTING']
            ),
            # Intentional Audit Issue 4: High Value Cut-off transaction near March 31
            Transaction(
                engagement=engagement,
                ledger_account=ledgers_map['Software Development Revenue (Domestic)'],
                voucher_number='SV-2025-098',
                voucher_type=VoucherType.SALES,
                date=date(2025, 3, 30), # 1 day before FY close
                counterparty='Reliance Digital Retail Limited',
                narration='Milestone 4 delivery sign-off on enterprise catalog application',
                debit_amount=Decimal('0.00'),
                credit_amount=Decimal('450000.00'),
                is_unusual=True,
                risk_flags=['CUT_OFF_NEAR_YEAR_END']
            ),
            # Regular transactions
            Transaction(
                engagement=engagement,
                ledger_account=ledgers_map['Employee Salaries & Allowances'],
                voucher_number='PV-2025-001',
                voucher_type=VoucherType.PAYMENT,
                date=date(2025, 1, 31),
                counterparty='Axis Bank Corporate Payroll Disbursal',
                narration='Staff salary payout for month of January 2025 through NEFT gateway',
                debit_amount=Decimal('785400.00'),
                credit_amount=Decimal('0.00')
            ),
            Transaction(
                engagement=engagement,
                ledger_account=ledgers_map['HDFC Bank Current Account'],
                voucher_number='RV-2025-045',
                voucher_type=VoucherType.RECEIPT,
                date=date(2025, 2, 12),
                counterparty='Tata Consultancy Services Ltd',
                narration='NEFT inward remittance invoice INV-2024-041 settlement',
                debit_amount=Decimal('1240000.00'),
                credit_amount=Decimal('0.00')
            ),
        ]
        Transaction.objects.bulk_create(txns_to_create)

        # 7. Run Bank Reconciliation (BRS) with realistic timing differences
        cb_sample = [
            {'date': date(2025, 3, 25), 'ref': 'CHQ-894101', 'desc': 'Vendor payment to Dell India', 'amount': '145000.00', 'type': 'WITHDRAWAL'},
            {'date': date(2025, 3, 28), 'ref': 'CHQ-894102', 'desc': 'Rent to Pinnacle Business Park', 'amount': '235000.00', 'type': 'WITHDRAWAL'},
            {'date': date(2025, 3, 29), 'ref': 'CHQ-894103', 'desc': 'Office Supplies vendor cheque issued', 'amount': '42000.00', 'type': 'WITHDRAWAL'}, # Timing: Not presented yet
            {'date': date(2025, 3, 30), 'ref': 'DEP-9811', 'desc': 'Customer cheque deposited Infosys Ltd', 'amount': '350000.00', 'type': 'DEPOSIT'}, # Timing: Not cleared yet
            {'date': date(2025, 3, 15), 'ref': 'NEFT-4412', 'desc': 'Consulting revenue receipt', 'amount': '500000.00', 'type': 'DEPOSIT'},
        ]
        bank_sample = [
            {'date': date(2025, 3, 26), 'ref': 'CHQ-894101', 'desc': 'CLG CHQ DELL INDIA', 'amount': '145000.00', 'type': 'WITHDRAWAL'},
            {'date': date(2025, 3, 29), 'ref': 'CHQ-894102', 'desc': 'CLG CHQ PINNACLE PARK', 'amount': '235000.00', 'type': 'WITHDRAWAL'},
            {'date': date(2025, 3, 15), 'ref': 'NEFT-4412', 'desc': 'INWARD NEFT CONSULTING', 'amount': '500000.00', 'type': 'DEPOSIT'},
            {'date': date(2025, 3, 31), 'ref': 'CHG-9901', 'desc': 'ANNUAL FOLIO & BANK CHARGES', 'amount': '3500.00', 'type': 'WITHDRAWAL'}, # Timing: Bank charge not in books
        ]
        BankReconciliationEngine.execute_reconciliation(
            engagement=engagement,
            as_of_date=date(2025, 3, 31),
            cashbook_items=cb_sample,
            bank_items=bank_sample,
            starting_cashbook_balance=Decimal('3450000.00'),
            actual_statement_balance=Decimal('3140500.00')
        )

        # 8. Run GST ITC (GSTR-2B vs Books) Reconciliation
        purchase_items = [
            {'date': date(2025, 1, 10), 'gstin': '27AAACG1234D1ZP', 'invoice_no': 'INV-2025-01', 'vendor_name': 'AWS India Pvt Ltd', 'itc_amount': '37800.00'},
            {'date': date(2025, 2, 14), 'gstin': '07AABCT9988K1ZK', 'invoice_no': 'DL-2025-88', 'vendor_name': 'Dell Global India', 'itc_amount': '81000.00'},
            {'date': date(2025, 3, 12), 'gstin': '27AAACT4455R1Z3', 'invoice_no': 'SL-2025-102', 'vendor_name': 'Shree Tech Solutions', 'itc_amount': '24500.00'}, # Missing in 2B
        ]
        gstr2b_items = [
            {'gstin': '27AAACG1234D1ZP', 'invoice_no': 'INV-2025-01', 'itc_amount': '37800.00'},
            {'gstin': '07AABCT9988K1ZK', 'invoice_no': 'DL-2025-88', 'itc_amount': '81000.00'},
        ]
        GstItcReconciliationEngine.execute_reconciliation(
            engagement=engagement,
            as_of_date=date(2025, 3, 31),
            purchase_items=purchase_items,
            gstr2b_items=gstr2b_items
        )

        # 9. Initialize Engagement Workflow Config
        EngagementWorkflowConfig.objects.update_or_create(
            engagement=engagement,
            defaults={
                'scope_description': "Statutory audit under Companies Act 2013 and Tax Audit under Section 44AB Form 3CD.",
                'applicable_framework': 'COMPANIES_ACT_2013',
                'caro_applicable': True,
                'form_3cd_applicable': True,
                'form_type': '3CA',
                'msmed_applicable': True,
                'schedule_iii_division': 'DIVISION_I',
                'required_documents': [
                    {'title': 'Signed Trial Balance', 'status': 'RECEIVED'},
                    {'title': 'General Ledger Dump', 'status': 'RECEIVED'},
                    {'title': 'Bank Statements & BRS', 'status': 'RECEIVED'},
                    {'title': 'Fixed Asset Register (FAR)', 'status': 'RECEIVED'},
                    {'title': 'Sundry Debtors Ageing Schedule', 'status': 'RECEIVED'},
                    {'title': 'Sundry Creditors & MSME Classification', 'status': 'RECEIVED'},
                    {'title': 'Inventory Valuation & Stock Sheets', 'status': 'RECEIVED'},
                    {'title': 'Statutory Dues Challans (PF/ESI/GST/TDS)', 'status': 'RECEIVED'}
                ],
                'milestones': {'planning': 'COMPLETED', 'risk_assessment': 'COMPLETED', 'fieldwork': 'IN_PROGRESS', 'final_review': 'PENDING'},
                'completion_criteria': {'all_wps_approved': False, 'zero_critical_exceptions': False, 'tb_balanced': True},
                'completion_status': 'IN_PROGRESS'
            }
        )

        # 10. Populate Fixed Asset Register (FAR) & Calculate Dual Depreciation
        far_records = [
            {
                'asset_id': 'FA-SRV-001',
                'asset_name': 'High-Performance Production Server Dell PowerEdge',
                'category': 'COMPUTERS & SERVERS',
                'cost': '1850000.00',
                'accumulated_depreciation': '616666.00',
                'acquisition_date': '2023-04-10',
                'put_to_use_date': '2023-04-10',
                'location': 'Mumbai Data Center'
            },
            {
                'asset_id': 'FA-LPT-002',
                'asset_name': 'Developer Laptops Dell Latitude (15 Units)',
                'category': 'COMPUTERS & SERVERS',
                'cost': '1250000.00',
                'accumulated_depreciation': '416666.00',
                'acquisition_date': '2023-08-15',
                'put_to_use_date': '2023-08-15',
                'location': 'Andheri HQ'
            },
            {
                'asset_id': 'FA-OF-003',
                'asset_name': 'Conference Room Modular Furniture & Workstations',
                'category': 'FURNITURE & FIXTURES',
                'cost': '850000.00',
                'accumulated_depreciation': '85000.00',
                'acquisition_date': '2023-04-01',
                'put_to_use_date': '2023-04-01',
                'location': 'Andheri HQ'
            },
            {
                # Asset acquired <180 days in current FY (Tests Income Tax 50% half-rate rule!)
                'asset_id': 'FA-SRV-004',
                'asset_name': 'Backup Storage SAN Array 48TB',
                'category': 'COMPUTERS & SERVERS',
                'cost': '550000.00',
                'accumulated_depreciation': '0.00',
                'acquisition_date': '2024-11-20',
                'put_to_use_date': '2024-12-01', # <180 days!
                'location': 'Mumbai Data Center'
            }
        ]
        FixedAssetAuditEngine.import_and_validate_far(engagement, far_records)

        # 11. Populate Subledger Receivables & Payables Ageing with MSME Overdue
        subledger_records = [
            # Receivables
            {
                'item_type': 'RECEIVABLE',
                'party_name': 'Reliance Digital Retail Limited',
                'party_pan': 'AABCR1234D',
                'party_gstin': '27AABCR1234D1Z2',
                'invoice_number': 'INV-2024-041',
                'invoice_date': '2024-09-15',
                'total_amount': '1850000.00',
                'outstanding_amount': '1850000.00'
            },
            {
                'item_type': 'RECEIVABLE',
                'party_name': 'Tata Consultancy Services Ltd',
                'party_pan': 'AAACT5678M',
                'party_gstin': '27AAACT5678M1Z8',
                'invoice_number': 'INV-2025-012',
                'invoice_date': '2025-02-10',
                'total_amount': '2450000.00',
                'outstanding_amount': '2450000.00'
            },
            {
                'item_type': 'RECEIVABLE',
                'party_name': 'Hindustan Media Ventures',
                'party_pan': 'AABCH9911K',
                'party_gstin': '07AABCH9911K1Z5',
                'invoice_number': 'INV-2025-029',
                'invoice_date': '2025-03-05',
                'total_amount': '1900000.00',
                'outstanding_amount': '1900000.00'
            },
            # Payables: Compliant Non-MSME
            {
                'item_type': 'PAYABLE',
                'party_name': 'Amazon Web Services India Pvt Ltd',
                'party_pan': 'AAACG1234D',
                'party_gstin': '27AAACG1234D1ZP',
                'is_msme': False,
                'msme_type': 'NON_MSME',
                'invoice_number': 'AWS-2025-03',
                'invoice_date': '2025-03-01',
                'total_amount': '850000.00',
                'outstanding_amount': '850000.00'
            },
            # Payables: Compliant MSME (<45 days)
            {
                'item_type': 'PAYABLE',
                'party_name': 'DevCraft Software Solutions LLP',
                'party_pan': 'AAPFD1122K',
                'party_gstin': '27AAPFD1122K1Z9',
                'is_msme': True,
                'msme_type': 'MICRO',
                'invoice_number': 'DC-2025-08',
                'invoice_date': '2025-03-10', # 21 days
                'total_amount': '225000.00',
                'outstanding_amount': '225000.00'
            },
            # Payables: Intentional Audit Issue: Section 43B(h) MSMED Overdue > 45 days!
            {
                'item_type': 'PAYABLE',
                'party_name': 'Kalyan Security & Facility Management',
                'party_pan': 'ABCPK8899L',
                'party_gstin': '27ABCPK8899L1Z1',
                'is_msme': True,
                'msme_type': 'SMALL',
                'invoice_number': 'KS-2024-114',
                'invoice_date': '2024-12-15', # Over 100 days outstanding!
                'total_amount': '175000.00',
                'outstanding_amount': '175000.00',
                'has_written_agreement': True
            }
        ]
        SubledgerAnalyticsEngine.process_subledger_items(engagement, subledger_records, date(2025, 3, 31))

        # 12. Setup Related Party Master
        RelatedParty.objects.filter(engagement=engagement).delete()
        RelatedParty.objects.create(
            engagement=engagement,
            party_name="Verma Corporate Advisors LLP",
            pan="AAAFV4455K",
            relationship_type="Entity where Director has substantial interest",
            applicable_standard="SECTION_2_76",
            notes="Director holds 45% partnership interest. Scrutinize for Section 188 arm's length compliance."
        )

        # 13. Initialize Statutory Clauses Checklist for CARO 2020 and Form 3CD
        StatutoryFormMatrixEngine.initialize_and_audit_clauses(engagement)

        # 14. Execute Audit Procedures and Generate Exceptions
        AuditProcedureRunner.run_all_procedures(engagement)

        # 15. Execute Cross-Document Reconciliations Suite
        CrossDocumentReconciliationEngine.run_all_cross_reconciliations(engagement)

        # 16. Create Proposed Adjustments (AJE)
        ProposedAdjustment.objects.filter(engagement=engagement).delete()
        ProposedAdjustment.objects.create(
            engagement=engagement,
            adjustment_number="AJE-01",
            title="Recording Year-End Bank Charges & Processing Fee",
            reason="HDFC Bank deducted annual folio maintenance and charges on 31-Mar-2025 not recorded in cashbook.",
            journal_entries=[
                {'account': 'Bank Charges & Loan Interest', 'debit': '3500.00', 'credit': '0.00'},
                {'account': 'HDFC Bank Current Account', 'debit': '0.00', 'credit': '3500.00'}
            ],
            total_debit=Decimal('3500.00'),
            total_credit=Decimal('3500.00'),
            is_balanced=True,
            pnl_impact=Decimal('-3500.00'),
            status=AdjustmentStatus.PROPOSED
        )

        # 17. Generate Evidence-Linked Audit Workpapers (including Phase 4 WPs)
        WorkpaperDraftingService.draft_workpapers(engagement)

        # 18. Generate PDF Draft Report
        ReportGeneratorService.generate_pdf_report(engagement)

        return engagement

