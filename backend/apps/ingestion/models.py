import hashlib
from django.db import models
from django.contrib.auth.models import User
from apps.companies.models import Engagement

class DocumentType(models.TextChoices):
    TRIAL_BALANCE = 'TRIAL_BALANCE', 'Trial Balance'
    GENERAL_LEDGER = 'GENERAL_LEDGER', 'General Ledger'
    BANK_STATEMENT = 'BANK_STATEMENT', 'Bank Statement'
    GSTR_2B = 'GSTR_2B', 'GSTR-2B (Input Tax Credit)'
    SALES_REGISTER = 'SALES_REGISTER', 'Sales Register'
    PURCHASE_REGISTER = 'PURCHASE_REGISTER', 'Purchase Register'
    FIXED_ASSET_REGISTER = 'FIXED_ASSET_REGISTER', 'Fixed Asset Register'
    SUBLEDGER_AGING = 'SUBLEDGER_AGING', 'Subledger / Aging Schedule'
    INVOICE_VOUCHER = 'INVOICE_VOUCHER', 'Invoice / Expense Voucher'
    UNKNOWN = 'UNKNOWN', 'Unclassified / Review Required'

class DocumentStatus(models.TextChoices):
    UPLOADED = 'UPLOADED', 'Uploaded'
    PROCESSING = 'PROCESSING', 'Processing'
    VERIFIED = 'VERIFIED', 'Verified & Ingested'
    REVIEW_REQUIRED = 'REVIEW_REQUIRED', 'Review Required (Ambiguous/Low Confidence)'
    FAILED = 'FAILED', 'Processing Failed'

class Document(models.Model):
    engagement = models.ForeignKey(Engagement, on_delete=models.CASCADE, related_name='documents')
    original_filename = models.CharField(max_length=255)
    file = models.FileField(upload_to='financial_docs/%Y/%m/')
    file_hash = models.CharField(max_length=64, db_index=True, help_text="SHA-256 Cryptographic Hash")
    file_size_bytes = models.BigIntegerField()
    mime_type = models.CharField(max_length=100)
    document_type = models.CharField(max_length=50, choices=DocumentType.choices, default=DocumentType.UNKNOWN)
    status = models.CharField(max_length=30, choices=DocumentStatus.choices, default=DocumentStatus.UPLOADED)
    extracted_summary = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.original_filename} ({self.document_type}) - {self.status}"

    @classmethod
    def calculate_sha256(cls, file_obj):
        hasher = hashlib.sha256()
        for chunk in file_obj.chunks():
            hasher.update(chunk)
        file_obj.seek(0)
        return hasher.hexdigest()

class ProcessingJob(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='jobs')
    stage = models.CharField(max_length=50, default='INITIALIZED')
    progress_percent = models.IntegerField(default=0)
    total_records = models.IntegerField(default=0)
    valid_records = models.IntegerField(default=0)
    review_records = models.IntegerField(default=0)
    failed_records = models.IntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    logs = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['-started_at']

class ExtractedRecord(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='extracted_records')
    row_index = models.IntegerField()
    source_location = models.CharField(max_length=100, help_text="e.g. Sheet1:Row12 or Page2:Table1:Row5")
    raw_data = models.JSONField(default=dict)
    normalized_data = models.JSONField(default=dict)
    validation_status = models.CharField(max_length=30, default='VALID', help_text="VALID, REVIEW_REQUIRED, INVALID")
    validation_notes = models.TextField(blank=True)
    confidence_score = models.DecimalField(max_digits=4, decimal_places=2, default=1.00)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['document', 'row_index']


class ProcessingRunStage(models.TextChoices):
    UPLOAD_RECEIVED = 'UPLOAD_RECEIVED', '1. Upload Received'
    FILE_VALIDATION = 'FILE_VALIDATION', '2. File Validation & Hashing'
    DOCUMENT_CLASSIFICATION = 'DOCUMENT_CLASSIFICATION', '3. Document Classification'
    DATA_EXTRACTION = 'DATA_EXTRACTION', '4. Data Extraction'
    DATA_VALIDATION = 'DATA_VALIDATION', '5. Data Validation'
    ACCOUNT_NORMALIZATION = 'ACCOUNT_NORMALIZATION', '6. Account Normalization'
    ACCOUNTING_CALCULATIONS = 'ACCOUNTING_CALCULATIONS', '7. Accounting Calculations'
    RECONCILIATION = 'RECONCILIATION', '8. Reconciliation Suite'
    AUDIT_PROCEDURES = 'AUDIT_PROCEDURES', '9. Audit Procedures'
    EXCEPTION_GENERATION = 'EXCEPTION_GENERATION', '10. Exception Generation'
    WORKPAPER_GENERATION = 'WORKPAPER_GENERATION', '11. Workpaper Generation'
    REPORT_ASSEMBLY = 'REPORT_ASSEMBLY', '12. Report Assembly'
    OUTPUT_VALIDATION = 'OUTPUT_VALIDATION', '13. Output Validation & Exports'
    COMPLETED = 'COMPLETED', '14. Completed'


class ProcessingRunStatus(models.TextChoices):
    QUEUED = 'QUEUED', 'Queued'
    RUNNING = 'RUNNING', 'Running'
    COMPLETED = 'COMPLETED', 'Completed'
    PARTIALLY_COMPLETED = 'PARTIALLY_COMPLETED', 'Partially Completed'
    AWAITING_CLARIFICATION = 'AWAITING_CLARIFICATION', 'Awaiting Clarification'
    REVIEW_REQUIRED = 'REVIEW_REQUIRED', 'Review Required'
    BLOCKED = 'BLOCKED', 'Blocked'
    FAILED = 'FAILED', 'Failed'
    CANCELLED = 'CANCELLED', 'Cancelled'


class ProcessingRun(models.Model):
    run_id = models.CharField(max_length=64, unique=True, db_index=True)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, null=True, blank=True, related_name='processing_runs')
    engagement = models.ForeignKey('companies.Engagement', on_delete=models.CASCADE, null=True, blank=True, related_name='processing_runs')
    
    status = models.CharField(max_length=40, choices=ProcessingRunStatus.choices, default=ProcessingRunStatus.QUEUED)
    current_stage = models.CharField(max_length=50, choices=ProcessingRunStage.choices, default=ProcessingRunStage.UPLOAD_RECEIVED)
    progress_percent = models.IntegerField(default=0)
    
    stage_statuses = models.JSONField(default=dict, blank=True)
    stage_logs = models.JSONField(default=list, blank=True)
    
    documents = models.ManyToManyField(Document, blank=True, related_name='processing_runs')
    generated_reports = models.ManyToManyField('reporting.GeneratedReport', blank=True, related_name='processing_runs')
    
    zip_package = models.FileField(upload_to='audit_packages/%Y/%m/', null=True, blank=True)
    zip_package_hash = models.CharField(max_length=64, blank=True)
    
    summary_metrics = models.JSONField(default=dict, blank=True)
    blockers = models.JSONField(default=list, blank=True)
    
    initiated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='initiated_runs')
    
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        comp_name = self.company.name if self.company else "Unassigned"
        return f"{self.run_id} - {comp_name} ({self.status})"
