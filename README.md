# Captrix AI — Automated Accounting Verification & CA Audit Intelligence Platform

**Captrix AI** is an advanced, India-focused Automated Accounting Verification, CA Audit & Financial Intelligence Platform built from scratch for Chartered Accountants (CAs), statutory auditors, and corporate finance teams.

It automates the complete routine audit lifecycle:
$$\text{Single ZIP Ingestion} \longrightarrow \text{Security Validation} \longrightarrow \text{Extraction} \longrightarrow \text{Classification} \longrightarrow \text{Accounting & Tax Analytics} \longrightarrow \text{Exceptions} \longrightarrow \text{SA 230 Workpapers} \longrightarrow \text{SA 220 Review} \longrightarrow \text{Audit Dossier (.ZIP)}$$

The platform guarantees **100% deterministic mathematical calculations**, **fail-closed processing**, **zero synthetic plug figures**, **immutable source-of-truth preservation** (via SHA-256 cryptographic hashing), and strict alignment with the **Companies Act 2013**, **Schedule III**, **CARO 2020**, and the **Income Tax Act 1961** (Form 3CD).

---

## 1. Non-Negotiable Core Architecture & Principles

1. **Flexible Document & ZIP Archive Ingestion**:
   - The routine auditor interface supports uploading company financial records (`.csv`, `.xlsx`, `.xls`, `.pdf`, `.png`, `.jpg`) **file-by-file individually** or bundled in **a single consolidated .ZIP archive**.
   - Built-in zip bomb protection (200MB limit, 100 files max), path traversal rejection (`..`), and encrypted archive rejection.
   - Every uploaded document is cryptographically verified and tracked with SHA-256 hashing.
2. **Audit Evidence Completeness Matrix (SA 705 Compliance)**:
   - Interactive pre-flight and live-run audit evidence completeness tracking.
   - Pinpoints any missing client documents (Bank Statements, GSTR-2B, FAR, Debtors/Creditors subledgers) and explains the exact audit procedure blocked (e.g. BRS unverified, GST Rule 36(4) unverified) without inventing missing balances.
3. **Zero Synthetic Figures & Plugs**:
   - Out-of-balance Trial Balances fail closed and generate structured exceptions. The system never manufactures artificial balancing plug numbers.
4. **Deterministic Decimal Arithmetic & Advanced Algorithms**:
   - All monetary calculations utilize Python's `decimal.Decimal` with 2 decimal places to completely eliminate binary floating-point rounding errors.
   - Algorithms include Benford's Law Chi-Square distribution analysis, 4-way BRS matching with clearance tolerance, MSME 43B(h) overdue days and 3x RBI interest, and dual depreciation (Schedule II SLM vs Sec 32 WDV).
5. **Separation of Duties (SA 220)**:
   - Dedicated CA Review Queue enforces that the preparer who generated a workpaper cannot approve it; approval requires an authorized engagement partner or manager.

---

## 2. The 14-Stage Deterministic Pipeline

| Stage # | Stage Name | Description | Fails Closed On |
| :---: | :--- | :--- | :--- |
| **01** | `UPLOAD_RECEIVED` | Ingests client `.ZIP` archive, verifies file signature, and extracts supported documents. | Corrupted ZIP, password encryption, path traversal |
| **02** | `FILE_VALIDATION` | Verifies SHA-256 hash match against stored evidence and disk presence. | Hash mismatch, missing file, 0-byte file |
| **03** | `DOCUMENT_CLASSIFICATION` | Content-based classification of documents based on table headers and keywords. | Unidentifiable mandatory documents |
| **04** | `DATA_EXTRACTION` | Parses structured lines, Indian number formats, dates, and accounting fields. | Unparseable or unreadable lines |
| **05** | `DATA_VALIDATION` | Validates numeric values, debits vs credits, and eliminates negative amounts. | Invalid numeric characters |
| **06** | `ACCOUNT_NORMALIZATION` | Standardizes account codes, categories, and Schedule III division mappings. | Unmapped core financial heads |
| **07** | `ACCOUNTING_CALCULATIONS` | Computes Trial Balance totals, financial ratios, P&L, and Balance Sheet balances. | Unbalanced Trial Balance ($\text{Dr} \ne \text{Cr}$) |
| **08** | `RECONCILIATION` | Performs Bank Reconciliation Statement (BRS) and GST ITC vs GSTR-2B matching. | Reconciliation engine errors |
| **09** | `AUDIT_PROCEDURES` | Evaluates CARO 2020 clauses, Section 43B(h) MSME payables, and dual FAR depreciation. | Statutory threshold breaches |
| **10** | `EXCEPTION_GENERATION` | Produces structured exceptions with audit assertions (Completeness, Accuracy, Cutoff). | Critical risk threshold exceedance |
| **11** | `WORKPAPER_GENERATION` | Formulates draft SA 230 compliant working papers linked to extracted source rows. | Incomplete documentation |
| **12** | `REPORT_ASSEMBLY` | Assembles the complete 14-section Consolidated Financial and Audit Analysis Report. | Missing audit sections |
| **13** | `OUTPUT_VALIDATION` | Validates totals against database and generates PDF, 8-tab Excel, CSV, and manifest. | Pre-export mathematical discrepancies |
| **14** | `COMPLETED` | Concludes run and updates engagement review status. Flags if review required. | Unresolved critical exceptions |

