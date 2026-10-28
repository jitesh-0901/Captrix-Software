import os
import sys
import pytest
from decimal import Decimal
from datetime import date, datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from apps.companies.models import Company, Engagement, FinancialYear, EntityType, EngagementStatus
from apps.accounting.models import LedgerAccount, Transaction, VoucherType, ScheduleIIIGroup, AccountType
from apps.accounting.services import TrialBalanceService, GeneralLedgerScrutinyService
from apps.reconciliation.services import BankReconciliationEngine, GstItcReconciliationEngine
from apps.reconciliation.models import ReconciliationStatus, MatchType
from apps.audit.far_depreciation import FixedAssetAuditEngine
from apps.audit.services import FinancialRatiosEngine
from apps.audit.statutory_forms import StatutoryFormMatrixEngine
from apps.reporting.report_builder import ConsolidatedAuditReportBuilder
from apps.reporting.exporters import ReportExporterService


@pytest.fixture
def test_setup():
    company, _ = Company.objects.get_or_create(
        cin="U29253TN2018PTC123456",
        defaults={
            "name": "Asterion Industrial Components Private Limited",
            "pan": "AAACA1234A",
            "gstin": "33AAACA1234A1Z5",
            "entity_type": EntityType.PVT_LTD
        }
    )
    fy, _ = FinancialYear.objects.get_or_create(
        company=company,
        label="FY 2025-26",
        defaults={
            "start_date": date(2025, 4, 1),
            "end_date": date(2026, 3, 31)
        }
    )
    engagement, _ = Engagement.objects.get_or_create(
        company=company,
        financial_year=fy,
        defaults={
            "title": "Statutory Audit FY 2025-26",
            "status": EngagementStatus.FIELDWORK,
            "overall_materiality": Decimal("500000.00"),
            "performance_materiality": Decimal("375000.00")
        }
    )
    return {"company": company, "fy": fy, "engagement": engagement}


@pytest.mark.django_db
def test_general_ledger_trial_balance_statuses_and_differences(test_setup):
    """Priority 1: Test General Ledger debit/credit, exact difference, and balanced/unbalanced/not_computed statuses."""
    eng = test_setup["engagement"]

    # 1. Balanced Trial Balance
    balanced_rows = [
        {"Account Name": "Capital", "Credit": "1000000.00"},
        {"Account Name": "Bank Account", "Debit": "1000000.00"}
    ]
    res_bal = TrialBalanceService.calculate_trial_balance(balanced_rows, engagement=eng)
    assert res_bal["is_balanced"] is True
    assert res_bal["status"] == "BALANCED"
    assert res_bal["total_debits"] == "1000000.00"
    assert res_bal["total_credits"] == "1000000.00"
    assert res_bal["difference_amount"] == "0.00"
    assert res_bal["exact_difference"] == "0.00"

    # 2. Unbalanced Trial Balance
    unbal_rows = [
        {"Account Name": "Capital", "Credit": "1000000.00"},
        {"Account Name": "Bank Account", "Debit": "950000.00"}
    ]
    res_unbal = TrialBalanceService.calculate_trial_balance(unbal_rows, engagement=eng)
    assert res_unbal["is_balanced"] is False
    assert res_unbal["status"] == "UNBALANCED"
    assert Decimal(res_unbal["difference_amount"]) == Decimal("-50000.00")
    assert Decimal(res_unbal["exact_difference"]) == Decimal("-50000.00")

    # 3. Empty Rows (Not Computed)
    res_empty = TrialBalanceService.calculate_trial_balance([], engagement=eng)
    assert res_empty["is_balanced"] is False
    assert res_empty["status"] == "NOT_COMPUTED"


