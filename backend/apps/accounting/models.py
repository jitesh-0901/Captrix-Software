from django.db import models
from decimal import Decimal
from apps.companies.models import Company, Engagement
from apps.ingestion.models import Document

class AccountType(models.TextChoices):
    ASSET = 'ASSET', 'Asset'
    LIABILITY = 'LIABILITY', 'Liability'
    EQUITY = 'EQUITY', 'Equity'
    REVENUE = 'REVENUE', 'Revenue'
    EXPENSE = 'EXPENSE', 'Expense'

class ScheduleIIIGroup(models.TextChoices):
    # Non-Current Assets
    PPE = 'PPE', 'Property, Plant and Equipment'
    INTANGIBLE = 'INTANGIBLE', 'Intangible Assets'
    NON_CURRENT_INVESTMENTS = 'NON_CURRENT_INVESTMENTS', 'Non-Current Investments'
    DEFERRED_TAX_ASSET = 'DEFERRED_TAX_ASSET', 'Deferred Tax Assets (Net)'
    LONG_TERM_LOANS_ADV = 'LONG_TERM_LOANS_ADV', 'Long-Term Loans and Advances'
    # Current Assets
    INVENTORIES = 'INVENTORIES', 'Inventories'
    TRADE_RECEIVABLES = 'TRADE_RECEIVABLES', 'Trade Receivables'
    CASH_EQUIVALENTS = 'CASH_EQUIVALENTS', 'Cash and Cash Equivalents'
    SHORT_TERM_LOANS = 'SHORT_TERM_LOANS', 'Short-Term Loans and Advances'
    OTHER_CURRENT_ASSETS = 'OTHER_CURRENT_ASSETS', 'Other Current Assets'
    # Equity
    SHARE_CAPITAL = 'SHARE_CAPITAL', 'Share Capital'
    RESERVES_SURPLUS = 'RESERVES_SURPLUS', 'Reserves and Surplus'
    # Non-Current Liabilities
    LONG_TERM_BORROWINGS = 'LONG_TERM_BORROWINGS', 'Long-Term Borrowings'
    DEFERRED_TAX_LIABILITY = 'DEFERRED_TAX_LIABILITY', 'Deferred Tax Liabilities (Net)'
    LONG_TERM_PROVISIONS = 'LONG_TERM_PROVISIONS', 'Long-Term Provisions'
    # Current Liabilities
    SHORT_TERM_BORROWINGS = 'SHORT_TERM_BORROWINGS', 'Short-Term Borrowings'
    TRADE_PAYABLES = 'TRADE_PAYABLES', 'Trade Payables'
    OTHER_CURRENT_LIABILITIES = 'OTHER_CURRENT_LIABILITIES', 'Other Current Liabilities'
    SHORT_TERM_PROVISIONS = 'SHORT_TERM_PROVISIONS', 'Short-Term Provisions'
    # Statement of Profit and Loss
    REVENUE_OPERATIONS = 'REVENUE_OPERATIONS', 'Revenue from Operations'
    OTHER_INCOME = 'OTHER_INCOME', 'Other Income'
    COST_OF_MATERIALS = 'COST_OF_MATERIALS', 'Cost of Materials Consumed'
    EMPLOYEE_BENEFITS = 'EMPLOYEE_BENEFITS', 'Employee Benefits Expense'
    FINANCE_COSTS = 'FINANCE_COSTS', 'Finance Costs'
    DEPRECIATION_AMORT = 'DEPRECIATION_AMORT', 'Depreciation and Amortization Expense'
    OTHER_EXPENSES = 'OTHER_EXPENSES', 'Other Expenses'
    UNCLASSIFIED = 'UNCLASSIFIED', 'Unclassified / Suspense Account'

class ChartOfAccounts(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='coa_accounts')
    account_code = models.CharField(max_length=50)
    account_name = models.CharField(max_length=255)
    account_type = models.CharField(max_length=20, choices=AccountType.choices)
    schedule_iii_group = models.CharField(max_length=50, choices=ScheduleIIIGroup.choices, default=ScheduleIIIGroup.UNCLASSIFIED)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('company', 'account_code')
        ordering = ['account_code']

    def __str__(self):
        return f"{self.account_code} - {self.account_name} ({self.schedule_iii_group})"

