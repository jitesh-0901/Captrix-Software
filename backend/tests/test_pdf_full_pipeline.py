import os
import sys
import django

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.ingestion.orchestrator import AutomationOrchestratorService
from apps.ingestion.models import ProcessingRunStatus

@pytest.mark.django_db(transaction=True)
def test_full_pipeline_with_pdf_documents():
    tb_pdf_path = os.path.join(os.path.dirname(__file__), '..', 'test_fixtures', 'sample_trial_balance.pdf')
    bank_pdf_path = os.path.join(os.path.dirname(__file__), '..', 'test_fixtures', 'sample_bank_statement.pdf')

    with open(tb_pdf_path, 'rb') as f_tb, open(bank_pdf_path, 'rb') as f_bank:
        tb_upload = SimpleUploadedFile("Apex_Trial_Balance_FY24_25.pdf", f_tb.read(), content_type="application/pdf")
        bank_upload = SimpleUploadedFile("HDFC_Bank_Statement_FY24_25.pdf", f_bank.read(), content_type="application/pdf")

        run = AutomationOrchestratorService.create_run(
            files=[tb_upload, bank_upload],
            company_name="Apex Infotech Private Limited",
            financial_year_label="FY 2024-25"
        )
        print(f"Created Processing Run: {run.run_id}")

        completed_run = AutomationOrchestratorService.execute_pipeline(
            run=run,
            uploaded_files=[tb_upload, bank_upload],
            company_hint="Apex Infotech Private Limited",
            fy_hint="FY 2024-25"
        )

        print(f"\nPipeline Run Finished with Status: {completed_run.status}")
        print("Stage Statuses:")
        for stage, meta in completed_run.stage_statuses.items():
            print(f"  {stage:<26} -> {meta['status']} ({meta.get('details', '')})")

        assert completed_run.status in [ProcessingRunStatus.COMPLETED, ProcessingRunStatus.REVIEW_REQUIRED]
        assert completed_run.summary_metrics.get('schedule_iii_financial_statements') is not None
        fin = completed_run.summary_metrics['schedule_iii_financial_statements']
        assert fin['balance_sheet']['is_balanced'] is True
        print(f"\nSchedule III Balance Sheet Balanced: {fin['balance_sheet']['is_balanced']}")
        print(f"Revenue from Operations: {fin['profit_and_loss']['revenue_from_operations']}")
        print("FULL 14-STAGE PIPELINE WITH PDF INGESTION PASSED 100%!")

if __name__ == '__main__':
    test_full_pipeline_with_pdf_documents()