@pytest.mark.django_db
def test_general_ledger_scrutiny_and_sa240_indicators(test_setup):
    """Test unusual transaction detection (Sundays, round numbers, large misc expenses) and SA 240 non-accusatory flags."""
    eng = test_setup["engagement"]
    company = test_setup["company"]

    bank_acc, _ = LedgerAccount.objects.get_or_create(
        company=company, name="HDFC Current Bank",
        defaults={"closing_balance": Decimal("5000000.00"), "closing_balance_type": "Dr"}
    )
    misc_acc, _ = LedgerAccount.objects.get_or_create(
        company=company, name="Miscellaneous Office Expenses",
        defaults={"closing_balance": Decimal("500000.00"), "closing_balance_type": "Dr"}
    )

    txns = [
        # Sunday transaction (2025-06-15 is Sunday)
        Transaction(
            engagement=eng, ledger_account=bank_acc, voucher_number="VCH-01",
            voucher_type=VoucherType.PAYMENT, date=date(2025, 6, 15),
            debit_amount=Decimal("50000.00"), credit_amount=Decimal("0.00"),
            narration="Payment to vendor"
        ),
        # Large misc expense (₹35,000 >= ₹25,000)
        Transaction(
            engagement=eng, ledger_account=misc_acc, voucher_number="VCH-02",
            voucher_type=VoucherType.JOURNAL, date=date(2025, 6, 16),
            debit_amount=Decimal("35000.00"), credit_amount=Decimal("0.00"),
            narration="Sundry administrative expenses"
        ),
        # Round number payment (₹100,000)
        Transaction(
            engagement=eng, ledger_account=bank_acc, voucher_number="VCH-03",
            voucher_type=VoucherType.PAYMENT, date=date(2025, 6, 17),
            debit_amount=Decimal("100000.00"), credit_amount=Decimal("0.00"),
            narration="Advance payment"
        )
    ]
    Transaction.objects.filter(engagement=eng).delete()
    created_txns = Transaction.objects.bulk_create(txns)

    res = GeneralLedgerScrutinyService.scrutinize_transactions(created_txns)
    assert res["flagged_count"] >= 3

    # Verify Sunday transaction
    t1 = Transaction.objects.get(voucher_number="VCH-01")
    assert "SUNDAY_TRANSACTION" in t1.risk_flags
    assert "WEEKEND_POSTING" in t1.risk_flags

    # Verify Large Misc Expense
    t2 = Transaction.objects.get(voucher_number="VCH-02")
    assert "LARGE_MISCELLANEOUS_EXPENSE" in t2.risk_flags

    # Verify Round Number Payment
    t3 = Transaction.objects.get(voucher_number="VCH-03")
    assert "ROUND_NUMBER_PAYMENT" in t3.risk_flags

    # Verify SA 240 disclaimer exists and does not label transactions as fraud
    assert "SA 240" in res["sa_240_disclaimer"]
    assert "does not establish intentional fraud without corroborating evidence" in res["sa_240_disclaimer"]


@pytest.mark.django_db
def test_bank_reconciliation_exact_mathematical_bridge(test_setup):
    """Priority 2: Test BRS transaction matching, bridge calculation, and ledger-only/bank-only breakdown."""
    eng = test_setup["engagement"]

    # Starting Cashbook: ₹10,000,000.00
    starting_cashbook = Decimal("10000000.00")

    # Cashbook entries
    cashbook_items = [
        # Matched deposit: ₹500,000
        {"date": "2026-03-20", "ref": "DEP-001", "desc": "Customer Receipt", "amount": "500000.00", "type": "DEPOSIT"},
        # Unpresented cheque (valid timing, < 90 days): ₹200,000
        {"date": "2026-03-28", "ref": "CHQ-101", "desc": "Vendor Payment", "amount": "200000.00", "type": "WITHDRAWAL"},
        # Uncleared deposit (valid timing, < 90 days): ₹150,000
        {"date": "2026-03-30", "ref": "DEP-002", "desc": "Cheque Deposit", "amount": "150000.00", "type": "DEPOSIT"},
    ]

    # Bank statement entries
    bank_items = [
        # Matched deposit: ₹500,000
        {"date": "2026-03-21", "ref": "DEP-001", "desc": "NEFT Inward", "amount": "500000.00", "type": "DEPOSIT"},
        # Bank-only debit: Bank service charges ₹5,000
        {"date": "2026-03-31", "ref": "CHG-001", "desc": "Bank Charges", "amount": "5000.00", "type": "WITHDRAWAL"},
        # Bank-only credit: Direct interest ₹12,000
        {"date": "2026-03-31", "ref": "INT-001", "desc": "Bank Interest", "amount": "12000.00", "type": "DEPOSIT"},
    ]

    # Mathematical bridge:
    # 10,000,000 + 200,000 (unpresented) - 150,000 (uncleared) + 12,000 (interest) - 5,000 (charges) = 10,057,000.00
    expected_statement_bal = Decimal("10057000.00")

    rec = BankReconciliationEngine.execute_reconciliation(
        engagement=eng,
        as_of_date=date(2026, 3, 31),
        cashbook_items=cashbook_items,
        bank_items=bank_items,
        starting_cashbook_balance=starting_cashbook,
        actual_statement_balance=expected_statement_bal
    )

    s_data = rec.summary_data
    assert Decimal(s_data["unreconciled_variance"]) == Decimal("0.00")
    assert s_data["arithmetic_balanced"] is True
    assert Decimal(s_data["computed_statement_balance"]) == expected_statement_bal

    # Check breakdown
    assert s_data["matched_items_count"] == 1
    assert s_data["ledger_only_transactions"]["unpresented_cheques_count"] == 1
    assert Decimal(s_data["ledger_only_transactions"]["unpresented_cheques_amount"]) == Decimal("200000.00")
    assert s_data["ledger_only_transactions"]["uncleared_deposits_count"] == 1
    assert Decimal(s_data["ledger_only_transactions"]["uncleared_deposits_amount"]) == Decimal("150000.00")

    assert s_data["bank_only_transactions"]["bank_service_fees_count"] == 1
    assert Decimal(s_data["bank_only_transactions"]["bank_service_fees_amount"]) == Decimal("5000.00")
    assert s_data["bank_only_transactions"]["customer_receipts_count"] == 1
    assert Decimal(s_data["bank_only_transactions"]["customer_receipts_amount"]) == Decimal("12000.00")


