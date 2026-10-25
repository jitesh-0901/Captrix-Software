import os
import sys
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header (pages after page 1)
        if self._pageNumber > 1:
            self.drawString(40, 800, "CAPTRIX — AUDITOR USER MANUAL & WORKFLOW GUIDE")
            self.drawRightString(555, 800, "CONFIDENTIAL & STATUTORY AUDIT READY")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(40, 792, 555, 792)

        # Footer (all pages)
        self.setFont("Helvetica", 8)
        self.drawString(40, 30, "Captrix Autonomous Statutory Audit & Assurance Platform")
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(555, 30, page_text)
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(40, 42, 555, 42)
        self.restoreState()


def build_pdf(filename="Captrix_Auditor_User_Manual_and_Workflow_Guide.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=55,
        bottomMargin=55
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#475569'),
        spaceAfter=15
    )

    h1_style = ParagraphStyle(
        'H1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=colors.HexColor('#1E3A8A'),
        spaceBefore=14,
        spaceAfter=6
    )

    h2_style = ParagraphStyle(
        'H2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=8,
        spaceAfter=4
    )

    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#334155'),
        spaceAfter=6
    )

    bullet_style = ParagraphStyle(
        'Bullet',
        parent=body_style,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=3
    )

    callout_style = ParagraphStyle(
        'Callout',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#1E40AF'),
        backColor=colors.HexColor('#EFF6FF'),
        borderColor=colors.HexColor('#BFDBFE'),
        borderWidth=1,
        borderPadding=8,
        spaceBefore=6,
        spaceAfter=8,
        borderRadius=4
    )

    table_header_style = ParagraphStyle(
        'TH',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white
    )

    table_cell_style = ParagraphStyle(
        'TD',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#1E293B')
    )

    table_cell_bold = ParagraphStyle(
        'TDBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#0F172A')
    )

    story = []

    # Title Banner
    story.append(Paragraph("CAPTRIX AUDIT WORKFLOW MANUAL", title_style))
    story.append(Paragraph("A Complete, Simple English Step-by-Step Guide for Statutory Auditors, Chartered Accountants, and Audit Teams", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563EB"), spaceAfter=14))

    # Section 1: Introduction
    story.append(Paragraph("1. What is Captrix & Who is it for?", h1_style))
    story.append(Paragraph(
        "<b>Captrix</b> is an autonomous statutory audit platform designed specifically for Indian Chartered Accountants (CAs). "
        "It ingests your client's year-end accounting records, reconciles transactions against bank and tax portal records, executes statutory audit procedures, and drafts professional audit reports complying with the Companies Act 2013, CARO 2020, and the Income Tax Act 1961.",
        body_style
    ))
    story.append(Paragraph("<b>Primary Users:</b> Statutory Auditors, Engagement Partners, Audit Managers, Articled Assistants, and Corporate Tax Teams.", body_style))

    # Section 2: The Audit Pack File
    story.append(Spacer(1, 4))
    story.append(Paragraph("2. What File Should You Upload? (The Single Audit Pack)", h1_style))
    story.append(Paragraph(
        "You do not need to upload multiple files one by one. You can upload <b>one single Excel file (.xlsx)</b> or a <b>.zip folder</b> named <code>Client_FY2024_25_Audit_Pack.xlsx</code> containing 6 sheets:",
        body_style
    ))

    # Table of 6 sheets
    table_data = [
        [Paragraph("Sheet Name", table_header_style), Paragraph("Contents", table_header_style), Paragraph("Why Captrix Needs It", table_header_style)],
        [
            Paragraph("<b>Sheet 1: Trial_Balance</b>", table_cell_bold),
            Paragraph("Account Code, Name, Debit, Credit", table_cell_style),
            Paragraph("Verifies mathematical equality (Dr = Cr) and builds Schedule III Balance Sheet / P&L.", table_cell_style)
        ],
        [
            Paragraph("<b>Sheet 2: General_Ledger</b>", table_cell_bold),
            Paragraph("Date, Voucher No, Account, Dr, Cr, Narration", table_cell_style),
            Paragraph("Performs daybook scrutiny, unusual journal detection, and forensic audit checks.", table_cell_style)
        ],
        [
            Paragraph("<b>Sheet 3: Bank_Statement</b>", table_cell_bold),
            Paragraph("Txn Date, Narration, Chq No, Dr, Cr, Balance", table_cell_style),
            Paragraph("Executes automated Bank Reconciliation (BRS) against bank ledger accounts.", table_cell_style)
        ],
        [
            Paragraph("<b>Sheet 4: Fixed_Asset_Register</b>", table_cell_bold),
            Paragraph("Asset ID, Category, Cost, Put to Use Date", table_cell_style),
            Paragraph("Recalculates Companies Act Schedule II depreciation and flags unrecorded variances.", table_cell_style)
        ],
        [
            Paragraph("<b>Sheet 5: Subledger_Aging</b>", table_cell_bold),
            Paragraph("Party, PAN, GSTIN, MSME Status, Due Date", table_cell_style),
            Paragraph("Calculates Section 43B(h) statutory disallowances for MSME overdue payments (>45 days).", table_cell_style)
        ],
        [
            Paragraph("<b>Sheet 6: GSTR_2B_Purchase</b>", table_cell_bold),
            Paragraph("Supplier GSTIN, Invoice No, Taxable Value, Tax", table_cell_style),
            Paragraph("Reconciles Input Tax Credit (ITC) between GST Portal GSTR-2B and Purchase Ledger.", table_cell_style)
        ]
    ]

    t = Table(table_data, colWidths=[130, 150, 235])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#F8FAFC'), colors.white]),
    ]))
    story.append(t)

    # Section 3: Step-by-Step Navigation
    story.append(Spacer(1, 8))
    story.append(Paragraph("3. Complete Step-by-Step Workflow", h1_style))

    story.append(Paragraph("Step 1: Uploading Documents (Page: <code>/upload</code>)", h2_style))
    story.append(Paragraph("&bull; Open the <b>Upload Documents</b> page from the navigation bar.", bullet_style))
    story.append(Paragraph("&bull; Drag and drop your <code>Client_FY2024_25_Audit_Pack.xlsx</code> file into the dropzone.", bullet_style))
    story.append(Paragraph("&bull; Review the detected sheet matrix (green checks will appear for all 6 categories).", bullet_style))
    story.append(Paragraph("&bull; Click the blue <b>'Process Audit Pack'</b> button to start.", bullet_style))

    story.append(Spacer(1, 4))
    story.append(Paragraph("Step 2: Automated Pipeline Monitoring (Page: <code>/processing</code>)", h2_style))
    story.append(Paragraph("&bull; Captrix automatically advances through 13 audit stages: Extraction &rarr; Normalization &rarr; BRS &rarr; GST Reconciliation &rarr; Statutory Procedures.", bullet_style))
    story.append(Paragraph("&bull; Each completed stage turns green with a checkmark (<code>✓ Completed</code>).", bullet_style))

    story.append(Spacer(1, 4))
    story.append(Paragraph("Step 3: Reviewing & Resolving Findings (Page: <code>/exceptions</code>)", h2_style))
    story.append(Paragraph("&bull; If any discrepancies exist in the books, Captrix generates an <b>Audit Exception Card</b>.", bullet_style))
    story.append(Paragraph(
        "<b>Example (Depreciation Variance):</b> Captrix recalculates Schedule II depreciation at <b>₹11,39,999.40</b>, but finds <b>₹0.00</b> recorded in the client's ledger.<br/>"
        "&bull; <b>Inspect Evidence:</b> Click this button to view the asset list, useful lives, and calculation sheets.<br/>"
        "&bull; <b>Update Resolution:</b> Click this button and select <i>'Adjusting Journal Entry (AJE) Recommended'</i>. Add a note: <code>'Dr. Depreciation / Cr. Accumulated Depreciation ₹11,39,999.40'</code>. Click Save to clear the finding.",
        callout_style
    ))

    story.append(Spacer(1, 4))
    story.append(Paragraph("Step 4: Statutory Assurance in the Auditor Suite (Page: <code>/auditor-suite</code>)", h2_style))
    story.append(Paragraph("&bull; <b>CARO 2020 Tab:</b> Shows all 21 statutory clauses (PPE, Inventory, Loans, Statutory Dues, Fraud). <b>Touch or click any card</b> to open the complete ICAI Sub-Checklist, Audit Procedures, and Draft Audit Report paragraph.", bullet_style))
    story.append(Paragraph("&bull; <b>Tax Audit Form 3CD Tab:</b> Click any clause row (e.g., Clause 22 MSME, Clause 34 TDS, Clause 44 GST) to review statutory working papers and update partner observations.", bullet_style))
    story.append(Paragraph("&bull; <b>MSMED Section 43B(h) Tab:</b> Shows the overdue payables pool (>45 days) subject to statutory disallowance under Finance Act 2023.", bullet_style))
    story.append(Paragraph("&bull; <b>Completion Controls:</b> Verifies the 9-Point Mandatory Pre-Sign-off checklist before the audit can be locked.", bullet_style))

    story.append(Spacer(1, 4))
    story.append(Paragraph("Step 5: Final Partner Sign-off & Reports (Page: <code>/reports</code>)", h2_style))
    story.append(Paragraph("&bull; When all 9 completion checks pass, the Engagement Partner clicks <b>'Finalize Engagement'</b>.", bullet_style))
    story.append(Paragraph("&bull; Navigate to <b>Reports</b> to download the complete audit-ready deliverables: Independent Auditor's Report, Form 3CD, and Schedule III Financials.", bullet_style))

    # Summary table
    story.append(Spacer(1, 8))
    story.append(Paragraph("4. Quick Reference Matrix: Where to Go & What to Do", h1_style))
    summary_data = [
        [Paragraph("Page Name", table_header_style), Paragraph("URL", table_header_style), Paragraph("Your Action As Auditor", table_header_style)],
        [Paragraph("<b>Upload</b>", table_cell_bold), Paragraph("<code>/upload</code>", table_cell_style), Paragraph("Drag & drop the 6-sheet Excel audit pack; click Process.", table_cell_style)],
        [Paragraph("<b>Processing</b>", table_cell_bold), Paragraph("<code>/processing</code>", table_cell_style), Paragraph("Watch the 13 automated audit stages complete in real time.", table_cell_style)],
        [Paragraph("<b>Exceptions</b>", table_cell_bold), Paragraph("<code>/exceptions</code>", table_cell_style), Paragraph("Inspect evidence and resolve differences (e.g. Depreciation Variance).", table_cell_style)],
        [Paragraph("<b>Auditor Suite</b>", table_cell_bold), Paragraph("<code>/auditor-suite</code>", table_cell_style), Paragraph("Touch cards to open CARO 2020 & 3CD details; review Sec 43B(h) pool.", table_cell_style)],
        [Paragraph("<b>Reports</b>", table_cell_bold), Paragraph("<code>/reports</code>", table_cell_style), Paragraph("Perform partner sign-off and download final PDF/Excel audit reports.", table_cell_style)],
    ]
    t2 = Table(summary_data, colWidths=[110, 110, 295])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#F8FAFC'), colors.white]),
    ]))
    story.append(t2)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated PDF: {filename}")


if __name__ == "__main__":
    out_file = os.path.join(os.getcwd(), "Captrix_Auditor_User_Manual_and_Workflow_Guide.pdf")
    build_pdf(out_file)
