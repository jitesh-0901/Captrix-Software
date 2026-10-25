import os
import zipfile
import hashlib
from decimal import Decimal
from django.test import TestCase
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status

from apps.companies.models import Company, FinancialYear, Engagement, EntityType, EngagementType
from apps.ingestion.models import ProcessingRun, ProcessingRunStage, ProcessingRunStatus, Document
from apps.ingestion.orchestrator import AutomationOrchestratorService, ALL_STAGES


class AutomationOrchestratorTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.test_data_dir = os.path.join(settings.BASE_DIR, 'test_data', 'synthetic_company')
        os.environ['ALLOW_SYNTHETIC_DEMO'] = '1'

    def _get_synthetic_files(self):
        file_names = [
            'trial_balance_fy24_25.csv',
            'general_ledger_dump.csv',
            'bank_statement_fy24_25.csv',
            'gstr_2b_itc_statement.csv',
            'purchase_register.csv',
            'fixed_asset_register.csv',
            'subledger_debtors_creditors.csv',
        ]
        files = []
        for name in file_names:
            path = os.path.join(self.test_data_dir, name)
            if os.path.exists(path):
                with open(path, 'rb') as f:
                    files.append(SimpleUploadedFile(name, f.read(), content_type='text/csv'))
        return files

    def test_orchestrator_create_run(self):
        """Verify initial run creation, stage initialization, and metadata structure."""
        company = Company.objects.create(name="Apex Systems Ltd", pan="AABCA1234F")
        fy = company.financial_years.create(label="FY 2024-25", start_date="2024-04-01", end_date="2025-03-31")
        eng = Engagement.objects.create(company=company, financial_year=fy, title="Statutory Audit FY 2024-25")

        run = AutomationOrchestratorService.create_run(
            files=[],
            company_name=company.name,
            financial_year_label="FY 2024-25",
            engagement_id=eng.id
        )

        self.assertIsNotNone(run.run_id)
        self.assertTrue(run.run_id.startswith("RUN-"))
        self.assertEqual(run.status, ProcessingRunStatus.QUEUED)
        self.assertEqual(run.current_stage, ProcessingRunStage.UPLOAD_RECEIVED)
        self.assertEqual(run.progress_percent, 0)
        self.assertEqual(len(run.stage_statuses), 14)
        for stage in ALL_STAGES:
            self.assertIn(stage, run.stage_statuses)
            self.assertEqual(run.stage_statuses[stage]['status'], 'PENDING')

    def test_orchestrator_full_14_stage_pipeline_synthetic_dataset(self):
        """Execute full 14-stage pipeline on verified synthetic company files."""
        uploaded_files = self._get_synthetic_files()
        self.assertGreaterEqual(len(uploaded_files), 5, "Synthetic files should be present")

        # 1. Create run
        run = AutomationOrchestratorService.create_run(
            files=uploaded_files,
            company_name="Vanguard Industrial Automations Private Limited",
            financial_year_label="FY 2024-25"
        )

        # 2. Execute pipeline
        completed_run = AutomationOrchestratorService.execute_pipeline(
            run=run,
            uploaded_files=uploaded_files,
            company_hint="Vanguard Industrial Automations Private Limited",
            fy_hint="FY 2024-25"
        )

        # 3. Assertions on status and progress (status can be COMPLETED or REVIEW_REQUIRED if MSME 43B(h) / audit exceptions exist)
        self.assertIn(completed_run.status, [ProcessingRunStatus.COMPLETED, ProcessingRunStatus.REVIEW_REQUIRED])
        self.assertEqual(completed_run.current_stage, ProcessingRunStage.COMPLETED)
        self.assertEqual(completed_run.progress_percent, 100)

        # 4. Check all 14 stages completed
        for stage in ALL_STAGES:
            st_info = completed_run.stage_statuses.get(stage)
            self.assertIsNotNone(st_info, f"Missing stage status for {stage}")
            self.assertEqual(st_info['status'], 'COMPLETED', f"Stage {stage} did not complete: {st_info}")

        # 5. Check documents ingested with cryptographic hashes
        docs = completed_run.documents.all()
        self.assertEqual(docs.count(), len(uploaded_files))
        for doc in docs:
            self.assertIsNotNone(doc.file_hash)
            self.assertEqual(len(doc.file_hash), 64, "SHA-256 hash must be 64 hex characters")
            self.assertGreater(doc.file_size_bytes, 0)

        # 6. Check Trial Balance calculation
        tb_balanced = completed_run.summary_metrics.get('tb_balanced')
        self.assertTrue(tb_balanced, "Trial Balance must be mathematically balanced")

        # 7. Check ZIP package generation and content
        self.assertIsNotNone(completed_run.zip_package)
        self.assertTrue(os.path.exists(completed_run.zip_package.path))
        self.assertIsNotNone(completed_run.zip_package_hash)
        self.assertEqual(len(completed_run.zip_package_hash), 64)

        # Verify ZIP contains expected files
        with zipfile.ZipFile(completed_run.zip_package.path, 'r') as zf:
            namelist = zf.namelist()
            self.assertIn("Consolidated_Audit_Report.pdf", namelist)
            self.assertIn("Consolidated_Audit_Schedules.xlsx", namelist)
            self.assertIn("Financial_Summary_Extract.csv", namelist)
            self.assertIn("Source_Evidence_Index.json", namelist)
            self.assertIn("Audit_Run_Manifest.json", namelist)

    def test_orchestrator_original_file_immutability(self):
        """Verify original uploaded files are not mutated during processing."""
        sample_content = b"Account Code,Particulars,Classification,Debit (INR),Credit (INR)\n1001,Capital,EQUITY,0.00,1000.00\n"
        expected_hash = hashlib.sha256(sample_content).hexdigest()
        sample_file = SimpleUploadedFile("test_tb.csv", sample_content, content_type="text/csv")

        run = AutomationOrchestratorService.create_run(files=[sample_file])
        run = AutomationOrchestratorService.execute_pipeline(run=run, uploaded_files=[sample_file])

        doc = run.documents.first()
        self.assertIsNotNone(doc)
        self.assertEqual(doc.file_hash, expected_hash)

        # Read directly from disk to confirm byte-for-byte immutability
        with open(doc.file.path, 'rb') as f_read:
            disk_content = f_read.read()
            self.assertEqual(disk_content, sample_content)
            self.assertEqual(hashlib.sha256(disk_content).hexdigest(), expected_hash)

    def test_orchestrator_empty_file_validation_fails_closed(self):
        """Verify that zero-byte files cause the pipeline to fail closed at validation."""
        empty_file = SimpleUploadedFile("empty.csv", b"", content_type="text/csv")

        # API should reject empty file with HTTP 400
        response = self.client.post('/api/ingestion/runs/', {'files': [empty_file]}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('empty', response.data.get('error', '').lower())

    def test_api_run_synthetic_demo(self):
        """Verify 1-click synthetic acceptance demo API endpoint."""
        response = self.client.post('/api/ingestion/runs/run_synthetic_demo/')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        data = response.data
        self.assertIn('run_id', data)
        self.assertIn(data['status'], [ProcessingRunStatus.COMPLETED, ProcessingRunStatus.REVIEW_REQUIRED])
        self.assertEqual(data['progress_percent'], 100)
        self.assertGreaterEqual(len(data.get('documents', [])), 5)
        self.assertIn('zip_package_url', data)

    def test_api_history_and_download(self):
        """Verify past runs list and .ZIP download package endpoints."""
        # 1. Trigger synthetic demo to create a completed run
        run_res = self.client.post('/api/ingestion/runs/run_synthetic_demo/')
        self.assertEqual(run_res.status_code, status.HTTP_201_CREATED)
        run_id = run_res.data['run_id']

        # 2. Test GET /api/ingestion/runs/
        history_res = self.client.get('/api/ingestion/runs/')
        self.assertEqual(history_res.status_code, status.HTTP_200_OK)
        results = history_res.data.get('results', history_res.data)
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]['run_id'], run_id)

        # 3. Test GET /api/ingestion/runs/{run_id}/
        retrieve_res = self.client.get(f'/api/ingestion/runs/{run_id}/')
        self.assertEqual(retrieve_res.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieve_res.data['run_id'], run_id)

        # 4. Test GET /api/ingestion/runs/{run_id}/download_package/
        download_res = self.client.get(f'/api/ingestion/runs/{run_id}/download_package/')
        self.assertEqual(download_res.status_code, status.HTTP_200_OK)
        self.assertEqual(download_res['Content-Type'], 'application/zip')
        self.assertIn(f"Captrix_Audit_Package_{run_id}.zip", download_res['Content-Disposition'])

    def test_synthetic_demo_environment_guard(self):
        """Verify synthetic demo endpoint is blocked when DEBUG=False and ALLOW_SYNTHETIC_DEMO is not set."""
        with self.settings(DEBUG=False):
            old_env = os.environ.get('ALLOW_SYNTHETIC_DEMO')
            if 'ALLOW_SYNTHETIC_DEMO' in os.environ:
                del os.environ['ALLOW_SYNTHETIC_DEMO']
            try:
                response = self.client.post('/api/ingestion/runs/run_synthetic_demo/')
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
                self.assertIn('restricted', response.data.get('error', '').lower())
            finally:
                if old_env is not None:
                    os.environ['ALLOW_SYNTHETIC_DEMO'] = old_env

    def test_unbalanced_trial_balance_records_exception(self):
        """Verify that an unbalanced trial balance does not synthesize fake balancing and raises an exception."""
        unbalanced_tb = (
            "Account Code,Particulars,Classification,Debit (INR),Credit (INR)\n"
            "1001,Capital Account,EQUITY,0.00,500000.00\n"
            "2001,HDFC Current Bank Account,ASSET,450000.00,0.00\n"
        ).encode('utf-8')
        tb_file = SimpleUploadedFile("trial_balance.csv", unbalanced_tb, content_type="text/csv")

        run = AutomationOrchestratorService.create_run(
            files=[tb_file],
            company_name="Zeta Logistics Private Limited",
            financial_year_label="FY 2024-25"
        )
        completed_run = AutomationOrchestratorService.execute_pipeline(
            run=run,
            uploaded_files=[tb_file],
            company_hint="Zeta Logistics Private Limited",
            fy_hint="FY 2024-25"
        )

        self.assertEqual(completed_run.summary_metrics.get('tb_balanced'), False)
        # Should record an exception for trial balance mismatch
        exceptions = completed_run.engagement.exceptions.all()
        tb_exceptions = [e for e in exceptions if 'trial balance' in e.title.lower() or 'trial balance' in e.explanation.lower()]
        self.assertGreaterEqual(len(tb_exceptions), 1)

    def test_real_company_upload_isolation_from_demo_data(self):
        """Verify that real client uploads remain strictly isolated and do not inherit synthetic flags or fixtures."""
        clean_tb = (
            "Account Code,Particulars,Classification,Debit (INR),Credit (INR)\n"
            "1001,Share Capital,EQUITY,0.00,100000.00\n"
            "2001,Bank Account,ASSET,100000.00,0.00\n"
        ).encode('utf-8')
        clean_file = SimpleUploadedFile("clean_tb.csv", clean_tb, content_type="text/csv")

        run = AutomationOrchestratorService.create_run(
            files=[clean_file],
            company_name="Nova Tech Innovations Private Limited",
            financial_year_label="FY 2024-25"
        )
        completed_run = AutomationOrchestratorService.execute_pipeline(
            run=run,
            uploaded_files=[clean_file],
            company_hint="Nova Tech Innovations Private Limited",
            fy_hint="FY 2024-25"
        )

        self.assertEqual(completed_run.company.name, "Nova Tech Innovations Private Limited")
        self.assertFalse(completed_run.summary_metrics.get('is_synthetic_test_data', False))
        self.assertNotIn("[TEST DEMO]", completed_run.company.name)
        self.assertNotIn("Vanguard", completed_run.company.name)

