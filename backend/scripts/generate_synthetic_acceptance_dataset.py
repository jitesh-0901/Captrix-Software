"""
Captrix AI — Independent Synthetic Acceptance Test Dataset Generator
Entity: Vanguard Industrial Automations Private Limited (CIN: U29100MH2020PTC345678, PAN: AABCV9876K, GSTIN: 27AABCV9876K1Z8)
Period: FY 2024-25 (01-Apr-2024 to 31-Mar-2025)

Generates CSV files with mathematically verified ground-truth values.
"""

import os
import csv
import json
from decimal import Decimal

OUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'synthetic_company')
os.makedirs(OUT_DIR, exist_ok=True)

# -------------------------------------------------------------
# 1. Balanced Trial Balance
# -------------------------------------------------------------
tb_balanced_rows = [
    ["Account Code", "Particulars", "Classification", "Debit (INR)", "Credit (INR)"],
    ["1001", "Equity Share Capital", "EQUITY", "0.00", "50,00,000.00"],
    ["1002", "Retained Earnings / General Reserves", "EQUITY", "0.00", "15,50,000.00"],
    ["2001", "HDFC Bank Long Term Project Loan", "NON_CURRENT_LIABILITY", "0.00", "20,00,000.00"],
    ["2101", "Trade Payables - Sundry Creditors", "CURRENT_LIABILITY", "0.00", "22,50,000.00"],
    ["2102", "Statutory Dues Payable (GST & TDS)", "CURRENT_LIABILITY", "0.00", "4,50,000.00"],
    ["2103", "State Bank Working Capital Overdraft", "CURRENT_LIABILITY", "0.00", "3,00,000.00"],
    ["3001", "Revenue from Automation Systems & Services", "REVENUE", "0.00", "1,20,00,000.00"],
    ["3002", "Other Operating Income", "REVENUE", "0.00", "2,50,000.00"],
    ["1104", "Accumulated Depreciation - Plant & Equip", "NON_CURRENT_ASSET", "0.00", "12,00,000.00"],
    ["1101", "Plant & Industrial Machinery", "NON_CURRENT_ASSET", "45,00,000.00", "0.00"],
    ["1102", "Computers & Server Hardware", "NON_CURRENT_ASSET", "12,00,000.00", "0.00"],
    ["1103", "Office Equipment & Fixtures", "NON_CURRENT_ASSET", "8,00,000.00", "0.00"],
    ["1201", "Inventories - Automation Assemblies", "CURRENT_ASSET", "28,50,000.00", "0.00"],
    ["1202", "Trade Receivables - Sundry Debtors", "CURRENT_ASSET", "32,00,000.00", "0.00"],
    ["1203", "SBI Current Account No 40918234", "CURRENT_ASSET", "18,00,000.00", "0.00"],
    ["1204", "GST Input Tax Credit & Advance Tax", "CURRENT_ASSET", "6,00,000.00", "0.00"],
    ["4001", "Direct Purchases - Microcontrollers & Drives", "EXPENSE", "55,00,000.00", "0.00"],
    ["4002", "Salaries, Wages & Employee Benefits", "EXPENSE", "21,50,000.00", "0.00"],
    ["4003", "Depreciation Expense (Schedule II)", "EXPENSE", "8,45,000.00", "0.00"],
    ["4004", "Power, Fuel & Operating Overheads", "EXPENSE", "15,55,000.00", "0.00"],
]

