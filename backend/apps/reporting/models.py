from django.db import models
from decimal import Decimal
from apps.companies.models import Engagement
from apps.core.models import User

class WorkpaperStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft Workpaper'
    PREPARED = 'PREPARED', 'Prepared by Audit Team'
    READY_FOR_REVIEW = 'READY_FOR_REVIEW', 'Ready for Senior/Manager Review'
    REVIEW_REQUIRED = 'REVIEW_REQUIRED', 'Review Required (Action Needed)'
    RETURNED_FOR_CORRECTION = 'RETURNED_FOR_CORRECTION', 'Returned for Correction'
    REVIEWED = 'REVIEWED', 'Reviewed with Notes'
    APPROVED = 'APPROVED', 'Partner Approved'
    PARTNER_AUTHORIZED = 'PARTNER_AUTHORIZED', 'Partner Authorized'
    REJECTED = 'REJECTED', 'Rejected'

class Workpaper(models.Model):
    engagement = models.ForeignKey(Engagement, on_delete=models.CASCADE, related_name='workpapers')
    wp_reference = models.CharField(max_length=50, help_text="e.g. WP-A101 Cash & Bank, WP-B201 Revenue")
    title = models.CharField(max_length=255)
    audit_area = models.CharField(max_length=100)
    audit_objective = models.TextField()
    scope_and_coverage = models.TextField()
    testing_methodology = models.TextField()
    results_summary = models.TextField()
    exceptions_noted = models.TextField(blank=True)
    proposed_conclusion = models.TextField()
    status = models.CharField(max_length=35, choices=WorkpaperStatus.choices, default=WorkpaperStatus.DRAFT)
    
    # Review & Governance
    preparer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='prepared_workpapers')
    reviewer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_workpapers')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='signed_off_workpapers')
    
    review_comments = models.TextField(blank=True)
    review_notes = models.TextField(blank=True)
    return_reason = models.TextField(blank=True)
    approval_reason = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    
    evidence_verified = models.BooleanField(default=False)
    evidence_reference = models.CharField(max_length=255, blank=True)
    review_required = models.BooleanField(default=False)
    
    version = models.IntegerField(default=1)
    version_history = models.JSONField(default=list, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('engagement', 'wp_reference')
        ordering = ['wp_reference']

    def __str__(self):
        return f"{self.wp_reference}: {self.title} ({self.status})"

class AdjustmentStatus(models.TextChoices):
    PROPOSED = 'PROPOSED', 'Proposed Adjustment'
    ACCEPTED_BY_MANAGEMENT = 'ACCEPTED_BY_MANAGEMENT', 'Accepted by Management'
    APPROVED_BY_PARTNER = 'APPROVED_BY_PARTNER', 'Approved by Senior CA Partner'
    POSTED = 'POSTED', 'Posted to General Ledger (Executed)'
    UNADJUSTED_PASSED = 'UNADJUSTED_PASSED', 'Unadjusted / Passed (Immaterial)'
    REJECTED = 'REJECTED', 'Rejected'

class ProposedAdjustment(models.Model):
    engagement = models.ForeignKey(Engagement, on_delete=models.CASCADE, related_name='adjustments')
    adjustment_number = models.CharField(max_length=50, help_text="e.g. AJE-01, AJE-02")
    title = models.CharField(max_length=255)
    reason = models.TextField()
    
    # Balancing Journal Entry details: list of dicts [{'account': 'Office Expenses', 'debit': 15000, 'credit': 0}, ...]
    journal_entries = models.JSONField(default=list)
    total_debit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    total_credit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    is_balanced = models.BooleanField(default=True)
    
    pnl_impact = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'), help_text="Impact on Net Profit (+/-)")
    status = models.CharField(max_length=30, choices=AdjustmentStatus.choices, default=AdjustmentStatus.PROPOSED)
    is_posted = models.BooleanField(default=False)
    posted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['adjustment_number']

    def __str__(self):
        return f"{self.adjustment_number}: {self.title} (₹{self.total_debit})"

class ReportType(models.TextChoices):
    CONSOLIDATED_AUDIT_REPORT = 'CONSOLIDATED_AUDIT_REPORT', 'Consolidated Financial & Audit Analysis Report'
    DOCUMENT_PROCESSING_REPORT = 'DOCUMENT_PROCESSING_REPORT', 'Document Upload & Processing Report'
    AUDIT_SUMMARY = 'AUDIT_SUMMARY', 'Audit Summary & Exceptions Report'
    BRS_REPORT = 'BRS_REPORT', 'Bank Reconciliation & Clearance Report'
    GSTR2B_RECON = 'GSTR2B_RECON', 'GST ITC Reconciled Report'
    TAX_AUDIT_3CD = 'TAX_AUDIT_3CD', 'Tax Audit Form 3CD Schedule'
    CARO_2020 = 'CARO_2020', 'CARO 2020 Compliance Matrix'
    TRIAL_BALANCE_REPORT = 'TRIAL_BALANCE_REPORT', 'Trial Balance & Movement Schedule'
    EXCEPTIONS_REPORT = 'EXCEPTIONS_REPORT', 'Audit Exceptions & Risk Register'

class GeneratedReport(models.Model):
    engagement = models.ForeignKey(Engagement, on_delete=models.CASCADE, related_name='reports')
    report_type = models.CharField(max_length=60, choices=ReportType.choices, default=ReportType.CONSOLIDATED_AUDIT_REPORT)
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='reports/%Y/%m/', null=True, blank=True)
    file_format = models.CharField(max_length=15, default='PDF', help_text="PDF, EXCEL, CSV, JSON")
    summary_data = models.JSONField(default=dict, blank=True)
    is_stale = models.BooleanField(default=False)
    source_checksum = models.CharField(max_length=64, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        return f"{self.report_type} - {self.engagement.company.name} ({self.generated_at.strftime('%Y-%m-%d')})"
