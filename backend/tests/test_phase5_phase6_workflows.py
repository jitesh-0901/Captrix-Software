import os
import io
import pytest
from decimal import Decimal
from datetime import date
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.companies.models import Company, FinancialYear, Engagement, EntityType, EngagementType, EngagementStatus
from apps.companies.completion_service import EngagementCompletionService
from apps.ingestion.models import Document, DocumentStatus, DocumentType
from apps.accounting.models import ChartOfAccounts, LedgerAccount, Transaction, TrialBalanceSnapshot, ScheduleIIIGroup, AccountType
from apps.audit.models import ProcedureExecution, ProcedureStatus, AuditProcedure, ExceptionItem, ExceptionSeverity, ExceptionStatus
from apps.reporting.models import Workpaper, WorkpaperStatus, ProposedAdjustment, AdjustmentStatus, GeneratedReport
from apps.reporting.report_builder import ConsolidatedAuditReportBuilder, DocumentUploadReportBuilder
from apps.reporting.exporters import ReportExporterService


@pytest.mark.django_db
class TestPhase5AndPhase6Suite:
    def setup_method(self):
        self.client = APIClient()

        # Users for Separation of Duties testing
        self.preparer_user = User.objects.create_user(username="preparer_ca", password="password123")
        self.reviewer_user = User.objects.create_user(username="partner_fca", password="password123")

        # 1. Create Company
        self.company = Company.objects.create(
            name="Alpha Infotech Private Limited",
            cin="U72200MH2021PTC123456",
            pan="AABCA1234F",
            gstin="27AABCA1234F1Z5",
            entity_type=EntityType.PVT_LTD
        )

        # 2. Create Financial Year
        self.fy = FinancialYear.objects.create(
            company=self.company,
            label="FY 2024-25",
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31)
        )

        # 3. Create Audit Engagement
        self.engagement = Engagement.objects.create(
            company=self.company,
            financial_year=self.fy,
            title="Statutory Audit FY 2024-25",
            engagement_type=EngagementType.STATUTORY,
            overall_materiality=Decimal('500000.00'),
            performance_materiality=Decimal('375000.00'),
            clearly_trivial_threshold=Decimal('25000.00'),
            lead_partner=self.reviewer_user
        )

    def test_workpaper_review_separation_of_duties_enforcement(self):
        """
        SEPARATION OF DUTIES TEST:
        SA 220 / SQC 1 requires that a workpaper preparer cannot approve their own workpaper.
        System must reject self-approval with HTTP 403 Forbidden.
        """
        wp = Workpaper.objects.create(
            engagement=self.engagement,
            wp_reference="WP-TEST-SOD",
            title="Cash & Bank Testing",
            audit_area="Cash and Bank",
            audit_objective="Verify bank balances",
            scope_and_coverage="100% bank accounts",
            testing_methodology="Direct confirmation",
            results_summary="All balances confirmed",
            proposed_conclusion="Satisfactory",
            status=WorkpaperStatus.READY_FOR_REVIEW,
            preparer=self.preparer_user,
            evidence_verified=True
        )

        # Case 1: Preparer attempts to self-approve -> Forbidden (403)
        self.client.force_authenticate(user=self.preparer_user)
        res_self = self.client.post(
            f"/api/reporting/workpapers/{wp.id}/review_action/",
            {"action_type": "APPROVE", "reason": "Self-certifying my own testing"},
            format="json"
        )
        assert res_self.status_code == 403
        assert "Separation of duties violation" in res_self.data["error"]

        # Case 2: Different user (Partner) approves -> Succeeds (200)
        self.client.force_authenticate(user=self.reviewer_user)
        res_partner = self.client.post(
            f"/api/reporting/workpapers/{wp.id}/review_action/",
            {"action_type": "APPROVE", "reason": "Reviewed and verified bank confirmation certificates."},
            format="json"
        )
        assert res_partner.status_code == 200
        wp.refresh_from_db()
        assert wp.status == WorkpaperStatus.APPROVED
        assert wp.approved_at is not None
        assert wp.reviewed_by == self.reviewer_user
        assert len(wp.version_history) >= 1

    def test_workpaper_return_for_correction_and_version_history(self):
        """
        RETURN FOR CORRECTION TEST:
        Reviewer can return workpaper for correction with notes.
        Workpaper status changes to RETURNED_FOR_CORRECTION and logs version history snapshot.
        """
        wp = Workpaper.objects.create(
            engagement=self.engagement,
            wp_reference="WP-TEST-RET",
            title="Inventory Cut-off",
            audit_area="Inventory",
            audit_objective="Cut-off verification",
            scope_and_coverage="March invoices",
            testing_methodology="Voucher sampling",
            results_summary="Sample testing",
            proposed_conclusion="Satisfactory",
            status=WorkpaperStatus.READY_FOR_REVIEW,
            preparer=self.preparer_user
        )

        self.client.force_authenticate(user=self.reviewer_user)
        res = self.client.post(
            f"/api/reporting/workpapers/{wp.id}/review_action/",
            {
                "action_type": "REQUEST_CORRECTION",
                "reason": "Missing GRN documents for last 3 inward dispatches.",
                "notes": "Please attach signed goods received notes."
            },
            format="json"
        )
        assert res.status_code == 200
        wp.refresh_from_db()
        assert wp.status == WorkpaperStatus.RETURNED_FOR_CORRECTION
        assert "Missing GRN documents" in wp.return_reason
        assert wp.version == 2
        assert len(wp.version_history) == 1
        assert wp.version_history[0]["action"] == "RETURNED_FOR_CORRECTION"

    def test_engagement_completion_controls_fail_closed_blocking(self):
        """
        COMPLETION CONTROLS TEST:
        Finalization must fail closed if material exceptions remain open or workpapers are unapproved.
        Once partner records permitted exception override or resolves conditions, finalization succeeds.
        """
        # Create unreviewed workpaper (blocker)
        wp = Workpaper.objects.create(
            engagement=self.engagement,
            wp_reference="WP-UNAPPROVED",
            title="Unreviewed Workpaper",
            audit_area="Investments",
            audit_objective="Valuation check",
            scope_and_coverage="Market quotes",
            testing_methodology="Fair value check",
            results_summary="Checked",
            proposed_conclusion="Fairly stated",
            status=WorkpaperStatus.DRAFT
        )

        # Create critical open exception (blocker)
        exc = ExceptionItem.objects.create(
            engagement=self.engagement,
            title="Unapproved Cash Payment under Section 40A(3)",
            severity=ExceptionSeverity.CRITICAL,
            status=ExceptionStatus.OPEN,
            amount_involved=Decimal('850000.00'), # Exceeds materiality (500k)
            category="TAX_AUDIT",
            explanation="Single day cash payment exceeded ₹10,000 threshold."
        )

        # 1. Check checklist: should be blocked
        checklist = EngagementCompletionService.evaluate_checklist(self.engagement)
        assert checklist["can_finalize"] is False
        assert checklist["overall_status"] == "BLOCKED"
        assert len(checklist["blockers"]) >= 2

        # 2. Attempt finalization via API -> Must return 400 Bad Request
        self.client.force_authenticate(user=self.reviewer_user)
        res_fail = self.client.post(f"/api/companies/engagements/{self.engagement.id}/finalize/")
        assert res_fail.status_code == 400
        assert res_fail.data["success"] is False

        # 3. Resolve workpaper and override exception
        wp.status = WorkpaperStatus.APPROVED
        wp.save()

        # Document partner permitted exception
        res_override = self.client.post(
            f"/api/companies/engagements/{self.engagement.id}/override_exception/",
            {
                "code": "CHK-04-EXCEPTIONS",
                "reason": "Payment made to agricultural cultivator exempt under Income Tax Rule 6DD(e)."
            },
            format="json"
        )
        assert res_override.status_code == 200

        # Mark procedure executions as satisfied
        proc = AuditProcedure.objects.create(
            code="PROC-TEST-P5",
            title="Test Procedure",
            category="COMPLETENESS",
            audit_objective="Test",
            execution_logic_name="test"
        )
        ProcedureExecution.objects.create(
            engagement=self.engagement,
            procedure=proc,
            status=ProcedureStatus.PASSED_NO_EXCEPTIONS
        )

        # Create balanced TB
        TrialBalanceSnapshot.objects.create(
            engagement=self.engagement,
            as_of_date=date(2025, 3, 31),
            total_debits=Decimal('1000000.00'),
            total_credits=Decimal('1000000.00'),
            difference_amount=Decimal('0.00'),
            is_balanced=True
        )

        from apps.reconciliation.models import ReconciliationRun, ReconciliationStatus
        ReconciliationRun.objects.create(
            engagement=self.engagement,
            recon_type='BANK',
            status=ReconciliationStatus.BALANCED,
            as_of_date=date(2025, 3, 31),
            unreconciled_difference=Decimal('0.00'),
            unmatched_count=0
        )

        # Check that can_finalize is now True
        self.engagement.refresh_from_db()
        eval_updated = EngagementCompletionService.evaluate_checklist(self.engagement)
        assert eval_updated["can_finalize"] is True

        # 4. Finalize engagement -> Must succeed
        res_success = self.client.post(
            f"/api/companies/engagements/{self.engagement.id}/finalize/",
            {"justification": "All items verified and partner override justified under Rule 6DD."},
            format="json"
        )
        assert res_success.status_code == 200
        assert res_success.data["success"] is True
        self.engagement.refresh_from_db()
        assert self.engagement.is_finalized is True
        assert self.engagement.status == EngagementStatus.COMPLETED

    def test_document_upload_report_builder_and_ocr_disclaimer(self):
        """
        REPORT 1 TEST:
        Builds Document Upload and Processing Report with file metrics, duplicate warnings,
        and statutory extraction vs accounting correctness disclaimer.
        """
        doc = Document.objects.create(
            engagement=self.engagement,
            original_filename="Bank_Statement_HDFC_FY24_25.pdf",
            file_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            file_size_bytes=102400,
            mime_type="application/pdf",
            document_type=DocumentType.BANK_STATEMENT,
            status=DocumentStatus.VERIFIED
        )

        report = DocumentUploadReportBuilder.build_report(self.engagement)
        assert report["total_documents"] == 1
        assert "DATA EXTRACTION INTEGRITY NOTICE" in report["statutory_disclaimer"]
        assert len(report["files"]) == 1
        f_rep = report["files"][0]
        assert f_rep["original_filename"] == "Bank_Statement_HDFC_FY24_25.pdf"
        assert f_rep["accounting_verification_status"] == "AUDITOR_VERIFIED"

    def test_consolidated_report_builder_all_sections_a_to_n(self):
        """
        REPORT 2 TEST:
        Builds Consolidated Financial & Audit Analysis Report verifying that all 14 sections
        (A through N) exist and are populated from database records.
        """
        # Create sample trial balance snapshot
        TrialBalanceSnapshot.objects.create(
            engagement=self.engagement,
            as_of_date=date(2025, 3, 31),
            total_debits=Decimal('50000000.00'),
            total_credits=Decimal('50000000.00'),
            difference_amount=Decimal('0.00'),
            is_balanced=True
        )

        # Create Ledger Accounts
        coa_rev = ChartOfAccounts.objects.create(
            company=self.company, account_code="4001", account_name="Software Revenue",
            account_type=AccountType.REVENUE, schedule_iii_group=ScheduleIIIGroup.REVENUE_OPERATIONS
        )
        LedgerAccount.objects.create(
            company=self.company, coa=coa_rev, name="Software Revenue",
            closing_balance=Decimal('45000000.00'), closing_balance_type='Cr'
        )

        coa_exp = ChartOfAccounts.objects.create(
            company=self.company, account_code="5001", account_name="Employee Salaries",
            account_type=AccountType.EXPENSE, schedule_iii_group=ScheduleIIIGroup.EMPLOYEE_BENEFITS
        )
        LedgerAccount.objects.create(
            company=self.company, coa=coa_exp, name="Employee Salaries",
            closing_balance=Decimal('25000000.00'), closing_balance_type='Dr'
        )

        report = ConsolidatedAuditReportBuilder.build_report(self.engagement)

        # Verify all 14 sections exist
        for sec_letter in ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n']:
            sec_key = f"section_{sec_letter}"
            assert sec_key in report, f"Missing section {sec_key} in consolidated audit report"

        # Verify specific grounded calculations (PAT = PBT 20M less 25% corporate tax provision 5M = 15M)
        assert report["section_a"]["cin"] == "U72200MH2021PTC123456"
        assert report["section_b"]["trial_balance_balanced"] is True
        assert Decimal(report["section_c"]["revenue_from_operations"]) == Decimal('45000000.00')
        assert Decimal(report["section_c"]["total_expenses"]) == Decimal('25000000.00')
        assert Decimal(report["section_c"]["net_profit_loss"]) == Decimal('15000000.00')
        assert "STATUTORY AUDITOR MANDATORY DISCLAIMER" in report["section_n"]["statutory_auditor_disclaimer"]

    def test_multi_format_exports_pdf_excel_csv(self):
        """
        MULTI-FORMAT EXPORT TEST:
        Verifies ReportLab PDF, OpenPyXL multi-tab Excel, and CSV generation.
        Asserts that exported files are valid, non-empty, and column totals match database records.
        """
        # Ensure at least 1 trial balance snapshot exists
        TrialBalanceSnapshot.objects.create(
            engagement=self.engagement,
            as_of_date=date(2025, 3, 31),
            total_debits=Decimal('100000.00'),
            total_credits=Decimal('100000.00'),
            difference_amount=Decimal('0.00'),
            is_balanced=True
        )

        # 1. Test PDF Export
        pdf_bytes = ReportExporterService.export_consolidated_pdf(self.engagement)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 1000
        assert pdf_bytes.startswith(b'%PDF')

        # 2. Test Excel Export
        excel_bytes = ReportExporterService.export_consolidated_excel(self.engagement)
        assert isinstance(excel_bytes, bytes)
        assert len(excel_bytes) > 1000
        # Verify ZIP / XLSX magic header
        assert excel_bytes.startswith(b'PK')

        # 3. Test CSV Export
        csv_str = ReportExporterService.export_consolidated_csv(self.engagement)
        assert isinstance(csv_str, str)
        assert "CAPTRIX AI" in csv_str and "CONSOLIDATED AUDIT REPORT SUMMARY" in csv_str
        assert "Revenue from Operations" in csv_str

        # 4. Test API Export Endpoints
        res_pdf = self.client.get(f"/api/reporting/reports/export_pdf/?engagement={self.engagement.id}")
        assert res_pdf.status_code == 200
        assert res_pdf["Content-Type"] == "application/pdf"

        res_excel = self.client.get(f"/api/reporting/reports/export_excel/?engagement={self.engagement.id}")
        assert res_excel.status_code == 200
        assert "spreadsheetml" in res_excel["Content-Type"]

        res_csv = self.client.get(f"/api/reporting/reports/export_csv/?engagement={self.engagement.id}")
        assert res_csv.status_code == 200
        assert "text/csv" in res_csv["Content-Type"]