class LedgerAccount(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='ledger_accounts')
    coa = models.ForeignKey(ChartOfAccounts, on_delete=models.SET_NULL, null=True, blank=True, related_name='ledger_accounts')
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, blank=True)
    opening_balance = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    opening_balance_type = models.CharField(max_length=2, choices=[('Dr', 'Debit'), ('Cr', 'Credit')], default='Dr')
    closing_balance = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    closing_balance_type = models.CharField(max_length=2, choices=[('Dr', 'Debit'), ('Cr', 'Credit')], default='Dr')
    adjusted_balance = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    adjusted_balance_type = models.CharField(max_length=2, choices=[('Dr', 'Debit'), ('Cr', 'Credit')], default='Dr')
    is_suspense = models.BooleanField(default=False)
    is_reconciled = models.BooleanField(default=False)
    schedule_iii_division = models.CharField(max_length=30, default='DIVISION_I')
    mapping_status = models.CharField(
        max_length=30,
        choices=[
            ('MAPPED', 'Mapped'),
            ('UNMAPPED', 'Unmapped'),
            ('REVIEW_REQUIRED', 'Review Required'),
            ('APPROVED', 'Approved by Auditor')
        ],
        default='MAPPED'
    )
    mapping_notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('company', 'name')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} (Closing: {self.closing_balance} {self.closing_balance_type})"

class VoucherType(models.TextChoices):
    PAYMENT = 'PAYMENT', 'Payment Voucher'
    RECEIPT = 'RECEIPT', 'Receipt Voucher'
    JOURNAL = 'JOURNAL', 'Journal Entry'
    CONTRA = 'CONTRA', 'Contra (Cash/Bank Transfer)'
    SALES = 'SALES', 'Sales Voucher'
    PURCHASE = 'PURCHASE', 'Purchase Voucher'
    CREDIT_NOTE = 'CREDIT_NOTE', 'Credit Note'
    DEBIT_NOTE = 'DEBIT_NOTE', 'Debit Note'

class Transaction(models.Model):
    engagement = models.ForeignKey(Engagement, on_delete=models.CASCADE, related_name='transactions')
    document = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    ledger_account = models.ForeignKey(LedgerAccount, on_delete=models.CASCADE, related_name='transactions')
    voucher_number = models.CharField(max_length=100, db_index=True)
    voucher_type = models.CharField(max_length=30, choices=VoucherType.choices, default=VoucherType.JOURNAL)
    date = models.DateField(db_index=True)
    counterparty = models.CharField(max_length=255, blank=True)
    narration = models.TextField(blank=True)
    debit_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    credit_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(max_length=10, default='INR')
    source_reference = models.CharField(max_length=255, blank=True, help_text="e.g. Sheet1:Row15")
    
    # Audit scrutiny flags
    is_unusual = models.BooleanField(default=False)
    risk_flags = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'voucher_number']

    def __str__(self):
        return f"{self.date} | Vch {self.voucher_number} | {self.ledger_account.name} | Dr: {self.debit_amount} Cr: {self.credit_amount}"

class TrialBalanceSnapshot(models.Model):
    engagement = models.ForeignKey(Engagement, on_delete=models.CASCADE, related_name='trial_balances')
    document = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True, related_name='trial_balances')
    as_of_date = models.DateField()
    total_debits = models.DecimalField(max_digits=18, decimal_places=2)
    total_credits = models.DecimalField(max_digits=18, decimal_places=2)
    difference_amount = models.DecimalField(max_digits=18, decimal_places=2)
    is_balanced = models.BooleanField(default=False)
    status = models.CharField(max_length=30, default='BALANCED')
    accounts_snapshot = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.engagement.company.name} TB as of {self.as_of_date} (Diff: ₹{self.difference_amount})"
