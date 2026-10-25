import os
from decimal import Decimal
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

def create_trial_balance_pdf(pdf_path: str):
    os.makedirs(os.path.dirname(os.path.abspath(pdf_path)), exist_ok=True)
    doc = SimpleDocTemplate(pdf_path, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph("<b>APEX INFOTECH PRIVATE LIMITED</b>", styles['Heading1']))
    elements.append(Paragraph("Trial Balance as of 31-Mar-2025", styles['Normal']))
    elements.append(Spacer(1, 15))

    # 13 accounts + 1 Total row = 14 rows total (excluding header)
    data = [
        ["Account Code", "Particulars", "Debit (INR)", "Credit (INR)"],
        ["1001", "Equity Share Capital", "0.00", "50,00,000.00"],
        ["1002", "Reserves & Surplus", "0.00", "15,50,000.00"],
        ["2001", "Term Loan Facility", "0.00", "20,00,000.00"],
        ["2101", "Trade Payables - Creditors", "0.00", "22,50,000.00"],
        ["2102", "Statutory Dues Payable", "0.00", "4,50,000.00"],
        ["3001", "Revenue from Operations", "0.00", "1,20,00,000.00"],
        ["1101", "Plant & Machinery", "45,00,000.00", "0.00"],
        ["1102", "Computers & IT Hardware", "12,00,000.00", "0.00"],
        ["1201", "Inventories Stock", "28,50,000.00", "0.00"],
        ["1202", "Trade Receivables - Debtors", "32,00,000.00", "0.00"],
        ["1203", "HDFC Bank Operating Account", "18,00,000.00", "0.00"],
        ["4001", "Raw Material Purchases", "55,00,000.00", "0.00"],
        ["4002", "Salaries & Staff Costs", "42,00,000.00", "0.00"],
        ["TOTAL", "Total Debits and Credits", "2,32,50,000.00", "2,32,50,000.00"]
    ]

    t = Table(data, colWidths=[90, 240, 105, 105])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t)
    doc.build(elements)


def create_bank_statement_pdf(pdf_path: str):
    os.makedirs(os.path.dirname(os.path.abspath(pdf_path)), exist_ok=True)
    doc = SimpleDocTemplate(pdf_path, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    styles = getSampleStyleSheet()

    # Page 1
    elements.append(Paragraph("<b>HDFC BANK LIMITED — STATEMENT OF ACCOUNT</b>", styles['Heading1']))
    elements.append(Paragraph("Account No: 50200012345678 | IFSC: HDFC0001234", styles['Normal']))
    elements.append(Spacer(1, 10))

    headers = ["Txn Date", "Value Date", "Description", "Ref No", "Withdrawal", "Deposit", "Balance"]
    page1_rows = [
        headers,
        ["01/04/2024", "01/04/2024", "OPENING BALANCE", "-", "0.00", "0.00", "15,00,000.00"],
        ["05/04/2024", "05/04/2024", "NEFT INW-KINETIC TECH-PAYMENT", "HDFC00129", "0.00", "5,00,000.00", "20,00,000.00"],
        ["12/04/2024", "12/04/2024", "CHQ CLG-VENDOR SUPPLIES", "CHQ-89012", "2,50,000.00", "0.00", "17,50,000.00"],
        ["20/04/2024", "20/04/2024", "SALARY DISBURSEMENT APRIL", "NEFT-0044", "4,20,000.00", "0.00", "13,30,000.00"],
        ["CARRIED FORWARD", "-", "Carried forward to next page", "-", "0.00", "0.00", "13,30,000.00"]
    ]
    t1 = Table(page1_rows, colWidths=[65, 65, 170, 70, 60, 60, 50])
    t1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
    ]))
    elements.append(t1)
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Page 1 of 2 — Computer generated statement", styles['Normal']))
    elements.append(PageBreak())

    # Page 2
    elements.append(Paragraph("<b>HDFC BANK LIMITED — STATEMENT OF ACCOUNT (Contd.)</b>", styles['Heading1']))
    elements.append(Spacer(1, 10))
    page2_rows = [
        headers,
        ["BROUGHT FORWARD", "-", "Brought forward from Page 1", "-", "0.00", "0.00", "13,30,000.00"],
        ["02/05/2024", "02/05/2024", "RTGS INW-CLIENT ENTERPRISES", "RTGS-8812", "0.00", "8,00,000.00", "21,30,000.00"],
        ["15/05/2024", "15/05/2024", "GST PAYMENT TAX ONLINE", "GST-0921", "3,30,000.00", "0.00", "18,00,000.00"],
        ["31/05/2024", "31/05/2024", "INTEREST CREDITED Q1", "INT-CR", "0.00", "25,000.00", "18,25,000.00"],
        ["TOTAL TRANSACTIONS", "-", "Total debits and credits", "-", "10,00,000.00", "13,25,000.00", "18,25,000.00"]
    ]
    t2 = Table(page2_rows, colWidths=[65, 65, 170, 70, 60, 60, 50])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
    ]))
    elements.append(t2)
    elements.append(Spacer(1, 15))
    elements.append(Paragraph("Page 2 of 2 — This is a computer generated advice and requires no signature. Subject to Mumbai jurisdiction.", styles['Normal']))
    doc.build(elements)


def create_borderless_bank_statement_pdf(pdf_path: str):
    os.makedirs(os.path.dirname(os.path.abspath(pdf_path)), exist_ok=True)
    doc = SimpleDocTemplate(pdf_path, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph("<b>STATE BANK OF INDIA — CURRENT ACCOUNT STATEMENT</b>", styles['Heading1']))
    elements.append(Paragraph("Account No: 40918234567 | IFSC: SBIN0001234", styles['Normal']))
    elements.append(Spacer(1, 15))

    headers = ["Txn Date", "Value Date", "Description", "Ref No", "Withdrawal", "Deposit", "Balance"]
    rows = [
        headers,
        ["01/04/2024", "01/04/2024", "INVOICE NO 1045 PAYMENT FROM ALPHA CORP", "SBI-1001", "0.00", "6,00,000.00", "6,00,000.00"],
        ["05/04/2024", "05/04/2024", "OFFICE RENT EXPENSE DISBURSAL", "SBI-1002", "1,50,000.00", "0.00", "4,50,000.00"],
        ["12/04/2024", "12/04/2024", "ELECTRICITY BOARD UTILITY CHARGES", "SBI-1003", "45,000.00", "0.00", "4,05,000.00"],
        ["18/04/2024", "18/04/2024", "VENDOR COMPONENT PROCUREMENT", "SBI-1004", "1,20,000.00", "0.00", "2,85,000.00"],
        ["25/04/2024", "25/04/2024", "CUSTOMER ADVANCE REMITTANCE", "SBI-1005", "0.00", "3,50,000.00", "6,35,000.00"],
        ["30/04/2024", "30/04/2024", "BANK CHARGES AND ANNUAL AMC", "SBI-1006", "5,000.00", "0.00", "6,30,000.00"],
    ]
    t = Table(rows, colWidths=[65, 65, 170, 70, 60, 60, 50])
    # Borderless table style
    t.setStyle(TableStyle([
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(t)
    doc.build(elements)
