import os
import io
from decimal import Decimal
from datetime import date
import pytest
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIRequestFactory

from apps.companies.models import Company, FinancialYear, Engagement, EntityType, EngagementType
from apps.ingestion.models import Document, DocumentStatus, DocumentType, ProcessingJob, ExtractedRecord
from apps.ingestion.services import IngestionPipelineService
from apps.ingestion.parsers import DocumentParserService
from apps.reporting.models import Workpaper, WorkpaperStatus, ProposedAdjustment, AdjustmentStatus
from apps.reporting.views import WorkpaperViewSet, ProposedAdjustmentViewSet
from apps.audit.models import FixedAsset, SubledgerAgingItem, ExceptionItem, ExceptionStatus
from apps.reconciliation.models import ReconciliationRun

@pytest.mark.django_db
class TestEndToEndAccountsIngestionAndBatchSignoff:
    def setup_method(self):
        self.company = Company.objects.create(
            name="Orion Dynamics Manufacturing Private Limited",
            cin="U29100KA2021PTC145678",
            pan="AAFCO1234K",
            gstin="29AAFCO1234K1Z5",
            entity_type=EntityType.PVT_LTD
        )
        self.fy = self.company.financial_years.create(
            label="FY 2025-26",
            start_date=date(2025, 4, 1),
            end_date=date(2026, 3, 31)
        )
        self.engagement = Engagement.objects.create(
            company=self.company,
            financial_year=self.fy,
            title="Statutory Audit FY 2025-26",
            engagement_type=EngagementType.STATUTORY,
            overall_materiality=Decimal('1000000.00')
        )
        self.factory = APIRequestFactory()

    def test_full_company_accounts_workbook_ingestion_dispatches_all_engines(self):
        """
        Tests that uploading an enterprise integrated accounts workbook (.xlsx)
        automatically parses and dispatches ALL accounting subsystems:
        TB, GL, FAR, Subledger Aging, and Bank Reconciliation without manual friction.
        """
        sample_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'media', 'financial_docs', '2026', '10',
            'Captrix_Enterprise_Integrated_Input_FY2025-26.xlsx'
        )
        if not os.path.exists(sample_path):
            pytest.skip("Integrated sample workbook not found on disk")

        with open(sample_path, 'rb') as f:
            file_bytes = f.read()

        uploaded = SimpleUploadedFile(
            name="Captrix_Enterprise_Integrated_Input_FY2025-26.xlsx",
            content=file_bytes,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        doc = Document.objects.create(
            engagement=self.engagement,
            original_filename="Captrix_Enterprise_Integrated_Input_FY2025-26.xlsx",
            file=uploaded,
            file_hash="mock_hash_orion_enterprise_001",
            file_size_bytes=len(file_bytes),
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            document_type=DocumentType.UNKNOWN,
            status=DocumentStatus.UPLOADED
        )

        # Process through the unified pipeline
        job = IngestionPipelineService.process_document(doc)

        assert job.stage == 'COMPLETED'
        assert doc.status == DocumentStatus.VERIFIED

        # 1. Verify Trial Balance populated
        tb = self.engagement.trial_balances.first()
        assert tb is not None, "Trial Balance must be generated"
        assert tb.total_debits > Decimal('0.00')
        assert tb.total_credits > Decimal('0.00')

        # 2. Verify Fixed Assets imported & Schedule II depreciation recalculated
        assets = FixedAsset.objects.filter(engagement=self.engagement)
        assert assets.count() > 100, f"Expected >100 assets, found {assets.count()}"
        total_gross = sum((a.original_cost for a in assets), Decimal('0.00'))
        assert total_gross > Decimal('50000000.00')

        # Verify AJE-01 auto-drafted for depreciation variance
        aje = ProposedAdjustment.objects.filter(engagement=self.engagement, adjustment_number="AJE-01").first()
        assert aje is not None, "AJE-01 must be automatically drafted for depreciation variance"
        assert aje.status == AdjustmentStatus.PROPOSED
        assert aje.total_debit > Decimal('0.00')

        # 3. Verify Subledger Aging & MSME Section 43B(h) scrutiny
        aging_items = SubledgerAgingItem.objects.filter(engagement=self.engagement)
        assert aging_items.count() > 100, f"Expected >100 subledger items, found {aging_items.count()}"
        msme_items = aging_items.filter(is_msme=True)
        assert msme_items.exists(), "Must identify MSME counterparties"

        # 4. Verify Bank Reconciliation executed
        brs_run = ReconciliationRun.objects.filter(engagement=self.engagement, recon_type='BANK').first()
        assert brs_run is not None, "Bank reconciliation must be executed automatically"
        assert brs_run.total_target_items > 0, "Bank statement transactions must be tracked"

        # 5. Verify SA 230 Workpapers generated with live evidence
        wps = Workpaper.objects.filter(engagement=self.engagement)
        assert wps.count() >= 13, f"Expected at least 13 standard workpapers, found {wps.count()}"

    def test_partner_batch_authorize_eliminates_repetitive_clicks(self):
        """
        Tests the streamlined partner_batch_authorize endpoint which allows the CA partner
        to review and authorize all workpapers in one click without 17 manual steps.
        """
        # Create 17 workpapers in READY_FOR_REVIEW status
        for idx in range(1, 18):
            Workpaper.objects.create(
                engagement=self.engagement,
                wp_reference=f"WP-{idx:03d}",
                title=f"Audit Area {idx}",
                audit_area=f"Area {idx}",
                audit_objective="Verify financial assertion",
                status=WorkpaperStatus.READY_FOR_REVIEW
            )

        view = WorkpaperViewSet.as_view({'post': 'partner_batch_authorize'})
        request = self.factory.post(
            '/api/reporting/workpapers/partner_batch_authorize/',
            {'engagement_id': self.engagement.id, 'reason': "Engagement partner final statutory review completed."},
            format='json'
        )
        response = view(request)

        assert response.status_code == 200
        assert response.data['authorized_count'] == 17
        assert response.data['skipped_count'] == 0

        # Verify all workpapers in DB now have PARTNER_AUTHORIZED status
        all_wps = Workpaper.objects.filter(engagement=self.engagement)
        for wp in all_wps:
            assert wp.status == WorkpaperStatus.PARTNER_AUTHORIZED
            assert wp.approval_reason == "Engagement partner final statutory review completed."
            assert wp.approved_at is not None

    def test_proposed_adjustment_batch_approve_and_post(self):
        """
        Tests batch approving and posting proposed adjustments to ledger in one click,
        resolving linked exception items.
        """
        exc = ExceptionItem.objects.create(
            engagement=self.engagement,
            rule_code="RULE_DEPRECIATION_VARIANCE",
            title="Depreciation Recalculation Variance",
            explanation="Schedule II depreciation variance of Rs. 1.5 Cr",
            amount_involved=Decimal('15000000.00'),
            status=ExceptionStatus.AJE_PROPOSED
        )

        aje = ProposedAdjustment.objects.create(
            engagement=self.engagement,
            adjustment_number="AJE-01",
            title="Depreciation Adjustment",
            reason="Schedule II recalculation",
            total_debit=Decimal('15000000.00'),
            total_credit=Decimal('15000000.00'),
            status=AdjustmentStatus.PROPOSED,
            is_posted=False
        )

        view = ProposedAdjustmentViewSet.as_view({'post': 'batch_approve_and_post'})
        request = self.factory.post(
            '/api/reporting/proposed-adjustments/batch_approve_and_post/',
            {'engagement_id': self.engagement.id},
            format='json'
        )
        response = view(request)

        assert response.status_code == 200
        assert response.data['posted_count'] == 1

        aje.refresh_from_db()
        assert aje.status == AdjustmentStatus.POSTED
        assert aje.is_posted is True
        assert aje.posted_at is not None

        exc.refresh_from_db()
        assert exc.status == ExceptionStatus.AJE_POSTED

    def test_scanned_pdf_or_image_without_ocr_fails_safe_with_clear_guidance(self):
        """
        Tests that when an unreadable/scanned image or empty PDF is uploaded,
        the system does NOT produce fake numbers or silently pretend it succeeded;
        it sets REVIEW_REQUIRED and provides explicit guidance to upload digital exports.
        """
        empty_pdf = SimpleUploadedFile(
            name="scanned_statement.pdf",
            content=b"%PDF-1.4\n%EOF",
            content_type="application/pdf"
        )
        doc = Document.objects.create(
            engagement=self.engagement,
            original_filename="scanned_statement.pdf",
            file=empty_pdf,
            file_hash="mock_empty_scanned_pdf_hash",
            file_size_bytes=14,
            mime_type="application/pdf",
            document_type=DocumentType.UNKNOWN,
            status=DocumentStatus.UPLOADED
        )

        job = IngestionPipelineService.process_document(doc)

        assert job.stage == 'COMPLETED_WITH_WARNINGS'
        doc.refresh_from_db()
        assert doc.status == DocumentStatus.REVIEW_REQUIRED
        assert "Scanned image/PDF without digital text layer detected" in doc.error_message
        assert "Tally, SAP, Zoho Books, Busy, or QuickBooks" in doc.error_message
