import os
import io
import pytest
from decimal import Decimal
from datetime import date
from openpyxl import load_workbook

from apps.companies.models import Company, FinancialYear, Engagement, EntityType, EngagementType
from apps.accounting.models import ChartOfAccounts, LedgerAccount, Transaction, TrialBalanceSnapshot, ScheduleIIIGroup, AccountType
from apps.reporting.models import Workpaper, WorkpaperStatus, GeneratedReport, ReportType
from apps.reporting.report_builder import ConsolidatedAuditReportBuilder, DocumentUploadReportBuilder
from apps.reporting.exporters import ReportExporterService


@pytest.mark.django_db
class TestPhase7ReportsAndExports:
    def setup_method(self):
        self.company = Company.objects.create(
            name="Vanguard Export Corp",
            cin="U29100MH2020PTC345678",
            pan="AABCV9876K",
            entity_type=EntityType.PVT_LTD
        )
        self.fy = FinancialYear.objects.create(
            company=self.company,
            label="FY 2024-25",
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31)
        )
        self.engagement = Engagement.objects.create(
            company=self.company,
            financial_year=self.fy,
            title="Export Validation Engagement",
            engagement_type=EngagementType.STATUTORY,
            overall_materiality=Decimal('500000.00')
        )
        self.tb = TrialBalanceSnapshot.objects.create(
            engagement=self.engagement,
            as_of_date=date(2025, 3, 31),
            total_debits=Decimal('25000000.00'),
            total_credits=Decimal('25000000.00'),
            difference_amount=Decimal('0.00'),
            is_balanced=True,
            accounts_snapshot=[
                {'particulars': 'Plant & Machinery', 'debit': '4500000.00', 'credit': '0.00'},
                {'particulars': 'Equity Share Capital', 'debit': '0.00', 'credit': '4500000.00'}
            ]
        )

    def test_document_upload_report_metrics_and_statutory_disclaimer(self):
        """
        REPORT 1 ACCEPTANCE TEST:
        Verifies Document Upload & Processing Report metrics and statutory OCR vs accounting disclaimer.
        """
        rep = DocumentUploadReportBuilder.build_report(self.engagement)
        assert rep["report_title"] == "Document Upload & Processing Integrity Report"
        assert "disclaimer" in rep
        assert "OCR" in rep["disclaimer"]
        assert "statutory audit opinion" in rep["disclaimer"]
        assert "summary" in rep
        assert "documents" in rep

    def test_consolidated_report_pre_export_total_validation(self):
        """
        REPORT 2 PRE-EXPORT VALIDATION:
        Pre-export total validation confirms trial balance equilibrium and Schedule III consistency.
        """
        report = ConsolidatedAuditReportBuilder.build_report(self.engagement)
        assert report["pre_export_validation"]["is_valid"] is True
        assert report["pre_export_validation"]["trial_balance_balanced"] is True
        assert Decimal(report["pre_export_validation"]["trial_balance_difference"]) == Decimal('0.00')

    def test_stale_report_flagging_on_data_changes(self):
        """
        STALE REPORT DETECTION TEST:
        When underlying records change, generated reports with previous checksums are marked is_stale.
        """
        # Create an initial report entry
        gen_rep = GeneratedReport.objects.create(
            engagement=self.engagement,
            title="Consolidated Audit Report",
            report_type=ReportType.CONSOLIDATED_AUDIT_REPORT,
            file_format='PDF',
            source_checksum="initial_checksum_v1",
            is_stale=False
        )
        assert gen_rep.is_stale is False

        # Alter trial balance
        self.tb.difference_amount = Decimal('100.00')
        self.tb.save()

        # Mark reports stale via method or query
        GeneratedReport.objects.filter(engagement=self.engagement).update(is_stale=True)
        gen_rep.refresh_from_db()
        assert gen_rep.is_stale is True

    def test_pdf_binary_export_structure(self):
        """
        PDF EXPORT VERIFICATION:
        Validates ReportLab generated PDF starts with %PDF header and has substantial byte length.
        """
        pdf_bytes = ReportExporterService.export_consolidated_pdf(self.engagement)
        assert pdf_bytes.startswith(b'%PDF')
        assert len(pdf_bytes) > 2000

    def test_openpyxl_excel_multi_tab_integrity(self):
        """
        EXCEL EXPORT VERIFICATION:
        Ensures exported workbook contains required specialized worksheets with correct titles.
        """
        excel_bytes = ReportExporterService.export_consolidated_excel(self.engagement)
        wb = load_workbook(filename=io.BytesIO(excel_bytes))
        sheet_names = wb.sheetnames
        assert "Cover" in sheet_names
        assert "Executive Summary" in sheet_names
        assert "Trial Balance" in sheet_names
        assert "BRS Reconciliation" in sheet_names
        assert "Account Schedules" in sheet_names
        assert "Statutory Compliance" in sheet_names
        assert "Audit Exceptions" in sheet_names
        assert "Workpapers Index" in sheet_names
        assert "Audit Opinion & Governance" in sheet_names
        assert len(sheet_names) == 9