@pytest.mark.django_db
def test_bank_reconciliation_missing_data_fails_closed(test_setup):
    """Test BRS fails closed to REVIEW_REQUIRED if data is missing or stale cheques exist."""
    eng = test_setup["engagement"]

    # When actual statement balance is missing / zero with open timing items
    rec = BankReconciliationEngine.execute_reconciliation(
        engagement=eng,
        as_of_date=date(2026, 3, 31),
        cashbook_items=[],
        bank_items=[],
        starting_cashbook_balance=Decimal("100000.00"),
        actual_statement_balance=None
    )
    assert rec.status == ReconciliationStatus.REVIEW_REQUIRED


@pytest.mark.django_db
def test_gst_reconciliation_bidirectional_and_variance_detection(test_setup):
    """Priority 3: Test GST ITC reconciliation bidirectional invoice matching and taxable/tax mismatch detection."""
    eng = test_setup["engagement"]

    purchase_items = [
        # 1. Exact match
        {"gstin": "27AABCS1429B1Z1", "invoice_no": "INV-001", "date": "2025-05-10", "taxable_value": "100000.00", "itc_amount": "18000.00", "vendor_name": "Supplier A"},
        # 2. Tax amount mismatch
        {"gstin": "27AABCS1429B1Z2", "invoice_no": "INV-002", "date": "2025-05-12", "taxable_value": "200000.00", "itc_amount": "36000.00", "vendor_name": "Supplier B"},
        # 3. Missing in GSTR-2B
        {"gstin": "27AABCS1429B1Z3", "invoice_no": "INV-003", "date": "2025-05-15", "taxable_value": "150000.00", "itc_amount": "27000.00", "vendor_name": "Supplier C"}
    ]

    gstr2b_items = [
        # Exact match for INV-001
        {"gstin": "27AABCS1429B1Z1", "invoice_no": "INV-001", "date": "2025-05-10", "taxable_value": "100000.00", "itc_amount": "18000.00", "vendor_name": "Supplier A"},
        # Tax mismatch for INV-002 (2B has 24,000 instead of 36,000)
        {"gstin": "27AABCS1429B1Z2", "invoice_no": "INV-002", "date": "2025-05-12", "taxable_value": "200000.00", "itc_amount": "24000.00", "vendor_name": "Supplier B"},
        # Invoice in 2B but missing in books
        {"gstin": "27AABCS1429B1Z4", "invoice_no": "INV-004", "date": "2025-05-20", "taxable_value": "50000.00", "itc_amount": "9000.00", "vendor_name": "Supplier D"}
    ]

    rec = GstItcReconciliationEngine.execute_reconciliation(
        engagement=eng,
        as_of_date=date(2026, 3, 31),
        purchase_items=purchase_items,
        gstr2b_items=gstr2b_items
    )

    s = rec.summary_data
    assert rec.status == ReconciliationStatus.REVIEW_REQUIRED  # Discrepancies exist, must not be BALANCED
    assert s["matched_invoices"] == 1
    assert s["mismatched_tax_invoices"] == 1
    assert s["missing_in_gstr_2b_invoices"] == 1
    assert s["missing_in_purchase_register_invoices"] == 1
    assert s["rule_36_4_risk"] is True
    assert Decimal(s["total_itc_per_books"]) == Decimal("81000.00")
    assert Decimal(s["total_itc_per_gstr2b"]) == Decimal("51000.00")


