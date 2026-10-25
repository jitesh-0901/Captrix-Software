# Captrix — Phase 11: Report Integrity and Sign-off Safety

## Changes made

- Tightened the backend report integrity gate so a missing bank reconciliation, any non-BALANCED bank reconciliation, unmatched items, or residual variance blocks final issuance.
- Missing required source evidence for revenue cut-off (GSTR-1/e-way bill), fixed-asset records, or subledger aging now blocks final issuance. File presence alone is insufficient: relevant documents must be marked VERIFIED.
- High/critical exceptions in any non-terminal state block final issuance; `IN_REVIEW`, `EVIDENCE_REQUESTED`, and `ACCEPTED_RISK` are no longer silently treated as closed.
- Corporate entity engagements with missing CIN or PAN are blocked from final issuance.
- CA membership/FRN/UDIN format checks no longer count as external identity verification. A trusted server-side verification record and explicit verification flags are required.
- Corrected the exporter to read the integrity gate's actual `is_ready_for_final_issue` result.
- Draft reports no longer claim that all uploaded records were verified or include first-person statutory representations as if an auditor had completed the audit.
- Missing CIN/PAN/GSTIN are displayed as missing/review-required rather than incorrectly implying a non-corporate entity or non-registration.
- Removed client-side synthetic UDIN generation, default CA/FRN/member details, and one-click automatic statutory sign-off. This UI remains draft-only until a trusted server-side CA authorization and UDIN verification workflow is implemented.
- Added a regression test confirming that plausible-looking CA details do not authorize final issuance without external verification.

## Verification performed in this environment

- Python source syntax compilation: passed for all 156 Python files.
- TypeScript/TSX syntax transpilation of `FinalAuditFilePage.tsx`: passed with no syntax diagnostics.
- Static assertions for the new integrity-gate conditions: passed.
- Full Django tests/migrations were not run because Django and Django REST Framework are not installed in this environment.
- Full frontend TypeScript project build/tests were not run because the project dependencies (`frontend/node_modules`) are not installed. Syntax transpilation is not a substitute for the full build.

## Important remaining release blocker

This change deliberately fails closed. It prevents false finalization, but it does not itself implement an external ICAI UDIN verification integration or a complete server-side CA authorization workflow. Until that workflow is implemented and security-reviewed, Captrix can safely produce draft workpapers and audit analysis, but cannot mark a statutory audit report as officially verified/final from this screen.
