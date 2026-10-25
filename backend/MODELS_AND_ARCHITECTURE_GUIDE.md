# Captrix AI — Backend Architecture & Models Guide

Welcome to the **Captrix AI** Django Backend.

This backend is architected following **Domain-Driven Design (DDD)** and official Django enterprise best practices. Rather than dumping all logic into a single giant file, models and services are organized into **7 domain apps** under [`apps/`](./apps/).

---

## 1. Quick Model Directory & Reference (26 Models)

All 26 models are centralized and can be imported directly via `models_registry.py`:
```python
from models_registry import Company, TrialBalanceSnapshot, Workpaper, ExceptionItem
```

### Table of Models by Domain

| App Directory | Model Name | Database Table | Key Purpose |
| :--- | :--- | :--- | :--- |
| **`apps/companies`** | `Company` | `companies_company` | Client profile, CIN, PAN, GSTIN, business scale tier (1 to 4). |
| | `FinancialYear` | `companies_financialyear` | Financial year (e.g. FY 2024-25), start/end dates, lock status. |
| | `Engagement` | `companies_engagement` | Statutory/Tax audit engagement container, materiality benchmark. |
| | `EngagementWorkflowConfig` | `companies_engagementworkflowconfig`| Applicable frameworks: CARO 2020, Form 3CD, Schedule III division. |
| **`apps/accounting`**| `ChartOfAccounts` | `accounting_chartofaccounts` | Standardized chart of accounts with Schedule III classification. |
| | `LedgerAccount` | `accounting_ledgeraccount` | General ledger master, opening/closing decimal balances. |
| | `Transaction` | `accounting_transaction` | Extracted journal/voucher entries, counterparty, voucher type. |
| | `TrialBalanceSnapshot` | `accounting_trialbalancesnapshot` | As-of date snapshot, total debits, total credits, is_balanced. |
| **`apps/ingestion`** | `Document` | `ingestion_document` | Uploaded client files, SHA-256 hash, size, document classification. |
| | `ProcessingJob` | `ingestion_processingjob` | Per-document extraction stage, valid rows, review required count. |
| | `ExtractedRecord` | `ingestion_extractedrecord` | Normalized line items preserving exact row/column coordinates. |
| | `ProcessingRun` | `ingestion_processingrun` | 14-stage autonomous orchestrator run instance & metrics. |
| **`apps/reconciliation`**| `ReconciliationRun` | `reconciliation_reconciliationrun`| Header for BRS, GST ITC, and GL vs Trial Balance reconciliations. |
| | `ReconciliationItem`| `reconciliation_reconciliationitem`| Line item 4-way matching, timing differences, clearance dates. |
| **`apps/audit`** | `AuditProcedure` | `audit_auditprocedure` | Standardized ICAI audit procedure definitions (SA 200 to SA 705). |
| | `ProcedureExecution`| `audit_procedureexecution` | Test execution results, tested record count, findings summary. |
| | `ExceptionItem` | `audit_exceptionitem` | Discrepancies, audit assertions, severity (Critical/High), risk state. |
| | `FixedAsset` | `audit_fixedasset` | FAR dual depreciation (Companies Act SLM vs Income Tax Sec 32 WDV).|
| | `SubledgerAgingItem`| `audit_subledgeragingitem`| Debtors & Creditors aging, MSME Sec 43B(h) overdue days & interest.|
| | `RelatedParty` | `audit_relatedparty` | Related party transactions registry (AS 18 / Ind AS 24). |
| | `StatutoryClauseAudit`| `audit_statutoryclauseaudit`| CARO 2020 & Form 3CD clause verification status and evidence. |
| **`apps/reporting`** | `Workpaper` | `reporting_workpaper` | SA 230 standardized electronic audit workpapers with versioning. |
| | `ProposedAdjustment`| `reporting_proposedadjustment`| Auditor-proposed balanced adjusting entries with P&L impact. |
| | `GeneratedReport` | `reporting_generatedreport` | Deliverable files: PDF dossier, 8-tab Excel workbook, CSV extract. |
| **`apps/core`** | `UserProfile` | `core_userprofile` | Chartered Accountant role, membership number, firm registration. |
| | `AuditLog` | `core_auditlog` | Immutable governance audit trail of all actions and sign-offs. |

---

## 2. Core Service Engines & Algorithms

| Service File | Lines | Key Algorithms & Mathematics |
| :--- | :---: | :--- |
| **`apps/ingestion/orchestrator.py`** | 1,057 | 14-Stage automated pipeline, cryptographic SHA-256 integrity, ZIP sandboxing, and ICAI SA 705 Audit Completeness Matrix. |
| **`apps/accounting/services.py`** | 616 | Schedule III Trial Balance equilibrium ($\sum \text{Dr} - \sum \text{Cr} = 0$), Benford's Law Chi-Square distribution ($P(d) = \log_{10}(1 + 1/d)$), round sum and high-value journal scrutiny. |
| **`apps/reconciliation/services.py`** | 782 | BRS 4-way matching engine with $\pm 3$ day clearance tolerance, GST Rule 36(4) ITC matching, FAR dual depreciation (Companies Act Sch II SLM vs Sec 32 WDV), and MSME Section 43B(h) 45-day overdue penalty interest engine ($3 \times \text{RBI Bank Rate}$). |
| **`apps/audit/services.py` & `compliance_rules.py`** | 703 | CARO 2020 Clause 3 and Tax Audit Form 3CD compliance verification (Sec 40A(3) cash payments $> \text{₹}10,000$, Sec 40(a)(ia) TDS defaults). |
| **`apps/reporting/services.py` & `report_builder.py`** | 1,625 | 14-section Consolidated Financial & Audit Dossier generator, SA 230 standardized workpaper generator, 8-tab Excel builder (`openpyxl`), and PDF report builder (`reportlab`). |
| **`apps/companies/completion_service.py`** | 305 | SA 220 separation of duties (preparers cannot approve their own workpapers) and engagement completion checklist evaluator. |

---

## 3. Running Backend Tests

```powershell
.\backend\.venv\Scripts\python.exe -m pytest backend\tests
```
*Current test suite: 78 tests passing across unit, integration, and statutory compliance checks.*