---

## 3. Technology Stack

- **Frontend**: React 19, TypeScript with strict typing, Vite, Tailwind CSS v4, Lucide React icons, Recharts, React Router v7.
- **Backend**: Python 3.12, Django 5.1, Django REST Framework 3.15, SQLite in WAL mode with foreign keys enabled, `openpyxl`, `pdfplumber`, `pandas`, `reportlab`.
- **Theme**: Restored Dark Navy Sidebar (`#0a0f1d`) and Light Theme Workspace (`bg-slate-50/70`, `bg-white`, `border-slate-200`, `text-slate-900`).
- **Health Check API**: Unauthenticated `GET /api/health/` and `GET /api/core/health/` returning HTTP 200 OK.

---

## 4. Local Windows Launch

### Fast Setup (One-Time)
Double-click or run `setup.bat`:
```cmd
setup.bat
```
This script:
1. Verifies Python 3.11+ and Node.js 18+ availability.
2. Creates and activates virtual environment `backend\.venv`.
3. Installs Python dependencies from `backend\requirements.txt`.
4. Runs Django migrations.
5. Installs Node.js frontend packages in `frontend\`.

### Launching the Application
Double-click or run `start.bat`:
```cmd
start.bat
```
This automatically launches:
- **Django Backend**: `http://127.0.0.1:8000/`
- **React Frontend**: `http://localhost:3000/`
- Opens your browser to the Captrix AI Dashboard.

---

## 5. Verification & Test Suite Results

### Backend Test Suite (Pytest)
```cmd
backend\.venv\Scripts\python -m pytest backend/tests
```
**Result**: **78 passed**, 0 failed, 0 skipped in ~116s.
- `test_single_zip_ingestion.py`: Valid ZIP upload, corrupted zip rejection, path traversal rejection, encrypted zip rejection, unsupported files rejection.
- `test_health_check.py`: Health endpoints `/api/health/` and `/api/core/health/`.
- `test_enterprise_tiering_and_review_queue.py`: SA 220 separation-of-duties review queue, 4-tier business matrix, multi-branch hierarchies.
- `test_india_specific_audit_engine.py`: CARO 2020, Form 3CD, Section 43B(h), Section 40A(3), Dual FAR depreciation (Companies Act SLM vs IT Act WDV).
- `test_phase7_acceptance_suite.py`: End-to-end 14-stage automated pipeline against independent ground truth.
- `test_negative_and_security.py`: Multi-tenant isolation, empty file rejection, unbalanced TB fails closed.

### Frontend Test Suite (Vitest)
```cmd
cd frontend
npm test -- --run
```
**Result**: **16 passed** across 4 test suites.
- `AutomationWorkflow.test.tsx`: Single ZIP archive workflow, drag & drop, synthetic demo runner, 14-stage progression, final audit file.
- `Phase9EnterpriseAndReview.test.tsx`: SA 220 review queue, approval modals, status transitions.
- `Phase3Pages.test.tsx`: Reconciliation workspaces, BRS, GST ITC.
- `App.test.tsx`: Sidebar navigation, layout structure.

### Production Build
```cmd
cd frontend
npm run build
```
**Result**: Built in ~2.1s with zero TypeScript or packaging errors.

---

## 6. Statutory & Ethical Compliance Disclaimers

> [!IMPORTANT]
> **Chartered Accountant Sign-Off Requirement**:
> Captrix AI assists Chartered Accountants and auditors by automating data extraction, calculations, and preliminary working papers.
> Under ICAI guidelines and Indian statutory law, software cannot provide statutory sign-off or replace human professional judgment.
> A qualified Chartered Accountant must review all workpapers, investigate flagged exceptions, apply professional skepticism, and physically or cryptographically sign the statutory audit report with their ICAI Membership Number, Firm Registration Number (FRN), and Unique Document Identification Number (UDIN).


## Audit report finalization safety

Captrix keeps statutory reports in draft until the server-side integrity gate passes. A client-side CA name, FRN, membership number, or UDIN-shaped string is not proof of authorization or ICAI verification. External verification and authorized partner approval must be recorded by a trusted server-side workflow. See `PHASE11_CHANGELOG.md` for the latest integrity fixes and test limitations.