@pytest.mark.django_db
def test_fixed_assets_and_depreciation_recalculation(test_setup):
    """Priority 4: Test FAR cost mapping, zero cost detection, date anomalies, and dual depreciation."""
    eng = test_setup["engagement"]

    far_records = [
        # Valid asset with 'Purchase Cost' alias
        {
            "Asset ID": "FA-001",
            "Asset Description": "CNC Milling Center",
            "Asset Category": "PLANT & MACHINERY",
            "Purchase Cost": "5,000,000.00",
            "Acquisition Date": "2025-04-01",
            "Put to Use Date": "2025-04-01",
            "Useful Life": "15.0",
            "Residual %": "5.0",
            "Booked Depreciation": "316666.67"
        },
        # Zero cost asset
        {
            "Asset ID": "FA-002",
            "Asset Description": "Spare Spindle",
            "Asset Category": "PLANT & MACHINERY",
            "Cost": "0.00",
            "Acquisition Date": "2025-04-01",
            "Put to Use Date": "2025-04-01"
        },
        # Inverted date asset (put to use precedes acquisition)
        {
            "Asset ID": "FA-003",
            "Asset Description": "Packaging Machine",
            "Asset Category": "PLANT & MACHINERY",
            "Purchase Cost": "1,000,000.00",
            "Acquisition Date": "2025-08-01",
            "Put to Use Date": "2025-07-01",
            "Useful Life": "10.0"
        }
    ]

    res = FixedAssetAuditEngine.import_and_validate_far(engagement=eng, far_records=far_records)
    assert res["total_assets"] == 3
    assert res["zero_cost_assets_count"] == 1
    assert res["invalid_dates_count"] == 1
    assert Decimal(res["recalculated_schedule_ii_depreciation"]) > Decimal("0.00")
    assert len(res["asset_wise_depreciation"]) == 3

    # Check exceptions created
    assert eng.exceptions.filter(rule_code="RULE_FAR_ZERO_COST").exists()
    assert eng.exceptions.filter(rule_code="RULE_FAR_INVALID_DATE").exists()


@pytest.mark.django_db
def test_financial_statements_balance_sheet_equation(test_setup):
    """Priority 5: Test Balance Sheet equation verification and strict non-zero difference check."""
    # Balanced Trial Balance
    balanced_accounts = [
        {"account_name": "Equity Share Capital", "schedule_iii_group": ScheduleIIIGroup.SHARE_CAPITAL, "debit": "0.00", "credit": "10000000.00"},
        {"account_name": "Plant & Machinery", "schedule_iii_group": ScheduleIIIGroup.PPE, "debit": "8000000.00", "credit": "0.00"},
        {"account_name": "Bank Balance", "schedule_iii_group": ScheduleIIIGroup.CASH_EQUIVALENTS, "debit": "2000000.00", "credit": "0.00"},
    ]
    fs_bal = TrialBalanceService.compile_financial_statements(balanced_accounts)
    assert fs_bal["balance_sheet"]["is_balanced"] is True
    assert Decimal(fs_bal["balance_sheet"]["difference"]) == Decimal("0.00")

    # Unbalanced Trial Balance (difference of ₹500,000)
    unbal_accounts = [
        {"account_name": "Equity Share Capital", "schedule_iii_group": ScheduleIIIGroup.SHARE_CAPITAL, "debit": "0.00", "credit": "10000000.00"},
        {"account_name": "Plant & Machinery", "schedule_iii_group": ScheduleIIIGroup.PPE, "debit": "8000000.00", "credit": "0.00"},
        {"account_name": "Bank Balance", "schedule_iii_group": ScheduleIIIGroup.CASH_EQUIVALENTS, "debit": "1500000.00", "credit": "0.00"},
    ]
    fs_unbal = TrialBalanceService.compile_financial_statements(unbal_accounts)
    assert fs_unbal["balance_sheet"]["is_balanced"] is False
    assert Decimal(fs_unbal["balance_sheet"]["difference"]) == Decimal("500000.00")


