import pytest
from decimal import Decimal
from datetime import date
from apps.companies.models import Company, FinancialYear, Engagement
from apps.accounting.models import Transaction, LedgerAccount, ChartOfAccounts, AccountType
from apps.accounting.validation import FinancialDataValidationService
from apps.reconciliation.services import BankReconciliationEngine, CrossDocumentReconciliationEngine
from apps.reconciliation.models import ReconciliationStatus, ReconciliationType, MatchType
from apps.reporting.services import WorkpaperDraftingService
from apps.audit.models import ExceptionItem, ExceptionSeverity, ExceptionStatus

@pytest.fixture
def test_setup():
    company = Company.objects.create(name="Acme Corp", pan="AAACA1234F")
    fy = FinancialYear.objects.create(
        company=company,
        label="FY 24-25",
        start_date=date(2024, 4, 1),
        end_date=date(2025, 3, 31)
    )
    engagement = Engagement.objects.create(
        company=company,
        financial_year=fy,
        title="FY 24-25 Statutory Audit"
    )
    coa_exp = ChartOfAccounts.objects.create(
        company=company,
        account_code="5001",
        account_name="Operating Expenses",
        account_type=AccountType.EXPENSE
    )
    coa_bank = ChartOfAccounts.objects.create(
        company=company,
        account_code="1002",
        account_name="Bank Accounts",
        account_type=AccountType.ASSET
    )
    ledger_exp = LedgerAccount.objects.create(
        company=company,
        name="Legal & Professional Fees",
        coa=coa_exp
    )
    ledger_bank = LedgerAccount.objects.create(
        company=company,
        name="HDFC Bank Current Account",
        coa=coa_bank
    )
    return {
        'company': company,
        'fy': fy,
        'engagement': engagement,
        'ledger_exp': ledger_exp,
        'ledger_bank': ledger_bank
    }

@pytest.mark.django_db
def test_financial_data_validation_period_and_vouchers(test_setup):
    engagement = test_setup['engagement']
    ledger_exp = test_setup['ledger_exp']
    ledger_bank = test_setup['ledger_bank']

    # 1. Out of bounds date
    Transaction.objects.create(
        engagement=engagement,
        ledger_account=ledger_exp,
        voucher_number="VR-2024-099",
        date=date(2023, 12, 15), # Outside FY 2024-25
        debit_amount=Decimal('5000.00'),
        credit_amount=Decimal('0.00')
    )
    # 2. Multi-leg unbalanced voucher VR-2024-100
    Transaction.objects.create(
        engagement=engagement,
        ledger_account=ledger_exp,
        voucher_number="VR-2024-100",
        date=date(2024, 5, 10),
        debit_amount=Decimal('10000.00'),
        credit_amount=Decimal('0.00')
    )
    Transaction.objects.create(
        engagement=engagement,
        ledger_account=ledger_bank,
        voucher_number="VR-2024-100",
        date=date(2024, 5, 10),
        debit_amount=Decimal('0.00'),
        credit_amount=Decimal('8000.00') # 2,000 difference
    )

    findings = FinancialDataValidationService.validate_engagement_transactions(engagement)
    rule_codes = [f.get('rule_code') for f in findings]
    
    assert 'DATE-OUT-OF-BOUNDS' in rule_codes
    assert 'VOUCHER-UNBALANCED' in rule_codes

@pytest.mark.django_db
def test_financial_data_validation_duplicates_and_rollforward(test_setup):
    engagement = test_setup['engagement']
    ledger_exp = test_setup['ledger_exp']

    # Duplicate candidate transactions
    Transaction.objects.create(
        engagement=engagement,
        ledger_account=ledger_exp,
        voucher_number="VR-DUP-01",
        date=date(2024, 7, 15),
        counterparty="Consultant ABC",
        debit_amount=Decimal('45000.00'),
        credit_amount=Decimal('0.00')
    )
    Transaction.objects.create(
        engagement=engagement,
        ledger_account=ledger_exp,
        voucher_number="VR-DUP-02",
        date=date(2024, 7, 15),
        counterparty="Consultant ABC",
        debit_amount=Decimal('45000.00'),
        credit_amount=Decimal('0.00')
    )

    findings = FinancialDataValidationService.validate_engagement_transactions(engagement)
    dup_finding = next((f for f in findings if f.get('rule_code') == 'DUPLICATE-CANDIDATE'), None)
    assert dup_finding is not None
    assert Decimal(dup_finding['amount']) == Decimal('45000.00')

    # Test rollforward validation equation
    # Opening 10,000 + Debits 5,000 - Credits 2,000 = Expected 13,000. Provided closing 12,000 (Mismatch)
    rf_check = FinancialDataValidationService.validate_rollforward(
        opening_balance=Decimal('10000.00'),
        total_debits=Decimal('5000.00'),
        total_credits=Decimal('2000.00'),
        closing_balance=Decimal('12000.00'),
        is_debit_balance=True
    )
    assert rf_check['is_reconciled'] is False
    assert rf_check['variance'] == Decimal('1000.00')

