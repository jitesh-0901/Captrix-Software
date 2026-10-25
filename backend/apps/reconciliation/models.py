from django.db import models
from decimal import Decimal
from apps.companies.models import Engagement
from apps.ingestion.models import Document

class ReconciliationType(models.TextChoices):
    BANK = 'BANK', 'Bank Reconciliation (BRS)'
    GST_ITC = 'GST_ITC', 'GST ITC (GSTR-2B vs Purchase Register)'
    LEDGER_TB = 'LEDGER_TB', 'General Ledger vs Trial Balance'
    SALES_VS_LEDGER = 'SALES_VS_LEDGER', 'Sales Register vs Revenue Ledgers'
    PURCHASE_VS_LEDGER = 'PURCHASE_VS_LEDGER', 'Purchase Register vs Expense Ledgers'
    AR_VS_CONTROL = 'AR_VS_CONTROL', 'Debtors Ageing vs Trade Receivables Control'
    AP_VS_CONTROL = 'AP_VS_CONTROL', 'Creditors Ageing vs Trade Payables Control'
    FAR_VS_LEDGER = 'FAR_VS_LEDGER', 'Fixed Asset Register vs PPE Ledgers'
    FS_VS_TB = 'FS_VS_TB', 'Financial Statements vs Trial Balance'
    GSTR1_VS_BOOKS = 'GSTR1_VS_BOOKS', 'GSTR-1 Outward Supplies vs Books'
    GSTR3B_VS_BOOKS = 'GSTR3B_VS_BOOKS', 'GSTR-3B Summary Return vs Books'
    TDS_26AS = 'TDS_26AS', 'Form 26AS / AIS TDS Credits vs Books'


class ReconciliationStatus(models.TextChoices):
    IN_PROGRESS = 'IN_PROGRESS', 'Reconciliation In Progress'
    MATCHED = 'MATCHED', 'Reconciled with Timing Differences'
    BALANCED = 'BALANCED', 'Zero Variance Reconciled'
    REVIEW_REQUIRED = 'REVIEW_REQUIRED', 'Review Required (Unmatched / Ambiguous Items)'
    BLOCKED = 'BLOCKED', 'Blocked (Prerequisite Documents Missing)'
    VARIANCE_DETECTED = 'VARIANCE_DETECTED', 'Material Variance Detected'

class MatchType(models.TextChoices):
    EXACT = 'EXACT', 'Exact Match (Amount, Date & Reference)'
    RULE_BASED = 'RULE_BASED', 'Rule-Based Match (Amount & Value Date within window)'
    ONE_TO_MANY = 'ONE_TO_MANY', 'One-to-Many Consolidated Match'
    MANY_TO_ONE = 'MANY_TO_ONE', 'Many-to-One Consolidated Match'
    SUGGESTED = 'SUGGESTED', 'Suggested Match (Amount Match, Narrative Similarity)'
    MANUAL = 'MANUAL', 'Auditor Manual Match'

class ReconciliationRun(models.Model):
    engagement = models.ForeignKey(Engagement, on_delete=models.CASCADE, related_name='reconciliation_runs')
    recon_type = models.CharField(max_length=40, choices=ReconciliationType.choices, default=ReconciliationType.BANK)
    status = models.CharField(max_length=30, choices=ReconciliationStatus.choices, default=ReconciliationStatus.IN_PROGRESS)
    as_of_date = models.DateField()
    date_tolerance_days = models.IntegerField(default=15)
    
    # Financial reconciliation summary figures
    balance_per_books = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    balance_per_statement = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    timing_differences_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    unreconciled_difference = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    
    total_source_items = models.IntegerField(default=0)
    total_target_items = models.IntegerField(default=0)
    matched_count = models.IntegerField(default=0)
    unmatched_count = models.IntegerField(default=0)
    unresolved_count = models.IntegerField(default=0)
    
    summary_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.engagement.company.name} - {self.recon_type} as of {self.as_of_date} (Diff: ₹{self.unreconciled_difference})"

class ReconciliationItem(models.Model):
    reconciliation_run = models.ForeignKey(ReconciliationRun, on_delete=models.CASCADE, related_name='items')
    source_type = models.CharField(max_length=50, help_text="BANK_STATEMENT, CASHBOOK, GSTR_2B, PURCHASE_REGISTER")
    item_date = models.DateField()
    reference_number = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    party_name = models.CharField(max_length=255, blank=True)
    debit_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    credit_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    
    is_matched = models.BooleanField(default=False)
    matched_with_id = models.IntegerField(null=True, blank=True)
    match_type = models.CharField(max_length=30, choices=MatchType.choices, blank=True)
    timing_category = models.CharField(max_length=100, blank=True, help_text="e.g. CHEQUE_ISSUED_NOT_PRESENTED, CHEQUE_DEPOSITED_NOT_CLEARED")
    match_notes = models.TextField(blank=True)
    is_approved = models.BooleanField(default=False)
    raw_source_ref = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['item_date', 'id']

    def __str__(self):
        return f"{self.source_type} [{self.item_date}] {self.description[:30]} - ₹{self.amount} ({'Matched' if self.is_matched else 'Unmatched'})"