@pytest.mark.django_db
def test_financial_ratios_division_by_zero_prevention_and_metadata(test_setup):
    """Priority 6: Test financial ratios formulas, zero-denominator prevention, and metadata outputs."""
    eng = test_setup["engagement"]

    # When accounts are completely empty
    ratios_empty = FinancialRatiosEngine.compute_ratios(None)
    assert len(ratios_empty) >= 7
    for r in ratios_empty:
        assert r["status"] == "AWAITING_DATA"

    # Setup accounts for ratio testing
    accounts = [
        {"account_name": "Trade Debtors", "schedule_iii_group": ScheduleIIIGroup.TRADE_RECEIVABLES, "debit": "3000000.00", "credit": "0.00"},
        {"account_name": "Inventories", "schedule_iii_group": ScheduleIIIGroup.INVENTORIES, "debit": "2000000.00", "credit": "0.00"},
        {"account_name": "Trade Creditors", "schedule_iii_group": ScheduleIIIGroup.TRADE_PAYABLES, "debit": "0.00", "credit": "4000000.00"},
        {"account_name": "Revenue from Operations", "schedule_iii_group": ScheduleIIIGroup.REVENUE_OPERATIONS, "debit": "0.00", "credit": "12000000.00"},
        {"account_name": "Raw Materials Consumed", "schedule_iii_group": ScheduleIIIGroup.COST_OF_MATERIALS, "debit": "8000000.00", "credit": "0.00"},
        {"account_name": "Share Capital", "schedule_iii_group": ScheduleIIIGroup.SHARE_CAPITAL, "debit": "0.00", "credit": "5000000.00"}
    ]

    tb_res = TrialBalanceService.calculate_trial_balance(accounts, engagement=eng)
    ratios = FinancialRatiosEngine.compute_ratios(eng)

    ratio_dict = {r["name"]: r for r in ratios}

    # Current Ratio = CA (5,000,000) / CL (4,000,000) = 1.25x
    cr = ratio_dict["Current Ratio"]
    assert cr["value"] == 1.25
    assert cr["numerator_name"] == "Current Assets"
    assert Decimal(cr["numerator_value"]) == Decimal("5000000.00")
    assert cr["denominator_name"] == "Current Liabilities"
    assert Decimal(cr["denominator_value"]) == Decimal("4000000.00")

    # Quick Ratio = (5,000,000 - 2,000,000) / 4,000,000 = 0.75x
    qr = ratio_dict["Quick Ratio (Acid Test)"]
    assert qr["value"] == 0.75

    # Receivables Turnover = 12,000,000 / 3,000,000 = 4.0x
    rt = ratio_dict["Trade Receivables Turnover Ratio"]
    assert rt["value"] == 4.0

    # Payables Turnover = 8,000,000 / 4,000,000 = 2.0x
    pt = ratio_dict["Trade Payables Turnover Ratio"]
    assert pt["value"] == 2.0


@pytest.mark.django_db
def test_statutory_forms_and_evidence_gating(test_setup):
    """Priority 7: Test CARO 2020 physical verification requirement and SA 240 fraud check evidence gating."""
    eng = test_setup["engagement"]

    # Provide FAR records without physical count sheet
    from apps.audit.models import FixedAsset
    FixedAsset.objects.create(
        engagement=eng, asset_id="FA-01", asset_name="Milling Machine",
        category="PLANT & MACHINERY", acquisition_date=date(2025, 4, 1),
        put_to_use_date=date(2025, 4, 1), original_cost=Decimal("1000000.00")
    )

    audits = StatutoryFormMatrixEngine.initialize_and_audit_clauses(eng)
    caro_clauses = [a for a in audits if a.form_type == "CARO_2020"]

    # CARO 3(i) should require review because physical verification report (Clause 3(i)(b)) is missing
    cl_1 = next((c for c in caro_clauses if c.clause_number == "Clause 3(i)"), None)
    assert cl_1 is not None
    assert cl_1.compliance_status == "REVIEW_REQUIRED"
    assert "Clause 3(i)(b)" in cl_1.auditor_remarks

    # CARO 3(xi) fraud check should state that statistical tests do not prove absence of fraud
    cl_11 = next((c for c in caro_clauses if c.clause_number == "Clause 3(xi)"), None)
    assert cl_11 is not None
    assert cl_11.compliance_status == "REVIEW_REQUIRED"
    assert "SA 240" in cl_11.auditor_remarks


@pytest.mark.django_db
def test_end_to_end_report_generation(test_setup):
    """Priority 8: Test complete end-to-end report generation with consistent figures and statuses."""
    eng = test_setup["engagement"]

    rep = ConsolidatedAuditReportBuilder.build_report(eng)
    assert rep["company_name"] == test_setup["company"].name
    assert rep["financial_year"] == "FY 2025-26"
    assert "sections" in rep
    assert len(rep["sections"]) >= 14

    # Test PDF generation without crashing
    pdf_bytes = ReportExporterService.export_consolidated_pdf(eng)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")
