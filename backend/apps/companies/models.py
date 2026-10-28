from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal

class EntityType(models.TextChoices):
    PVT_LTD = 'PVT_LTD', 'Private Limited Company'
    PUB_LTD = 'PUB_LTD', 'Public Limited Company'
    LLP = 'LLP', 'Limited Liability Partnership'
    PARTNERSHIP = 'PARTNERSHIP', 'Partnership Firm'
    PROPRIETORSHIP = 'PROPRIETORSHIP', 'Sole Proprietorship'

class BusinessTier(models.TextChoices):
    TIER_1_SMALL = 'TIER_1_SMALL', 'Tier 1 — Small Business / Sole Proprietorship'
    TIER_2_SME = 'TIER_2_SME', 'Tier 2 — SME / Growing Firm / LLP'
    TIER_3_MID = 'TIER_3_MID', 'Tier 3 — Mid-Market Private Limited'
    TIER_4_ENTERPRISE = 'TIER_4_ENTERPRISE', 'Tier 4 — Large Enterprise / Multi-Branch'

class Company(models.Model):
    name = models.CharField(max_length=255)
    cin = models.CharField(max_length=25, blank=True, help_text="Corporate Identification Number (e.g., U72200MH2018PTC123456)")
    pan = models.CharField(max_length=15, blank=True, help_text="Permanent Account Number (10 characters)")
    gstin = models.CharField(max_length=20, blank=True, help_text="Goods and Services Tax Identification Number (15 chars)")
    entity_type = models.CharField(max_length=30, choices=EntityType.choices, default=EntityType.PVT_LTD)
    business_tier = models.CharField(max_length=30, choices=BusinessTier.choices, default=BusinessTier.TIER_3_MID)
    parent_company = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='branches_or_subsidiaries', help_text="Parent company for multi-branch or holding group hierarchy")
    branch_name = models.CharField(max_length=150, blank=True, default='Head Office')
    branch_code = models.CharField(max_length=50, blank=True)
    registered_address = models.TextField(blank=True)
    industry = models.CharField(max_length=100, default='Information Technology & Services')
    incorporation_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Companies'

    def __str__(self):
        return f"{self.name} ({self.pan or 'No PAN'})"

class FinancialYear(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='financial_years')
    label = models.CharField(max_length=20, help_text="e.g. FY 2024-25")
    start_date = models.DateField(help_text="Standard Indian FY starts April 1")
    end_date = models.DateField(help_text="Standard Indian FY ends March 31")
    is_active = models.BooleanField(default=True)
    is_closed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('company', 'label')
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.company.name} - {self.label}"

class EngagementType(models.TextChoices):
    STATUTORY = 'STATUTORY', 'Statutory Audit (Companies Act 2013)'
    TAX_AUDIT = 'TAX_AUDIT', 'Tax Audit (Section 44AB Form 3CD)'
    INTERNAL = 'INTERNAL', 'Internal Audit'
    BANK_AUDIT = 'BANK_AUDIT', 'Concurrent / Statutory Bank Audit'
    STOCK_AUDIT = 'STOCK_AUDIT', 'Stock & Receivables Audit'
    LLP_AUDIT = 'LLP_AUDIT', 'LLP Statutory Audit (LLP Act 2008)'
    BRS_REVIEW = 'BRS_REVIEW', 'Bank Reconciliation & Scrutiny Review'
    GST_AUDIT = 'GST_AUDIT', 'GST Compliance & ITC Audit'

class EngagementStatus(models.TextChoices):
    PLANNING = 'PLANNING', 'Planning & Risk Assessment'
    FIELDWORK = 'FIELDWORK', 'Substantive Testing & Fieldwork'
    REVIEW = 'REVIEW', 'Senior / Partner Review'
    COMPLETED = 'COMPLETED', 'Audit Finalized & Approved'
    ARCHIVED = 'ARCHIVED', 'Archived'

class Engagement(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='engagements')
    financial_year = models.ForeignKey(FinancialYear, on_delete=models.CASCADE, related_name='engagements')
    title = models.CharField(max_length=255)
    engagement_type = models.CharField(max_length=30, choices=EngagementType.choices, default=EngagementType.STATUTORY)
    status = models.CharField(max_length=30, choices=EngagementStatus.choices, default=EngagementStatus.PLANNING)
    
    # Materiality Settings (Standards on Auditing SA 320)
    materiality_benchmark = models.CharField(max_length=50, default='PBT', help_text="Benchmark: PBT, Revenue, or Total Assets")
    benchmark_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('5.00'), help_text="e.g. 5.0% of PBT or 0.5% of Revenue")
    overall_materiality = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('500000.00'))
    performance_materiality = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('375000.00')) # Usually 75%
    clearly_trivial_threshold = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('25000.00')) # Usually 5%
    
    lead_partner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='partner_engagements')
    audit_manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='manager_engagements')
    
    notes = models.TextField(blank=True)
    
    # Engagement Completion Controls
    is_finalized = models.BooleanField(default=False)
    finalized_at = models.DateTimeField(null=True, blank=True)
    finalized_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='finalized_engagements')
    udin = models.CharField(max_length=50, blank=True, default='', help_text="Official 18-character ICAI Unique Document Identification Number")
    finalization_metadata = models.JSONField(default=dict, blank=True, help_text="Persisted CA partner certification metadata (CA Name, Membership No, FRN, UDIN, Signing Date/Place)")
    permitted_exceptions = models.JSONField(default=list, blank=True, help_text="Documented authorized exceptions with justification and audit trail")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.company.name} - {self.title} ({self.financial_year.label})"