@pytest.mark.django_db
def test_bank_reconciliation_date_tolerance_and_one_to_many(test_setup):
    engagement = test_setup['engagement']
    
    cashbook_items = [
        # Two payments that clear together in bank as a single batch withdrawal of 70,000
        {'date': date(2025, 3, 20), 'ref': 'PAY-1', 'desc': 'Vendor 1', 'amount': '30000.00', 'type': 'WITHDRAWAL'},
        {'date': date(2025, 3, 20), 'ref': 'PAY-2', 'desc': 'Vendor 2', 'amount': '40000.00', 'type': 'WITHDRAWAL'},
        # One item clearing with +4 days tolerance
        {'date': date(2025, 3, 10), 'ref': 'CHQ-55', 'desc': 'Supplier X', 'amount': '15000.00', 'type': 'WITHDRAWAL'}
    ]
    bank_items = [
        {'date': date(2025, 3, 22), 'ref': 'BATCH-01', 'desc': 'BULK VENDOR PAYOUT', 'amount': '70000.00', 'type': 'WITHDRAWAL'},
        {'date': date(2025, 3, 14), 'ref': 'CHQ-55', 'desc': 'CLG CHQ SUPPLIER X', 'amount': '15000.00', 'type': 'WITHDRAWAL'}
    ]

    run = BankReconciliationEngine.execute_reconciliation(
        engagement=engagement,
        as_of_date=date(2025, 3, 31),
        cashbook_items=cashbook_items,
        bank_items=bank_items,
        starting_cashbook_balance=Decimal('100000.00'),
        actual_statement_balance=Decimal('15000.00'),
        date_tolerance_days=5
    )

    # Toleranced item matched
    matched_items = run.items.filter(is_matched=True)
    assert matched_items.count() >= 1

@pytest.mark.django_db
def test_cross_document_reconciliation_blocked_on_missing_files(test_setup):
    engagement = test_setup['engagement']
    
    # Run all cross document reconciliations when registers are not uploaded
    runs = CrossDocumentReconciliationEngine.run_all_cross_reconciliations(engagement)
    
    sales_run = next(r for r in runs if r.recon_type == ReconciliationType.SALES_VS_LEDGER)
    purchase_run = next(r for r in runs if r.recon_type == ReconciliationType.PURCHASE_VS_LEDGER)
    far_run = next(r for r in runs if r.recon_type == ReconciliationType.FAR_VS_LEDGER)
    
    # Missing registers must be BLOCKED, not fail or fabricate numbers
    assert sales_run.status == ReconciliationStatus.BLOCKED
    assert 'Sales Register' in str(sales_run.summary_data)
    assert purchase_run.status == ReconciliationStatus.BLOCKED
    assert far_run.status == ReconciliationStatus.BLOCKED

@pytest.mark.django_db
def test_workpaper_drafting_service(test_setup):
    engagement = test_setup['engagement']
    
    # Seed a reconciliation run and an exception
    ExceptionItem.objects.create(
        engagement=engagement,
        rule_code='SEC-40A3',
        title='Cash payment exceeding 10,000 INR',
        category='Statutory Compliance',
        severity=ExceptionSeverity.CRITICAL,
        status=ExceptionStatus.OPEN,
        amount_involved=Decimal('35000.00'),
        explanation='Cash payment violated Section 40A(3)',
        recommended_action='Disallow in Form 3CD Clause 21(d)'
    )

    wps = WorkpaperDraftingService.draft_workpapers(engagement)
    assert len(wps) >= 5
    
    # Check that Form 3CD workpaper recorded the exception
    wp_3cd = next(w for w in wps if w.wp_reference == 'WP-T301')
    assert '35,000' in wp_3cd.exceptions_noted
    assert '35,000' in wp_3cd.results_summary
