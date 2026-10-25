from django.db import models
from decimal import Decimal
from apps.companies.models import Engagement
from apps.accounting.models import Transaction, LedgerAccount

class ProcedureCategory(models.TextChoices):
    COMPLETENESS = 'COMPLETENESS', 'Completeness Procedures'
    ACCURACY = 'ACCURACY', 'Accuracy & Mathematical Valuation'
    CUT_OFF = 'CUT_OFF', 'Cut-off & Periodicity Testing'
    CLASSIFICATION = 'CLASSIFICATION', 'Classification & Presentation'
    ANALYTICAL = 'ANALYTICAL', 'Substantive Analytical Review'
    TAX_AUDIT_3CD = 'TAX_AUDIT_3CD', 'Tax Audit Form 3CD Scrutiny'
    CARO_2020 = 'CARO_2020', 'CARO 2020 Compliance Order'
    STATUTORY_DUES = 'STATUTORY_DUES', 'Statutory Dues & Compliance (GST, TDS, PF, ESI)'

class ProcedureStatus(models.TextChoices):
    NOT_STARTED = 'NOT_STARTED', 'Not Started'
    RUNNING = 'RUNNING', 'Running Procedure'
    PASSED_NO_EXCEPTIONS = 'PASSED_NO_EXCEPTIONS', 'Completed - No Exceptions Detected'
    PASSED_WITH_EXCEPTIONS = 'PASSED_WITH_EXCEPTIONS', 'Completed - Exceptions Detected'
    BLOCKED = 'BLOCKED', 'Blocked (Prerequisites Missing)'
    REVIEW_REQUIRED = 'REVIEW_REQUIRED', 'Review Required by CA'

class AuditProcedure(models.Model):
    code = models.CharField(max_length=50, unique=True, help_text="e.g. PROC-CUTOFF-01, CARO-CLAUSE-1, TAX-3CD-21")
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=50, choices=ProcedureCategory.choices)
    audit_objective = models.TextField()
    applicable_standard = models.CharField(max_length=100, default='SA 500 Audit Evidence')
    rule_version = models.CharField(max_length=20, default='FY24-25.v1')
    execution_logic_name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code}: {self.title}"

class ProcedureExecution(models.Model):
    engagement = models.ForeignKey(Engagement, on_delete=models.CASCADE, related_name='procedure_executions')
    procedure = models.ForeignKey(AuditProcedure, on_delete=models.CASCADE, related_name='executions')
    status = models.CharField(max_length=40, choices=ProcedureStatus.choices, default=ProcedureStatus.NOT_STARTED)
    tested_records_count = models.IntegerField(default=0)
    exceptions_count = models.IntegerField(default=0)
    summary_findings = models.TextField(blank=True)
    evidence_reference = models.CharField(max_length=255, blank=True)
    results_payload = models.JSONField(default=dict, blank=True)
    executed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('engagement', 'procedure')
        ordering = ['procedure__code']

    def __str__(self):
        return f"{self.engagement.company.name} - {self.procedure.code}: {self.status}"

class ExceptionSeverity(models.TextChoices):
    CRITICAL = 'CRITICAL', 'Critical Statutory Non-Compliance'
    HIGH = 'HIGH', 'High Material Audit Risk'
    MEDIUM = 'MEDIUM', 'Medium Inconsistency'
    LOW = 'LOW', 'Low / Procedural Observation'

class ExceptionStatus(models.TextChoices):
    OPEN = 'OPEN', 'Open Exception'
    AJE_PROPOSED = 'AJE_PROPOSED', 'AJE Proposed (Pending Review)'
    IN_REVIEW = 'IN_REVIEW', 'Under CA Review'
    EVIDENCE_REQUESTED = 'EVIDENCE_REQUESTED', 'Evidence Requested from Client'
    RESOLVED = 'RESOLVED', 'Resolved & Satisfactory'
    AJE_POSTED = 'AJE_POSTED', 'AJE Posted to Books (Resolved)'
    ACCEPTED_RISK = 'ACCEPTED_RISK', 'Immaterial / Risk Accepted with Note'

class AuditAssertion(models.TextChoices):
    COMPLETENESS = 'COMPLETENESS', 'Completeness'
    EXISTENCE = 'EXISTENCE', 'Existence & Occurrence'
    ACCURACY = 'ACCURACY', 'Accuracy & Valuation'
    CUT_OFF = 'CUT_OFF', 'Cut-off & Periodicity'
    RIGHTS_OBLIGATIONS = 'RIGHTS_OBLIGATIONS', 'Rights & Obligations'
    PRESENTATION = 'PRESENTATION', 'Presentation & Disclosure'

