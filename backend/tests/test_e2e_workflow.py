import os
import pytest
from rest_framework.test import APIClient
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.companies.models import Company, FinancialYear, Engagement
from apps.ingestion.models import Document, DocumentStatus, DocumentType

@pytest.mark.django_db
def test_e2e_document_upload_and_extraction_pipeline():
    """End-to-End test uploading sample Trial Balance Excel file via REST API and inspecting extracted records"""
    client = APIClient()

    company = Company.objects.create(name="E2E Corp", pan="ABCDE1234F")
    fy = FinancialYear.objects.create(company=company, label="FY 24-25", start_date="2024-04-01", end_date="2025-03-31")
    eng = Engagement.objects.create(company=company, financial_year=fy, title="E2E Audit")

    from django.conf import settings
    sample_path = os.path.join(settings.BASE_DIR.parent, "samples", "Apex_Infotech_Trial_Balance_FY24_25.xlsx")
    if not os.path.exists(sample_path):
        sample_path = os.path.join(settings.BASE_DIR, "samples", "Apex_Infotech_Trial_Balance_FY24_25.xlsx")
    assert os.path.exists(sample_path)

    with open(sample_path, "rb") as f:
        uploaded_file = SimpleUploadedFile(
            name="Apex_Infotech_Trial_Balance_FY24_25.xlsx",
            content=f.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    response = client.post(
        "/api/ingestion/documents/",
        {
            "engagement": eng.id,
            "document_type": DocumentType.TRIAL_BALANCE,
            "file": uploaded_file
        },
        format="multipart"
    )

    assert response.status_code == 201
    doc_id = response.data["id"]
    doc = Document.objects.get(id=doc_id)

    # 1. Verify SHA-256 hash was generated
    assert len(doc.file_hash) == 64
    assert doc.status in [DocumentStatus.VERIFIED, DocumentStatus.REVIEW_REQUIRED]

    # 2. Verify extracted records and source locations
    records = doc.extracted_records.all()
    assert records.count() > 10

    first_rec = records.first()
    assert "Row_" in first_rec.source_location
    assert first_rec.validation_status == "VALID"
    assert first_rec.confidence_score >= 0.90

    # 3. Test duplicate upload warning
    with open(sample_path, "rb") as f:
        dup_file = SimpleUploadedFile(
            name="Apex_Infotech_Trial_Balance_FY24_25.xlsx",
            content=f.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    dup_resp = client.post(
        "/api/ingestion/documents/",
        {
            "engagement": eng.id,
            "file": dup_file
        },
        format="multipart"
    )
    assert dup_resp.status_code == 201
    assert dup_resp.data["is_duplicate_hash"] is True
    assert "Warning: Exact duplicate" in dup_resp.data["duplicate_warning"]
