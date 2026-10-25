import os
import openpyxl
import csv

os.makedirs('samples', exist_ok=True)

# 1. Trial Balance Excel
wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Trial_Balance"
ws.append(["Account Code", "Particulars", "Schedule III Group", "Debit (INR)", "Credit (INR)"])
tb_data = [
    ["1001", "Computer Systems & Hardware", "Property, Plant and Equipment", 4500000.00, 0.00],
    ["1002", "Office Equipment & Furniture", "Property, Plant and Equipment", 1850000.00, 0.00],
    ["1101", "Software IP & Licenses", "Intangible Assets", 2500000.00, 0.00],
    ["1201", "Mutual Fund Investments (Short-Term)", "Non-Current Investments", 3500000.00, 0.00],
    ["1301", "Trade Receivables (Domestic Clients)", "Trade Receivables", 6200000.00, 0.00],
    ["1302", "Trade Receivables (Export Clients)", "Trade Receivables", 4800000.00, 0.00],
    ["1401", "HDFC Bank Current Account", "Cash and Cash Equivalents", 3450000.00, 0.00],
    ["1402", "ICICI Bank Current Account", "Cash and Cash Equivalents", 1850000.00, 0.00],
    ["1403", "Petty Cash Account", "Cash and Cash Equivalents", 120000.00, 0.00],
    ["1501", "Prepaid Software Subscriptions", "Other Current Assets", 480000.00, 0.00],
    ["1502", "Security Deposits for Office Leases", "Long-Term Loans and Advances", 1200000.00, 0.00],
    ["2001", "Equity Share Capital", "Share Capital", 0.00, 10000000.00],
    ["2002", "Retained Earnings & Reserves", "Reserves and Surplus", 0.00, 8500000.00],
    ["2101", "HDFC Bank Term Loan", "Long-Term Borrowings", 0.00, 4500000.00],
    ["2201", "Trade Payables - Software Vendors", "Trade Payables", 0.00, 2250000.00],
    ["2202", "Trade Payables - Infrastructure", "Trade Payables", 0.00, 1850000.00],
    ["2301", "TDS Payable", "Other Current Liabilities", 0.00, 280000.00],
    ["2302", "GST Output Tax Payable", "Other Current Liabilities", 0.00, 520000.00],
    ["2303", "Salaries & Staff Dues Payable", "Short-Term Provisions", 0.00, 1350000.00],
    ["3001", "Software Development Revenue", "Revenue from Operations", 0.00, 12000000.00],
    ["3002", "Export IT Consulting Services", "Revenue from Operations", 0.00, 7000000.00],
    ["4001", "Employee Salaries & Allowances", "Employee Benefits Expense", 9500000.00, 0.00],
    ["4101", "AWS & Cloud Hosting Services", "Other Expenses", 2100000.00, 0.00],
    ["4102", "Legal & Professional Fees", "Other Expenses", 1400000.00, 0.00],
    ["4103", "Office Rent & Maintenance", "Other Expenses", 2800000.00, 0.00],
    ["4104", "Office Repairs & Renovation", "Other Expenses", 750000.00, 0.00],
    ["4201", "Depreciation on Hardware & PPE", "Depreciation and Amortization Expense", 1250000.00, 0.00],
    ["TOTAL", "Grand Total", "", 48250000.00, 48250000.00]
]
for r in tb_data:
    ws.append(r)
wb.save("samples/Apex_Infotech_Trial_Balance_FY24_25.xlsx")

# 2. Bank Statement CSV
with open("samples/HDFC_Bank_Statement_March_2025.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Txn Date", "Value Date", "Description", "Ref No / Cheque No", "Withdrawal (Dr)", "Deposit (Cr)", "Balance"])
    writer.writerow(["2025-03-01", "2025-03-01", "OPENING BALANCE B/F", "", "", "", "3740000.00"])
    writer.writerow(["2025-03-15", "2025-03-15", "INWARD NEFT CONSULTING REVENUE", "NEFT-4412", "", "500000.00", "4240000.00"])
    writer.writerow(["2025-03-26", "2025-03-26", "CLG CHQ DELL INDIA VENDOR PMT", "CHQ-894101", "145000.00", "", "4095000.00"])
    writer.writerow(["2025-03-29", "2025-03-29", "CLG CHQ PINNACLE PARK RENT", "CHQ-894102", "235000.00", "", "3860000.00"])
    writer.writerow(["2025-03-31", "2025-03-31", "ANNUAL FOLIO & BANK CHARGES", "CHG-9901", "3500.00", "", "3856500.00"])

# 3. GSTR-2B Excel
wb_gst = openpyxl.Workbook()
ws_gst = wb_gst.active
ws_gst.title = "GSTR-2B"
ws_gst.append(["GSTIN of Supplier", "Trade Name", "Invoice number", "Invoice date", "Invoice Value", "Taxable Value", "Integrated Tax", "Central Tax", "State Tax", "ITC Availability"])
gstr_data = [
    ["27AAACG1234D1ZP", "Amazon Web Services India Pvt Ltd", "INV-2025-01", "2025-01-10", 247800.00, 210000.00, 37800.00, 0.00, 0.00, "Yes"],
    ["07AABCT9988K1ZK", "Dell Global Services India Pvt Ltd", "DL-2025-88", "2025-02-14", 531000.00, 450000.00, 81000.00, 0.00, 0.00, "Yes"],
    ["27AABCM5566L1ZX", "Microsoft India Operations", "MS-8910", "2025-03-05", 118000.00, 100000.00, 18000.00, 0.00, 0.00, "Yes"]
]
for g in gstr_data:
    ws_gst.append(g)
wb_gst.save("samples/GSTR2B_Input_Tax_Credit_FY24_25.xlsx")

print("Created 3 sample workbooks in samples/ directory successfully.")
