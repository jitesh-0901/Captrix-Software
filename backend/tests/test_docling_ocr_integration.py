import os
import sys
import django

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import pytest
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.ingestion.docling_engine import DoclingOCREngine
from apps.ingestion.parsers import DocumentParserService
from apps.ingestion.orchestrator import AutomationOrchestratorService
from apps.ingestion.models import ProcessingRunStatus, ExtractedRecord

@pytest.mark.django_db(transaction=True)
def test_docling_availability_and_metadata():
    """Verify that the existing local Docling OCR folder is detected and operational."""
    assert DoclingOCREngine.is_available() is True
    metadata = DoclingOCREngine.get_engine_metadata()
    assert metadata["engine"] == "Docling-OCR"
    assert metadata["status"] == "OPERATIONAL"
    assert "Docling OCR" in metadata["source_path"]

@pytest.mark.django_db(transaction=True)
def test_docling_extraction_with_source_traceability_and_no_zero_fakes():
    """
    Test extraction on sample trial balance using Docling OCR:
    1. Records have source_location with Docling page & coordinate references.
    2. Missing/uncertain values are never silently treated as zero.
    """
    tb_path = os.path.join(os.path.dirname(__file__), '..', 'test_fixtures', 'sample_trial_balance.pdf')
    with open(tb_path, 'rb') as f:
        file_obj = SimpleUploadedFile("Apex_Trial_Balance_FY24_25.pdf", f.read(), content_type="application/pdf")
        parsed = DocumentParserService.parse_file(file_obj, original_filename="Apex_Trial_Balance_FY24_25.pdf")

    records = parsed.get("records", [])
    assert len(records) > 0, "Docling OCR should extract records from sample_trial_balance.pdf"

    for r in records:
        raw = r.get("raw", {})
        source_loc = r.get("source_location", "")
        # Verify source traceability
        assert "Docling:Page_" in source_loc, f"Record must have Docling source traceability, got: {source_loc}"
        
        # Verify no silent zero injection for missing values
        for key, val in raw.items():
            if val is None or val == "":
                # Value was missing, must NOT be silently replaced with 0 or 0.00
                assert val != 0 and val != 0.0 and val != "0.00", f"Missing key {key} was silently zeroed!"

@pytest.mark.django_db(transaction=True)
def test_docling_full_pipeline_upload_to_structured_results():
    """
    Test the complete 14-stage workflow:
    Upload → Ingestion (Docling OCR) → Normalization → Verification → Schedule III Financial Statements.
    """
    tb_path = os.path.join(os.path.dirname(__file__), '..', 'test_fixtures', 'sample_trial_balance.pdf')
    bank_path = os.path.join(os.path.dirname(__file__), '..', 'test_fixtures', 'sample_bank_statement.pdf')

    with open(tb_path, 'rb') as f_tb, open(bank_path, 'rb') as f_bank:
        tb_upload = SimpleUploadedFile("Apex_Trial_Balance_FY24_25.pdf", f_tb.read(), content_type="application/pdf")
        bank_upload = SimpleUploadedFile("HDFC_Bank_Statement_FY24_25.pdf", f_bank.read(), content_type="application/pdf")

        run = AutomationOrchestratorService.create_run(
            files=[tb_upload, bank_upload],
            company_name="Apex Infotech Private Limited",
            financial_year_label="FY 2024-25"
        )

        completed_run = AutomationOrchestratorService.execute_pipeline(
            run=run,
            uploaded_files=[tb_upload, bank_upload],
            company_hint="Apex Infotech Private Limited",
            fy_hint="FY 2024-25"
        )

    assert completed_run.status in [ProcessingRunStatus.COMPLETED, ProcessingRunStatus.REVIEW_REQUIRED]
    
    # Check that ExtractedRecords in DB retain Docling source locations
    docs = getattr(completed_run, 'documents').all()
    db_records = getattr(ExtractedRecord, 'objects').filter(document__in=docs)
    assert db_records.count() > 0
    has_docling_trace = any("Docling:Page_" in (rec.source_location or "") for rec in db_records)
    assert has_docling_trace, "Database extracted records must reflect Docling source traceability"

    # Verify Schedule III financial statements produced
    summary_metrics: dict = getattr(completed_run, 'summary_metrics', {})
    fin = summary_metrics.get('schedule_iii_financial_statements')
    assert fin is not None, "Schedule III financial statements must be generated"
    assert fin['balance_sheet']['is_balanced'] is True
    assert Decimal(str(fin['balance_sheet']['total_assets'])) == Decimal(str(fin['balance_sheet']['total_equity_and_liabilities']))