tb_path = os.path.join(OUT_DIR, 'trial_balance_fy24_25.csv')
with open(tb_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerows(tb_balanced_rows)

# -------------------------------------------------------------
# 2. Unbalanced Trial Balance (Intentional +25,000 INR variance)
# -------------------------------------------------------------
tb_unbalanced_rows = [row[:] for row in tb_balanced_rows]
# Modify SBI Current Account from 18,00,000.00 to 18,25,000.00
for r in tb_unbalanced_rows:
    if r[0] == "1203":
        r[3] = "18,25,000.00"

tb_unbal_path = os.path.join(OUT_DIR, 'trial_balance_unbalanced.csv')
with open(tb_unbal_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerows(tb_unbalanced_rows)

# -------------------------------------------------------------
# 3. Bank Statement FY 24-25 (BRS Testing)
# -------------------------------------------------------------
bank_rows = [
    ["Txn Date", "Value Date", "Description", "Chq No", "Withdrawal (Dr)", "Deposit (Cr)", "Balance"],
    ["2024-04-05", "2024-04-05", "NEFT/CLIENT/ALPHA INFOTECH/INV101", "", "0.00", "12,50,000.00", "12,50,000.00"],
    ["2024-05-12", "2024-05-12", "RTGS/VENDOR/SIEMENS DRIVES/CHQ4401", "4401", "8,20,000.00", "0.00", "4,30,000.00"],
    ["2024-06-20", "2024-06-20", "NEFT/CLIENT/TATA MOTORS/INV104", "", "0.00", "15,00,000.00", "19,30,000.00"],
    ["2024-07-15", "2024-07-15", "CHQ CLG/BHARAT FORGE/CHQ4402", "4402", "4,50,000.00", "0.00", "14,80,000.00"],
    ["2024-08-10", "2024-08-10", "NEFT/CLIENT/MAHINDRA/INV109", "", "0.00", "9,80,000.00", "24,60,000.00"],
    ["2024-09-22", "2024-09-22", "SALARY BULK NEFT/SEPTEMBER", "", "3,50,000.00", "0.00", "21,10,000.00"],
    ["2024-10-18", "2024-10-18", "NEFT/CLIENT/KIRLOSKAR/INV115", "", "0.00", "7,50,000.00", "28,60,000.00"],
    ["2024-11-25", "2024-11-25", "RTGS/VENDOR/ABB INDIA/CHQ4405", "4405", "11,00,000.00", "0.00", "17,60,000.00"],
    ["2024-12-30", "2024-12-30", "NEFT/CLIENT/L&T HEAVY/INV120", "", "0.00", "14,20,000.00", "31,80,000.00"],
    ["2025-01-14", "2025-01-14", "GST PAYMENT JAN 2025/CHALLAN", "", "2,80,000.00", "0.00", "29,00,000.00"],
    ["2025-02-18", "2025-02-18", "NEFT/CLIENT/GODREJ TOOL/INV128", "", "0.00", "8,90,000.00", "37,90,000.00"],
    ["2025-03-10", "2025-03-10", "VENDOR PAYMENT/APEX TOOLS/CHQ4408", "4408", "6,50,000.00", "0.00", "31,40,000.00"],
    ["2025-03-24", "2025-03-24", "CHQ CLG/VENDOR ADVANCE/CHQ4409", "4409", "5,00,000.00", "0.00", "26,40,000.00"],
    # Timing difference: Books recorded on 2025-03-25, cleared on 2025-03-28 (+3 days)
    ["2025-03-28", "2025-03-28", "CHQ CLG/ELECTRO SENSORS/CHQ4410", "4410", "4,20,000.00", "0.00", "22,20,000.00"],
    # Bank charges not entered in books
    ["2025-03-31", "2025-03-31", "ANNUAL FOLIO & CMS BANK CHARGES", "", "1,180.00", "0.00", "22,18,820.00"],
    # Deposit from customer cleared on 31-Mar
    ["2025-03-31", "2025-03-31", "NEFT/CLIENT/THERMAX/INV132", "", "0.00", "4,50,000.00", "26,68,820.00"],
]

bank_path = os.path.join(OUT_DIR, 'bank_statement_fy24_25.csv')
with open(bank_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerows(bank_rows)

# -------------------------------------------------------------
# 4. GSTR-2B Statement (ITC Verification)
# -------------------------------------------------------------
gstr2b_rows = [
    ["GSTIN of Supplier", "Trade Name", "Invoice Number", "Invoice Date", "Invoice Value", "Taxable Value", "Integrated Tax", "Central Tax", "State Tax", "ITC Availability"],
    ["27AAACS1234A1Z1", "Siemens Industrial Drives", "INV-2024-001", "2024-05-10", "9,67,600.00", "8,20,000.00", "0.00", "73,800.00", "73,800.00", "Y"],
    ["27AABCB5678B1Z2", "Bharat Forge Automation", "BFA/24/091", "2024-07-12", "5,31,000.00", "4,50,000.00", "0.00", "40,500.00", "40,500.00", "Y"],
    ["27AAACA9999C1Z3", "ABB India Limited", "ABB-MH-881", "2024-11-20", "12,98,000.00", "11,00,000.00", "0.00", "99,000.00", "99,000.00", "Y"],
    ["27AABCE1111D1Z4", "Electro Sensors Pune", "ESP-5512", "2025-03-22", "4,95,600.00", "4,20,000.00", "0.00", "37,800.00", "37,800.00", "Y"],
    ["27AAACP2222E1Z5", "Precision Tools Micro Engg", "PTM-101", "2025-01-10", "2,83,200.00", "2,40,000.00", "0.00", "21,600.00", "21,600.00", "Y"],
    ["27AABCS3333F1Z6", "Shree Fasteners Small Ind", "SFS-409", "2025-01-05", "2,18,300.00", "1,85,000.00", "0.00", "16,650.00", "16,650.00", "Y"],
]

gstr2b_path = os.path.join(OUT_DIR, 'gstr_2b_itc_statement.csv')
with open(gstr2b_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerows(gstr2b_rows)

# -------------------------------------------------------------
# 5. Purchase Register (Includes 2 invoices missing from 2B)
# -------------------------------------------------------------
purchase_rows = [
    ["Bill No", "Supplier Name", "Supplier GSTIN", "Invoice Date", "Taxable Amount", "GST Amount", "Total Invoice Value"],
    ["INV-2024-001", "Siemens Industrial Drives", "27AAACS1234A1Z1", "2024-05-10", "8,20,000.00", "1,47,600.00", "9,67,600.00"],
    ["BFA/24/091", "Bharat Forge Automation", "27AABCB5678B1Z2", "2024-07-12", "4,50,000.00", "81,000.00", "5,31,000.00"],
    ["ABB-MH-881", "ABB India Limited", "27AAACA9999C1Z3", "2024-11-20", "11,00,000.00", "1,98,000.00", "12,98,000.00"],
    ["ESP-5512", "Electro Sensors Pune", "27AABCE1111D1Z4", "2025-03-22", "4,20,000.00", "75,600.00", "4,95,600.00"],
    ["PTM-101", "Precision Tools Micro Engg", "27AAACP2222E1Z5", "2025-01-10", "2,40,000.00", "43,200.00", "2,83,200.00"],
    ["SFS-409", "Shree Fasteners Small Ind", "27AABCS3333F1Z6", "2025-01-05", "1,85,000.00", "33,300.00", "2,18,300.00"],
    # MISSING FROM 2B (Vendor failed to file GSTR-1 -> Rule 36(4) Ineligible ITC)
    ["APX-9901", "Apex Tooling Solutions", "27AABCA7777G1Z7", "2025-03-08", "6,50,000.00", "1,17,000.00", "7,67,000.00"],
    ["APX-9944", "Apex Tooling Solutions", "27AABCA7777G1Z7", "2025-03-25", "2,50,000.00", "45,000.00", "2,95,000.00"],
]

purch_path = os.path.join(OUT_DIR, 'purchase_register.csv')
with open(purch_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerows(purchase_rows)

# -------------------------------------------------------------
# 6. General Ledger Dump (Includes Section 40A(3) Cash Payments)
# -------------------------------------------------------------
gl_rows = [
    ["Voucher Date", "Voucher No", "Voucher Type", "Particulars", "Narration", "Debit (INR)", "Credit (INR)"],
    ["2024-04-15", "JV-01", "JOURNAL", "Plant & Industrial Machinery", "Purchase of CNC machine", "30,00,000.00", "0.00"],
    ["2024-05-10", "PV-02", "PAYMENT", "Siemens Industrial Drives", "Payment for drive components", "8,20,000.00", "0.00"],
    ["2024-08-14", "CP-2024-082", "PAYMENT", "Office Maintenance Expenses", "Single day cash settlement over 10k limit", "35,000.00", "0.00"],
    ["2024-11-12", "CP-2024-119", "PAYMENT", "Freight Inward Charges", "Single day cash payment to transporter", "45,000.00", "0.00"],
    ["2024-11-20", "PV-05", "PAYMENT", "ABB India Limited", "Robotic controller settlement", "11,00,000.00", "0.00"],
    ["2025-03-22", "PV-06", "PAYMENT", "Electro Sensors Pune", "Sensor batches settlement", "4,20,000.00", "0.00"],
    ["2025-03-31", "JV-08", "JOURNAL", "Depreciation Expense", "Annual Schedule II depreciation entry", "8,45,000.00", "0.00"],
]

gl_path = os.path.join(OUT_DIR, 'general_ledger_dump.csv')
with open(gl_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerows(gl_rows)

# -------------------------------------------------------------
# 7. Subledger Creditors Aging & Section 43B(h) MSME
# -------------------------------------------------------------
subledger_rows = [
    ["Party Name", "Party PAN", "Classification", "MSME Type", "Invoice No", "Invoice Date", "Due Date", "Outstanding Amount", "Is Overdue 43Bh"],
    ["Siemens Industrial Drives", "AAACS1234A", "CREDITOR", "LARGE", "INV-2024-001", "2024-05-10", "2024-06-24", "0.00", "NO"],
    ["Bharat Forge Automation", "AABCB5678B", "CREDITOR", "MEDIUM", "BFA/24/091", "2024-07-12", "2024-08-26", "2,50,000.00", "NO"],
    ["ABB India Limited", "AAACA9999C", "CREDITOR", "LARGE", "ABB-MH-881", "2024-11-20", "2025-01-04", "5,00,000.00", "NO"],
    # Section 43B(h) OVERDUE MSME 1 (> 45 days)
    ["Precision Tools Micro Engg", "AAACP2222E", "CREDITOR", "MICRO", "PTM-101", "2025-01-10", "2025-02-24", "2,40,000.00", "YES"],
    # Section 43B(h) OVERDUE MSME 2 (> 45 days)
    ["Shree Fasteners Small Ind", "AABCS3333F", "CREDITOR", "SMALL", "SFS-409", "2025-01-05", "2025-02-19", "1,85,000.00", "YES"],
    ["Apex Tooling Solutions", "AABCA7777G", "CREDITOR", "MEDIUM", "APX-9901", "2025-03-08", "2025-04-22", "6,50,000.00", "NO"],
    ["Electro Sensors Pune", "AABCE1111D", "CREDITOR", "MEDIUM", "ESP-5512", "2025-03-22", "2025-05-06", "4,25,000.00", "NO"],
]

sub_path = os.path.join(OUT_DIR, 'subledger_debtors_creditors.csv')
with open(sub_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerows(subledger_rows)

# -------------------------------------------------------------
# 8. Fixed Asset Register (Dual Depreciation Comparison)
# -------------------------------------------------------------
far_rows = [
    ["Asset Code", "Asset Name", "Category", "Purchase Date", "Capitalization Date", "Original Cost", "Sch II Life (Yrs)", "Sch II SLM Depn", "Sec 32 Block Rate", "Sec 32 WDV Depn"],
    ["FA-001", "CNC 5-Axis Milling Center", "PLANT_MACHINERY", "2024-04-01", "2024-04-01", "30,00,000.00", "15", "1,90,000.00", "15%", "4,50,000.00"],
    ["FA-002", "Industrial 6-Axis Robotic Arm", "PLANT_MACHINERY", "2024-04-01", "2024-04-01", "15,00,000.00", "15", "95,000.00", "15%", "2,25,000.00"],
    ["FA-003", "Enterprise AI & SCADA Servers", "IT_COMPUTERS", "2024-04-01", "2024-04-01", "12,00,000.00", "3", "3,80,000.00", "40%", "4,80,000.00"],
    ["FA-004", "Executive Modular Workstations", "FURNITURE", "2024-04-01", "2024-04-01", "8,00,000.00", "10", "76,000.00", "10%", "80,000.00"],
]

far_path = os.path.join(OUT_DIR, 'fixed_asset_register.csv')
with open(far_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerows(far_rows)

# -------------------------------------------------------------
# 9. Expected Ground-Truth Specification (JSON)
# -------------------------------------------------------------
expected_ground_truth = {
    "company": {
        "name": "Vanguard Industrial Automations Private Limited",
        "cin": "U29100MH2020PTC345678",
        "pan": "AABCV9876K",
        "gstin": "27AABCV9876K1Z8",
        "entity_type": "PVT_LTD",
        "financial_year": "FY 2024-25"
    },
    "trial_balance": {
        "is_balanced": True,
        "total_debits": "25000000.00",
        "total_credits": "25000000.00",
        "difference": "0.00",
        "accounts_count": 19
    },
    "unbalanced_tb": {
        "is_balanced": False,
        "total_debits": "25025000.00",
        "total_credits": "25000000.00",
        "difference": "25000.00"
    },
    "financial_overview": {
        "revenue_from_operations": "12000000.00",
        "total_expenses": "10050000.00",
        "net_profit": "1950000.00",
        "gross_ppe": "6500000.00",
        "cash_and_bank": "1800000.00"
    },
    "tax_audit_disallowances": {
        "section_43bh_msme_overdue_total": "425000.00",
        "section_43bh_overdue_count": 2,
        "section_40a3_cash_total": "80000.00",
        "section_40a3_violations_count": 2
    },
    "fixed_assets_dual_depreciation": {
        "total_gross_block": "6500000.00",
        "total_sch_ii_slm": "741000.00",
        "total_sec_32_wdv": "1235000.00",
        "depreciation_variance": "-494000.00"
    },
    "reconciliation_suite": {
        "bank_recon_items_count": 16,
        "unpresented_cheques_count": 1,
        "gst_itc_missing_in_2b_count": 2,
        "gst_itc_missing_in_2b_taxable": "900000.00",
        "gst_itc_missing_in_2b_tax": "162000.00"
    }
}

truth_path = os.path.join(OUT_DIR, 'expected_ground_truth.json')
with open(truth_path, 'w', encoding='utf-8') as f:
    json.dump(expected_ground_truth, f, indent=2)

print(f"Synthetic acceptance dataset generated successfully in {OUT_DIR}:")
for fname in os.listdir(OUT_DIR):
    fsize = os.path.getsize(os.path.join(OUT_DIR, fname))
    print(f"  - {fname} ({fsize} bytes)")
