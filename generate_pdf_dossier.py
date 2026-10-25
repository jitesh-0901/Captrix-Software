import os
import io
from decimal import Decimal
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, PageBreak, KeepTogether, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

class DossierNumberedCanvas(canvas.Canvas):
    """Adds running headers and 'Page X of Y' footers to ReportLab PDFs"""
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
        self.setFillColor(colors.HexColor('#64748b'))
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(36, 756, "CAPTRIX — PROJECT REVIEW & STATUTORY ASSURANCE DOSSIER")
            self.setFont("Helvetica", 8)
            self.drawRightString(576, 756, "PRODUCTION RELEASE 2.4.0")
            self.setStrokeColor(colors.HexColor('#cbd5e1'))
            self.setLineWidth(0.5)
            self.line(36, 750, 576, 750)

        # Footer (all pages)
        self.setStrokeColor(colors.HexColor('#cbd5e1'))
        self.setLineWidth(0.5)
        self.line(36, 42, 576, 42)
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(576, 30, page_str)
        self.setFont("Helvetica", 8)
        self.drawString(36, 30, "CONFIDENTIAL — STRICTLY FOR ACADEMIC & STATUTORY AUDIT REVIEW")
        self.restoreState()

def build_pdf_dossier():
    pdf_path = os.path.abspath(r"d:\Captrix Ai\Captrix_Project_Review_and_Submission_Dossier.pdf")
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=46,
        bottomMargin=46
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'MainTitle', parent=styles['Heading1'], fontSize=20, leading=24,
        textColor=colors.HexColor('#0F172A'), spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        'SubTitle', parent=styles['Heading2'], fontSize=11, leading=15,
        textColor=colors.HexColor('#1D4ED8'), spaceBefore=2, spaceAfter=8
    )
    h1_style = ParagraphStyle(
        'SecH1', parent=styles['Heading2'], fontSize=13, leading=17,
        textColor=colors.HexColor('#0F172A'), spaceBefore=12, spaceAfter=6,
        keepWithNext=True
    )
    h2_style = ParagraphStyle(
        'SecH2', parent=styles['Heading3'], fontSize=10.5, leading=14,
        textColor=colors.HexColor('#1E40AF'), spaceBefore=8, spaceAfter=4,
        keepWithNext=True
    )
    body_style = ParagraphStyle(
        'BodyDark', parent=styles['Normal'], fontSize=8.5, leading=12,
        textColor=colors.HexColor('#334155'), spaceAfter=4
    )
    bullet_style = ParagraphStyle(
        'BulletDark', parent=styles['Normal'], fontSize=8.5, leading=12,
        textColor=colors.HexColor('#334155'), leftIndent=12, spaceAfter=3
    )
    callout_style = ParagraphStyle(
        'CalloutText', parent=styles['Normal'], fontSize=8.5, leading=12,
        textColor=colors.HexColor('#1E293B')
    )
    formula_style = ParagraphStyle(
        'FormulaText', parent=styles['Normal'], fontSize=8, leading=11,
        textColor=colors.HexColor('#0F172A'), fontName='Courier'
    )

    elements = []

    # Title Banner
    elements.append(Paragraph("<b>CAPTRIX</b>", title_style))
    elements.append(Paragraph("<b>Autonomous Statutory Financial Audit & Assurance Platform</b>", subtitle_style))
    elements.append(Paragraph(
        "<b>Comprehensive Project Review, Architectural Specification & Submission Dossier</b><br/>"
        "<font size=7.5 color='#64748B'>Compliant with ICAI Standards on Auditing (SAs) • Companies Act, 2013 (Schedule III & CARO 2020) • Income Tax Act, 1961 (Form 3CD & Sec 43B(h)) • CGST Act, 2017</font>",
        body_style
    ))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#1D4ED8'), spaceAfter=8))

    # Callout: Executive Summary
    summary_html = (
        "<b>EXECUTIVE SUMMARY & CORE VISION:</b><br/>"
        "Captrix is an intelligent, autonomous statutory audit and financial assurance system designed specifically for Indian accounting environments. "
        "It eliminates weeks of tedious manual checking by taking client accounting documents (Trial Balance, General Ledger, Bank Statements, GSTR-2B, "
        "Fixed Asset Register, and Payables Subledgers), validating double-entry mathematical integrity to <b>INR 0.00 variance</b>, running deep fraud-risk tests (Benford's Law), "
        "executing 4-way reconciliations, computing dual-depreciation (Companies Act vs IT Act), screening Section 43B(h) MSME overdue payments, "
        "and compiling complete SA 230 compliant electronic audit workpapers with official CA seals and manual signature areas in <b>under 10 minutes</b>."
    )
    t_callout = Table([[Paragraph(summary_html, callout_style)]], colWidths=[540])
    t_callout.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#EFF6FF')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#3B82F6')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(t_callout)
    elements.append(Spacer(1, 8))

    # 1. Problem Statement
    elements.append(Paragraph("<b>1. Problem Statement & Why Captrix Was Built</b>", h1_style))
    elements.append(Paragraph(
        "Statutory financial audits in India are mandatory under Section 139 of the Companies Act, 2013 and Section 44AB of the Income Tax Act, 1961. "
        "However, traditional auditing across tens of thousands of CA firms suffers from critical bottlenecks:",
        body_style
    ))
    problems = [
        "<b>Massive Time Lag:</b> Auditing a mid-sized enterprise takes 2 to 4 weeks of manual spreadsheet cross-referencing and physical voucher checking.",
        "<b>Human Error & Fatigue:</b> Manual tick-and-bash spot sampling misses subtle ledger balancing errors, round-sum fraud entries, weekend transactions, and GST credit leakages.",
        "<b>Inflexibility:</b> Traditional audit software forces small local proprietorships (which only have a simple Trial Balance) through the same complex schedules required for large multinationals.",
        "<b>Fragmented Software Tools:</b> Audit teams juggle separate tools for accounting (Tally/Zoho), GST portal downloads, Excel sheets for BRS, and Word documents for reporting.",
        "<b>Strict Indian Regulatory Penalties:</b> Strict recent mandates such as Section 43B(h) MSME 45-day overdue disallowances and CARO 2020 21-clause reporting impose severe legal and tax liabilities if overlooked."
    ]
    for prob in problems:
        elements.append(Paragraph(f"• {prob}", bullet_style))
    elements.append(Spacer(1, 6))

    # 2. Adaptive Auditing
    elements.append(Paragraph("<b>2. Core Architectural Philosophy: Adaptive Auditing</b>", h1_style))
    elements.append(Paragraph(
        "A central innovation of Captrix is its <b>Adaptive Auditing Engine</b> (<i>'Upload enna iruko atha matum vechu audit panu'</i>). "
        "Local proprietary shops, doctors, and freelance businesses only possess a basic Trial Balance. Conversely, large corporate entities maintain complex Fixed Asset Registers, GSTR-2B files, and CARO 2020 obligations. "
        "Captrix dynamically adapts its entire interface, calculations, and final audit file to strictly reflect whatever files were uploaded:",
        body_style
    ))

    adapt_rows = [
        ["Client Entity Type", "Uploaded Files", "Active Verified Schedules", "Exempt / Hidden Schedules"],
        ["Small Proprietorship / Local Shop\n(Small Accounts)", "Trial Balance\n(CSV / Excel)", "• Schedule III Balance Sheet & P&L\n• Footing Check (Diff = INR 0.00)\n• 7 Key Financial Ratios\n• Statutory CA Opinion & Stamp", "• Bank Reconciliation (BRS) [Hidden]\n• GSTR-2B ITC Matching [Hidden]\n• Fixed Asset Register [Hidden]\n• CARO 2020 21-Clauses [Hidden]\n• MSME 43B(h) Aging [Hidden]"],
        ["Mid-Market Enterprise\n(Trading / Services)", "Trial Balance +\nGeneral Ledger +\nBank Statement", "• All Small Account Schedules\n• General Ledger Scrutiny (SA 240)\n• Benford's Law Fraud Test\n• 4-Way Automated BRS\n• Adjusting Journal Entries (AJE)", "• CARO 2020 (if Non-Corporate)\n• Fixed Asset Sch II (if no FAR)\n• GSTR-2B (if no GST file)"],
        ["Private / Public Limited Co.\n(Enterprise Corporate)", "Full Package:\nTB + GL + Bank +\nGST + FAR + Payables", "• All 14 Full Schedules (A to N)\n• GSTR-2B vs Purchase ITC (Sec 16)\n• Schedule II SLM vs Sec 32 WDV\n• MSMED Act 43B(h) 45-day Overdue\n• CARO 2020 21-Clause Verification", "None. 100% of statutory compliance schedules are active and verified."]
    ]
    t_adapt = Table(adapt_rows, colWidths=[110, 85, 175, 170])
    t_adapt.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(t_adapt)
    elements.append(Spacer(1, 8))

    # 3. 14-Stage Pipeline
    elements.append(Paragraph("<b>3. End-to-End Workflow: The 14-Stage Pipeline</b>", h1_style))
    pipeline_stages = [
        ("Stage 1: Multi-Format Ingestion & Hashing", "Accepts Excel, CSV, PDF (scanned/native), or multi-document ZIP. Immediately records SHA-256 hash for legal non-repudiation under SA 230."),
        ("Stage 2: Deterministic OCR & Tabular Extraction", "Uses pdfplumber, pypdfium2, and Tesseract OCR to parse structured rows with per-row extraction confidence scoring."),
        ("Stage 3: Column Normalization & Header Mapping", "Fuzzy-matches diverse client headers ('Cr Amt', 'Credit', 'Jama', 'Deposit') into double-entry standardized schema."),
        ("Stage 4: Schedule III Automated Classification", "Automatically maps raw ledgers to Schedule III Division I groups (Share Capital, PPE, Current Assets, etc.)."),
        ("Stage 5: Mathematical Footing & Zero-Variance Engine", "Calculates debit/credit footing, enforcing INR 0.00 difference between Total Assets and Total Equity & Liabilities."),
        ("Stage 6: Schedule III Financial Statements Compilation", "Generates real-time Balance Sheet, Profit & Loss, and 7 key audit ratios (Current Ratio, Quick Ratio, Debt-Equity, etc.)."),
        ("Stage 7: SA 240 Fraud Scrutiny & Benford's Law", "Tests voucher leading digits against logarithmic curves; flags Section 40A(3) cash entries (>INR 10,000) and weekend entries."),
        ("Stage 8: 4-Way Automated Bank Reconciliation (BRS)", "Cross-matches general ledger against bank statements across exact, date-tolerant (±3 days), and fuzzy description tiers."),
        ("Stage 9: GSTR-2B vs Purchase ITC Reconciliation", "Reconciles purchase invoices against GSTR-2B to enforce Section 16(2)(aa) CGST Act compliance, identifying ineligible credits."),
        ("Stage 10: Dual-Track Fixed Asset Depreciation Engine", "Simultaneously computes Schedule II SLM and Section 32 WDV depreciation, isolating timing differences for Deferred Tax."),
        ("Stage 11: Subledger Aging & MSME Section 43B(h)", "Screens payables against the MSMED Act 45-day window, totaling exact disallowance pools added back in Form 3CD Clause 22."),
        ("Stage 12: Statutory Clause Verification (CARO & 3CD)", "Evaluates 21 clauses of CARO 2020 and key Form 3CD clauses (Clause 21 personal expenses, Clause 26 statutory dues, Clause 34 TDS/TCS)."),
        ("Stage 13: SA 230 Electronic Workpaper Drafting", "Prepares formal audit working papers (WP-100 to WP-500) with Maker-Checker separation of duties enforcement."),
        ("Stage 14: Final Audit Dossier Compilation & Sign-off", "Compiles full pack, embeds official ICAI CA firm seal, provides designated physical ink signing zone, and generates PDF/Excel exports.")
    ]
    for s_name, s_det in pipeline_stages:
        elements.append(Paragraph(f"• <b>{s_name}:</b> {s_det}", bullet_style))
    elements.append(Spacer(1, 8))

    # 4. Algorithms & Formulas
    elements.append(Paragraph("<b>4. Mathematical Models & Algorithms Explained</b>", h1_style))
    
    # 4.1 Benford's Law
    elements.append(Paragraph("<b>4.1 SA 240 Fraud Detection: Benford's Law & Chi-Square Test</b>", h2_style))
    elements.append(Paragraph(
        "In unmanipulated accounting records, leading digits (1-9) follow Benford's logarithmic distribution: <b>P(d) = Log10(1 + 1/d)</b>. "
        "When management artificially splits transactions or fabricates journal entries, the observed distribution deviates sharply.",
        body_style
    ))
    elements.append(Paragraph(
        "Expected Frequencies: Digit 1 = 30.1% | Digit 2 = 17.6% | Digit 3 = 12.5% | Digit 4 = 9.7% | Digit 5 = 7.9% | Digit 6 = 6.7% | Digit 7 = 5.8% | Digit 8 = 5.1% | Digit 9 = 4.6%<br/>"
        "<b>Chi-Square Goodness-of-Fit Statistic:</b> χ² = Σ [ (Observed_d - Expected_d)² / Expected_d ]<br/>"
        "<i>Decision Rule: At df = 8 and 95% confidence level, critical threshold is <b>15.51</b>. If χ² > 15.51, Captrix flags high fraud risk.</i>",
        formula_style
    ))
    elements.append(Spacer(1, 4))

    # 4.2 Zero-Variance Balancing
    elements.append(Paragraph("<b>4.2 Zero-Variance Schedule III Equilibrium Engine</b>", h2_style))
    elements.append(Paragraph(
        "Captrix enforces deterministic double-entry balancing without dumping discrepancies into a 'Suspense Account':<br/>"
        "1. <b>Profit After Tax (PAT)</b> = Revenue from Operations + Other Income - Total Expenses - Tax Provision<br/>"
        "2. <b>Shareholders' Funds</b> = Share Capital + Reserves & Surplus + PAT - Proprietor Drawings<br/>"
        "3. <b>Total Equity & Liabilities</b> = Shareholders' Funds + Non-Current Liabilities + Current Liabilities<br/>"
        "4. <b>Total Assets</b> = Non-Current Assets (Net PPE + Intangibles + Investments) + Current Assets (Stock + Debtors + Bank + Advances)<br/>"
        "<b>Mathematical Invariant:</b> |Total Assets - Total Equity & Liabilities| ≡ <b>INR 0.00</b>",
        formula_style
    ))
    elements.append(Spacer(1, 4))

    # 4.3 4-Way BRS
    elements.append(Paragraph("<b>4.3 4-Way Automated Bank Reconciliation Engine (BRS)</b>", h2_style))
    elements.append(Paragraph(
        "• <b>Tier 1 (Exact):</b> Matches Amount + Cheque Number / UTR Reference.<br/>"
        "• <b>Tier 2 (Date-Tolerant):</b> Matches exact Amount within ±3 business days (clearing window).<br/>"
        "• <b>Tier 3 (Fuzzy Narration):</b> Token Jaccard similarity ≥ 0.85 on party name / transaction description.<br/>"
        "• <b>Tier 4 (Timing Isolation):</b> Unpresented cheques and deposits in transit isolated automatically to bridge Book and Bank balances.",
        body_style
    ))
    elements.append(Spacer(1, 4))

    # 4.4 Dual Depreciation
    elements.append(Paragraph("<b>4.4 Dual-Track Fixed Asset Depreciation Engine</b>", h2_style))
    elements.append(Paragraph(
        "1. <b>Companies Act 2013 (Schedule II SLM):</b> Annual Depn = (Original Cost - 5% Residual) / Useful Life in Years<br/>"
        "2. <b>Income Tax Act 1961 (Section 32 WDV):</b> Tax Depn = (Opening WDV + Additions_>180d + 50% Additions_<180d - Deductions) × Block Rate<br/>"
        "3. <b>Deferred Tax Impact:</b> Timing Difference = |Book Depn - Tax Depn|. Deferred Tax Provision = Timing Difference × 25.17%.",
        formula_style
    ))
    elements.append(Spacer(1, 4))

    # 4.5 MSME 43B(h)
    elements.append(Paragraph("<b>4.5 MSMED Act 2006 & Section 43B(h) Disallowance Engine</b>", h2_style))
    elements.append(Paragraph(
        "Under Section 43B(h) (Finance Act 2023), any payment owed to a registered Micro or Small enterprise beyond <b>45 days</b> (with agreement) or <b>15 days</b> (without agreement) is disallowed as a tax deduction in the year of accrual.<br/>"
        "Captrix screens every trade payable against the Udyam registry, calculates elapsed days as of 31st March, and automatically computes the exact disallowance pool for add-back in Form 3CD Clause 22.",
        body_style
    ))
    elements.append(Spacer(1, 6))

    # 5. Input Guide
    elements.append(Paragraph("<b>5. Input Guide & Supported File Types</b>", h1_style))
    in_rows = [
        ["Document Type", "Formats", "Mandatory Headers", "Purpose in Captrix"],
        ["Trial Balance (TB)", ".xlsx, .csv", "Account Name, Debit, Credit", "Footing verification, Schedule III Balance Sheet & P&L compilation."],
        ["General Ledger / Daybook", ".xlsx, .csv, .pdf", "Voucher No, Date, Account, Debit, Credit, Narration", "SA 240 fraud scrutiny, Benford's Law, Sec 40A(3) cash limits (>10k)."],
        ["Bank Statement", ".xlsx, .csv, .pdf", "Date, Description, Ref No, Withdrawal, Deposit, Balance", "Reconciled 4-ways against General Ledger bank accounts for BRS."],
        ["GSTR-2B / GSTR-2A", ".xlsx, .csv, .json", "GSTIN, Invoice No, Date, Taxable Value, IGST, CGST, SGST", "Cross-checked with Purchase Register for Section 16(2)(aa) ITC matching."],
        ["Fixed Asset Register (FAR)", ".xlsx, .csv", "Asset ID, Purchase Date, Cost, Useful Life, Dep. Rate", "Calculates Schedule II SLM vs Section 32 WDV depreciation blocks."],
        ["Payables Subledger", ".xlsx, .csv", "Supplier Name, Invoice No, Date, MSME Status, Balance", "Aging schedules & Section 43B(h) 45-day overdue tax disallowance pool."]
    ]
    t_in = Table(in_rows, colWidths=[100, 65, 175, 200])
    t_in.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(t_in)
    elements.append(Spacer(1, 8))

    # 6. Division of Labor
    elements.append(Paragraph("<b>6. Division of Responsibility: Software vs Human Auditor</b>", h1_style))
    div_rows = [
        ["Audit Dimension", "What Captrix Automates (90% Labor)", "What Human Auditor Must Do (10% Judgment)"],
        ["Trial Balance & Schedule III", "• Maps 100% of accounts to Schedule III\n• Balances Balance Sheet & P&L to INR 0.00 diff\n• Computes 7 vital audit ratios", "• Evaluates management's going concern assumption\n• Reviews notes on accounting policies\n• Approves grouping of unusual ledgers"],
        ["Bank Balances & BRS", "• 4-way matches thousands of transactions\n• Isolates unpresented cheques & timing diffs\n• Reconciles book balance to bank statement", "• Obtains external bank confirmation letters (SA 505)\n• Examines stale cheques (>3 months)\n• Inquires on unauthorized bank borrowings"],
        ["Fraud Scrutiny (SA 240)", "• Analyzes 100% of vouchers with Benford's Law\n• Flags cash payments >INR 10,000 (Sec 40A(3))\n• Detects weekend postings & missing gaps", "• Inquires with management on flagged vouchers\n• Corroborates suspicious narrations with physical bills\n• Assesses risk of management override"],
        ["Fixed Assets & MSME", "• Dual-track depreciation (Sch II vs Sec 32)\n• Identifies Deferred Tax timing variances\n• Totals Section 43B(h) 45-day overdue pool", "• Observes physical stock count & asset tagging\n• Inspects title deeds of immovable properties (CARO)\n• Obtains written management representations"],
        ["Statutory Certification", "• Compiles SA 230 electronic working papers\n• Embeds official ICAI firm seal\n• Provides designated physical ink signing space", "• Selects Audit Opinion (Clean / Qualified / Adverse)\n• Generates 18-digit UDIN on official ICAI portal\n• Signs manually with ink in the signature box"]
    ]
    t_div = Table(div_rows, colWidths=[120, 210, 210])
    t_div.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(t_div)
    elements.append(Spacer(1, 8))

    # 7. Comparison Matrix
    elements.append(Paragraph("<b>7. Competitive Advantage & Comparison Matrix</b>", h1_style))
    comp_rows = [
        ["Audit Capability", "Manual (Excel)", "Tally / Zoho Books", "SAP / Global ERP", "CAPTRIX PLATFORM"],
        ["Audit Completion Time", "2 to 4 Weeks", "Several Days", "1 to 2 Weeks", "Under 10 Minutes (Autonomous)"],
        ["Adaptive Scope Filtering", "Manual & messy", "Rigid fixed templates", "Expensive custom config", "Autonomous (Auto-hides unneeded schedules)"],
        ["Mathematical Balancing", "Formula mistakes", "Often leaves Suspense", "Strict but complex", "Strict INR 0.00 Variance Guaranteed"],
        ["Fraud Testing (SA 240)", "5% spot check", "None", "Expensive GRC addon", "100% Ledger Benford's Law Analysis"],
        ["Automated BRS", "Manual tick-marking", "Basic bank feeds", "Complex rule engine", "4-Way Matching (Exact, Date ±3d, Fuzzy)"],
        ["Section 43B(h) MSME", "Manual aging tally", "Basic aging report", "Custom ABAP code", "Automated 45-day threshold disallowance pool"],
        ["Dual Depreciation", "Separate sheets", "Single method only", "Complex asset module", "Automated Schedule II vs Sec 32 blocks"],
        ["Statutory Seal & Signing", "Word copy-paste", "Basic invoice print", "Third-party add-on", "Integrated Official CA Seal + Ink Signing Box"],
        ["Cost & Deployment", "Labor intensive", "Accounting-only", "INR 50L - INR 5Cr", "Affordable, Web-based, Instant Deployment"]
    ]
    t_comp = Table(comp_rows, colWidths=[105, 95, 105, 105, 130])
    t_comp.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(t_comp)
    elements.append(Spacer(1, 8))

    # 8. Signature & Official Stamp Display in PDF
    stamp_path = os.path.join(os.path.dirname(__file__), 'frontend', 'src', 'assets', 'Stamp.png')
    if not os.path.exists(stamp_path):
        stamp_path = os.path.join(os.path.dirname(__file__), 'backend', 'apps', 'reporting', 'assets', 'Stamp.png')

    stamp_img = None
    if os.path.exists(stamp_path):
        try:
            stamp_img = Image(stamp_path, width=90, height=90)
        except Exception:
            stamp_img = None

    sig_box_html = (
        "<b>STATUTORY AUDITOR SIGN-OFF & CERTIFICATION</b><br/>"
        "<b>Firm Name:</b> M/s Sharma & Associates, Chartered Accountants (FRN: 014285N)<br/>"
        "<b>Manual Signature:</b> ____________________________________<br/>"
        "<font size=7 color='#64748B'><i>(Engagement Partner physically signs here with pen)</i></font><br/><br/>"
        "<b>CA. Rajesh Sharma</b>, FCA (ICAI Membership No: 512345)<br/>"
        "<b>Official ICAI UDIN:</b> 25512345AAAAAA9876 | <b>Date:</b> 31-Jul-2025 | <b>Place:</b> Chennai, India"
    )
    t_sig = Table([[Paragraph(sig_box_html, body_style), stamp_img if stamp_img else Paragraph("<b>[OFFICIAL CA SEAL]</b>", body_style)]], colWidths=[400, 140])
    t_sig.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#0F172A')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))

    elements.append(KeepTogether([
        Paragraph("<b>8. Statutory Auditor Official Sign-off & Physical Signature Block</b>", h1_style),
        Paragraph("Pursuant to Section 143 of the Companies Act, 2013 and ICAI Standards on Auditing, Captrix provides a dedicated physical signing space and integrates the official firm seal:", body_style),
        Spacer(1, 4),
        t_sig
    ]))

    doc.build(elements, canvasmaker=DossierNumberedCanvas)
    print(f"PDF Dossier successfully generated at: {pdf_path}")

if __name__ == '__main__':
    build_pdf_dossier()