class EngagementWorkflowConfig(models.Model):
    engagement = models.OneToOneField(Engagement, on_delete=models.CASCADE, related_name='workflow_config')
    scope_description = models.TextField(blank=True)
    applicable_framework = models.CharField(max_length=100, default='COMPANIES_ACT_2013')
    caro_applicable = models.BooleanField(default=True)
    form_3cd_applicable = models.BooleanField(default=True)
    form_type = models.CharField(max_length=20, default='3CA', help_text="3CA, 3CB, or NONE")
    msmed_applicable = models.BooleanField(default=True)
    schedule_iii_division = models.CharField(max_length=30, default='DIVISION_I', help_text="DIVISION_I, DIVISION_II, or NOT_APPLICABLE")
    
    # Checklists and Milestones
    required_documents = models.JSONField(default=list, blank=True)
    milestones = models.JSONField(default=dict, blank=True)
    completion_criteria = models.JSONField(default=dict, blank=True)
    completion_status = models.CharField(max_length=40, default='IN_PROGRESS')
    
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_document_matrix_for(cls, entity_type=EntityType.PVT_LTD, business_tier=BusinessTier.TIER_3_MID, engagement_type=EngagementType.STATUTORY):
        """
        Dynamically calculates the tailored document requirement matrix based on
        the company scale tier, statutory entity form, and engagement scope.
        """
        docs = [
            {'title': 'Signed Trial Balance', 'category': 'CORE_TB', 'mandatory': True, 'description': 'Closing Trial Balance with account codes and opening/closing balances.'},
            {'title': 'General Ledger Dump', 'category': 'CORE_GL', 'mandatory': True, 'description': 'Full detailed transaction-level journal and ledger dumps.'},
            {'title': 'Bank Statements & BRS', 'category': 'BANK', 'mandatory': True, 'description': 'Monthly bank account statements and bank reconciliation statements.'},
        ]

        if engagement_type in [EngagementType.STATUTORY, EngagementType.TAX_AUDIT] or business_tier in [BusinessTier.TIER_3_MID, BusinessTier.TIER_4_ENTERPRISE]:
            docs.extend([
                {'title': 'Fixed Asset Register (FAR)', 'category': 'ASSETS', 'mandatory': True, 'description': 'Asset register with purchase dates, rates, and dual depreciation.'},
                {'title': 'Sundry Debtors Ageing Schedule', 'category': 'RECEIVABLES', 'mandatory': True, 'description': 'Ageing breakdown under Schedule III (<6M, 6M-1Y, 1-2Y, 2-3Y, >3Y).'},
                {'title': 'Sundry Creditors & MSME Classification', 'category': 'PAYABLES', 'mandatory': True, 'description': 'Payables breakdown with MSME status and Section 43B(h) due dates.'},
                {'title': 'Statutory Dues Challans (GST, TDS, PF, ESI)', 'category': 'STATUTORY_DUES', 'mandatory': True, 'description': 'Payment challans and return filings for statutory liabilities.'},
            ])

        if engagement_type in [EngagementType.STATUTORY] and business_tier in [BusinessTier.TIER_2_SME, BusinessTier.TIER_3_MID, BusinessTier.TIER_4_ENTERPRISE]:
            docs.append({'title': 'Inventory Valuation & Stock Sheets', 'category': 'INVENTORY', 'mandatory': False, 'description': 'Physical count sheets and lower of cost or NRV valuation.'})

        if business_tier == BusinessTier.TIER_4_ENTERPRISE:
            docs.extend([
                {'title': 'Branch Trial Balances & Intercompany Matrix', 'category': 'CONSOLIDATION', 'mandatory': True, 'description': 'Trial balances from all operating branches for consolidation & elimination.'},
                {'title': 'Internal Financial Controls (IFC) Risk Matrix', 'category': 'IFC', 'mandatory': True, 'description': 'Documentation of key entity-level and transaction-level controls.'},
            ])

        if engagement_type == EngagementType.TAX_AUDIT:
            docs.extend([
                {'title': 'Form 3CD Clause 21(d) Cash Payments Sheet', 'category': 'TAX_AUDIT', 'mandatory': True, 'description': 'Disallowances under Section 40A(3) payments in cash > ₹10,000.'},
                {'title': 'Form 26AS & AIS Reconciliation', 'category': 'TAX_AUDIT', 'mandatory': True, 'description': 'Income tax annual information statement and TDS credit ledger.'},
            ])

        return docs

    def __str__(self):
        return f"WorkflowConfig: {self.engagement.title} ({self.engagement.engagement_type})"


