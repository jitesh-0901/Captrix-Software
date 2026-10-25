"""
CAPTRIX AI — CENTRAL MODEL REGISTRY & SCHEMA OVERVIEW
=====================================================
This file consolidates and re-exports all 26 core Django ORM models across
the 7 domain-specific apps in `backend/apps/`.

Audit teams, developers, and scripts can import any model directly from here:
    from models_registry import Company, TrialBalanceSnapshot, Workpaper, etc.
"""

import os
import django

if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

try:
    django.setup()
except RuntimeError:
    pass  # Already setup

# ==============================================================================
# 1. CORE & GOVERNANCE (apps.core)
# ==============================================================================
from apps.core.models import (
    UserProfile,        # CA user credentials, membership number, firm name
    AuditLog,           # Immutable audit trail of every governance action
)

# ==============================================================================
# 2. COMPANIES & ENGAGEMENTS (apps.companies)
# ==============================================================================
from apps.companies.models import (
    Company,                    # Master entity: CIN, PAN, GSTIN, business tier (1-4)
    FinancialYear,              # Accounting FY period (e.g. FY 2024-25)
    Engagement,                 # Statutory/tax audit engagement container & materiality
    EngagementWorkflowConfig,   # CARO / Form 3CD / MSMED statutory applicability rules
)

# ==============================================================================
# 3. INGESTION & PIPELINE RUNS (apps.ingestion)
# ==============================================================================
from apps.ingestion.models import (
    Document,           # Uploaded files with SHA-256 cryptographic hashes
    ProcessingJob,      # Per-document extraction job status & record counts
    ExtractedRecord,    # Normalized rows preserving source file coordinates
    ProcessingRun,      # 14-stage autonomous orchestrator run instance & metrics
)

# ==============================================================================
# 4. ACCOUNTING & TRIAL BALANCE (apps.accounting)
# ==============================================================================
from apps.accounting.models import (
    ChartOfAccounts,        # Normalized COA with Schedule III division mapping
    LedgerAccount,          # Ledger master with opening/closing decimal balances
    Transaction,            # Extracted journal/voucher entries for scrutiny
    TrialBalanceSnapshot,   # Balanced/Unbalanced TB snapshot with Decimal precision
)

# ==============================================================================
# 5. RECONCILIATIONS (apps.reconciliation)
# ==============================================================================
from apps.reconciliation.models import (
    ReconciliationRun,      # BRS, GSTR-2B, and GL vs TB reconciliation header
    ReconciliationItem,     # Line items with 4-way matching status and clearance dates
)

# ==============================================================================
# 6. STATUTORY AUDIT & TAX (apps.audit)
# ==============================================================================
from apps.audit.models import (
    AuditProcedure,         # Standardized procedure definition (ICAI SA standards)
    ProcedureExecution,     # Execution results, record counts, and audit assertions
    ExceptionItem,          # Audit findings, severity (Critical/High), and risk status
    FixedAsset,             # Dual FAR depreciation (Companies Act Sch II vs Sec 32)
    SubledgerAgingItem,     # Debtors/Creditors with MSME Sec 43B(h) overdue & interest
    RelatedParty,           # Related party disclosures under AS 18 / Ind AS 24
    StatutoryClauseAudit,   # CARO 2020 (Clause 3) and Form 3CD (44 clauses) checks
)

# ==============================================================================
# 7. REPORTING & WORKPAPERS (apps.reporting)
# ==============================================================================
from apps.reporting.models import (
    Workpaper,              # SA 230 standardized electronic audit working papers
    ProposedAdjustment,     # Balanced adjusting journal entries for auditor sign-off
    GeneratedReport,        # Final PDF, 8-tab Excel, and CSV summary deliverables
)

# List of all 26 exported models in neat order
__all__ = [
    # 1. Core
    'UserProfile',
    'AuditLog',
    # 2. Companies
    'Company',
    'FinancialYear',
    'Engagement',
    'EngagementWorkflowConfig',
    # 3. Ingestion
    'Document',
    'ProcessingJob',
    'ExtractedRecord',
    'ProcessingRun',
    # 4. Accounting
    'ChartOfAccounts',
    'LedgerAccount',
    'Transaction',
    'TrialBalanceSnapshot',
    # 5. Reconciliation
    'ReconciliationRun',
    'ReconciliationItem',
    # 6. Audit
    'AuditProcedure',
    'ProcedureExecution',
    'ExceptionItem',
    'FixedAsset',
    'SubledgerAgingItem',
    'RelatedParty',
    'StatutoryClauseAudit',
    # 7. Reporting
    'Workpaper',
    'ProposedAdjustment',
    'GeneratedReport',
]