class ExceptionItem(models.Model):
    engagement = models.ForeignKey(Engagement, on_delete=models.CASCADE, related_name='exceptions')
    procedure_execution = models.ForeignKey(ProcedureExecution, on_delete=models.SET_NULL, null=True, blank=True, related_name='exceptions')
    related_transaction = models.ForeignKey(Transaction, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_exceptions')
    related_ledger = models.ForeignKey(LedgerAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_exceptions')
    
    finding_reference = models.CharField(max_length=50, blank=True, help_text="Structured finding identifier e.g. EXC-001")
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=50)
    rule_code = models.CharField(max_length=100, blank=True, help_text="e.g. RULE_TB_UNBALANCED, RULE_DUPLICATE_TXN")
    severity = models.CharField(max_length=20, choices=ExceptionSeverity.choices, default=ExceptionSeverity.HIGH)
    assertion = models.CharField(max_length=30, choices=AuditAssertion.choices, default=AuditAssertion.ACCURACY)
    status = models.CharField(max_length=30, choices=ExceptionStatus.choices, default=ExceptionStatus.OPEN)
    
    amount_involved = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    explanation = models.TextField()
    recommended_action = models.TextField()
    management_response = models.TextField(blank=True, help_text="Client auditee representation or explanation")
    resolution_notes = models.TextField(blank=True)
    resolution_history = models.JSONField(default=list, blank=True)
    source_reference = models.CharField(max_length=255, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-severity', '-created_at']

    def __str__(self):
        return f"[{self.severity}] {self.title} (₹{self.amount_involved}) - {self.status}"

class FixedAsset(models.Model):
    engagement = models.ForeignKey(Engagement, on_delete=models.CASCADE, related_name='fixed_assets')
    asset_id = models.CharField(max_length=100)
    asset_name = models.CharField(max_length=255)
    category = models.CharField(max_length=100, default='Plant & Machinery')
    acquisition_date = models.DateField()
    put_to_use_date = models.DateField(null=True, blank=True)
    original_cost = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    useful_life_years = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('5.00'))
    residual_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('5.00'))
    
    # Dual Depreciation
    sch_ii_depreciation = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    sec_32_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('15.00'))
    sec_32_depreciation = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    
    # Asset-Wise Booked Depreciation & Variance
    booked_depreciation = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'), help_text="Depreciation booked per asset in client FAR / books")
    depreciation_variance = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'), help_text="Variance: Schedule II recalculation vs Booked depreciation")
    
    accumulated_depreciation = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    carrying_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    location = models.CharField(max_length=255, blank=True)
    is_duplicate_candidate = models.BooleanField(default=False)
    source_reference = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['asset_id']

    def __str__(self):
        return f"{self.asset_id} - {self.asset_name} (₹{self.original_cost})"

class SubledgerAgingItem(models.Model):
    engagement = models.ForeignKey(Engagement, on_delete=models.CASCADE, related_name='aging_items')
    item_type = models.CharField(max_length=20, choices=[('RECEIVABLE', 'Trade Receivable'), ('PAYABLE', 'Trade Payable')])
    party_name = models.CharField(max_length=255)
    party_pan = models.CharField(max_length=20, blank=True)
    party_gstin = models.CharField(max_length=20, blank=True)
    is_msme = models.BooleanField(default=False)
    msme_type = models.CharField(max_length=20, choices=[('MICRO', 'Micro'), ('SMALL', 'Small'), ('MEDIUM', 'Medium'), ('NON_MSME', 'Non-MSME')], default='NON_MSME')
    
    invoice_number = models.CharField(max_length=100)
    invoice_date = models.DateField()
    due_date = models.DateField()
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    outstanding_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    
    ageing_days = models.IntegerField(default=0)
    ageing_bucket = models.CharField(max_length=30, default='0-30 days')
    is_disputed = models.BooleanField(default=False)
    
    # MSMED Act 2006 & Section 43B(h) compliance
    is_overdue_43bh = models.BooleanField(default=False)
    overdue_days_msme = models.IntegerField(default=0)
    source_reference = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-outstanding_amount']

    def __str__(self):
        return f"[{self.item_type}] {self.party_name} - {self.invoice_number}: ₹{self.outstanding_amount}"

class RelatedParty(models.Model):
    engagement = models.ForeignKey(Engagement, on_delete=models.CASCADE, related_name='related_parties')
    party_name = models.CharField(max_length=255)
    pan = models.CharField(max_length=20, blank=True)
    relationship_type = models.CharField(max_length=100, help_text="Director, KMP, Subsidiary, Relative under Sec 2(76)")
    applicable_standard = models.CharField(max_length=50, default='SECTION_2_76')
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.party_name} ({self.relationship_type})"

class StatutoryClauseAudit(models.Model):
    engagement = models.ForeignKey(Engagement, on_delete=models.CASCADE, related_name='clause_audits')
    form_type = models.CharField(max_length=20, choices=[('FORM_3CD', 'Tax Audit Form 3CD'), ('CARO_2020', 'CARO 2020 Order'), ('FORM_3CA', 'Form 3CA'), ('FORM_3CB', 'Form 3CB')])
    clause_number = models.CharField(max_length=50, help_text="e.g. Clause 21(d), Clause 3(i)")
    clause_title = models.CharField(max_length=255)
    is_applicable = models.BooleanField(default=True)
    calculated_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    evidence_status = models.CharField(
        max_length=30,
        choices=[
            ('AVAILABLE', 'Evidence Verified'),
            ('PARTIAL', 'Partial / Review Required'),
            ('PENDING_DOCS', 'Pending Documentation'),
            ('MISSING', 'Missing / Blocked')
        ],
        default='AVAILABLE'
    )
    compliance_status = models.CharField(
        max_length=30,
        choices=[
            ('COMPLIANT', 'Compliant - Verified Orderly'),
            ('CLEARED', 'Cleared - Nil Violations'),
            ('VERIFIED', 'Verified - Records Checked'),
            ('REPORTED', 'Reported - Schedule Annexed'),
            ('REVIEW_REQUIRED', 'Review Required - Pending Review'),
            ('EXCEPTION_NOTED', 'Non-Compliance / Exception Noted'),
            ('NON_COMPLIANT', 'Non-Compliant - Disallowed'),
            ('EXEMPT', 'Exempt / Not Applicable')
        ],
        default='COMPLIANT'
    )
    auditor_remarks = models.TextField(blank=True)
    statutory_citation = models.CharField(max_length=255, blank=True)
    rule_version = models.CharField(max_length=50, default='FY2024-25.v1')
    verified_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('engagement', 'form_type', 'clause_number')
        ordering = ['form_type', 'clause_number']

    def __str__(self):
        return f"{self.form_type} {self.clause_number}: {self.compliance_status}"

