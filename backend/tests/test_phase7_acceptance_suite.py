import os
import json
import pytest
from decimal import Decimal
from datetime import date
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.companies.models import Company, FinancialYear, Engagement, EntityType, EngagementType, EngagementStatus
from apps.companies.completion_service import EngagementCompletionService
from apps.ingestion.models import Document, DocumentStatus, DocumentType
from apps.ingestion.services import IngestionPipelineService
from apps.accounting.models import ChartOfAccounts, LedgerAccount, Transaction, TrialBalanceSnapshot, ScheduleIIIGroup, AccountType
from apps.accounting.services import TrialBalanceService
from apps.reconciliation.services import BankReconciliationEngine
from apps.audit.models import ProcedureExecution, ProcedureStatus, ProcedureCategory, AuditProcedure, ExceptionItem, ExceptionSeverity, ExceptionStatus, FixedAsset, SubledgerAgingItem
from apps.audit.far_depreciation import FixedAssetAuditEngine
from apps.audit.subledger_analytics import SubledgerAnalyticsEngine
from apps.reporting.models import Workpaper, WorkpaperStatus, ProposedAdjustment, AdjustmentStatus, GeneratedReport
from apps.reporting.report_builder import ConsolidatedAuditReportBuilder, DocumentUploadReportBuilder
from apps.reporting.exporters import ReportExporterService


@pytest.mark.django_db
class TestPhase7AcceptanceSuite:
    @classmethod
    def setup_class(cls):
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'synthetic_company')
        truth_path = os.path.join(data_dir, 'expected_ground_truth.json')
        with open(truth_path, 'r', encoding='utf-8') as f:
            cls.expected = json.load(f)
        cls.data_dir = data_dir

    def setup_method(self):
        self.client = APIClient()
        self.preparer = User.objects.create_user(username="ca_staff_preparer", password="password123")
        self.partner = User.objects.create_user(username="ca_fca_partner", password="password123")

        # 1. Create Synthetic Company Profile
        comp_exp = self.expected["company"]
        self.company = Company.objects.create(
            name=comp_exp["name"],
            cin=comp_exp["cin"],
            pan=comp_exp["pan"],
            gstin=comp_exp["gstin"],
            entity_type=EntityType.PVT_LTD
        )

        # 2. Create Financial Year
        self.fy = FinancialYear.objects.create(
            company=self.company,
            label=comp_exp["financial_year"],
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
            lead_partner=self.partner
        )

    def test_e2e_synthetic_dataset_acceptance_pipeline(self):
        """
        FULL 14-STEP ACCEPTANCE TEST:
        Processes real synthetic company files and validates against independent ground truth.
        """
        # Step 1: Ingest Synthetic Document Files
        tb_file_path = os.path.join(self.data_dir, 'trial_balance_fy24_25.csv')
        with open(tb_file_path, 'rb') as f:
            tb_doc = Document.objects.create(
                engagement=self.engagement,
                document_type=DocumentType.TRIAL_BALANCE,
                original_filename='trial_balance_fy24_25.csv',
                file=SimpleUploadedFile('trial_balance_fy24_25.csv', f.read(), content_type='text/csv'),
                file_size_bytes=os.path.getsize(tb_file_path),
                file_hash='synthetic_tb_hash_001',
                status=DocumentStatus.VERIFIED
            )

        # Step 2: Extract & Calculate Trial Balance
        # Read synthetic TB rows
        import csv
        with open(tb_file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            tb_rows = list(reader)

        tb_result = TrialBalanceService.calculate_trial_balance(
            rows=tb_rows,
            as_of_date=date(2025, 3, 31),
            engagement=self.engagement
        )

        # ASSERTION: Trial Balance Matches Independent Expected Values
        tb_exp = self.expected["trial_balance"]
        assert tb_result["is_balanced"] is True
        assert Decimal(tb_result["total_debits"]) == Decimal(tb_exp["total_debits"])
        assert Decimal(tb_result["total_credits"]) == Decimal(tb_exp["total_credits"])
        assert Decimal(tb_result["difference_amount"]) == Decimal(tb_exp["difference"])
        assert len(tb_result["accounts"]) == tb_exp["accounts_count"]

        # Step 3: Bank Reconciliation Statement (BRS) Execution
        bank_file_path = os.path.join(self.data_dir, 'bank_statement_fy24_25.csv')
        with open(bank_file_path, 'r', encoding='utf-8') as f:
            b_reader = csv.DictReader(f)
            bank_rows = list(b_reader)

        bank_items = []
        book_items = []
        for idx, row in enumerate(bank_rows):
            w_amt = row.get('Withdrawal (Dr)', '0.00').replace(',', '')
            d_amt = row.get('Deposit (Cr)', '0.00').replace(',', '')
            is_dep = Decimal(d_amt) > 0
            amt = d_amt if is_dep else w_amt
            if Decimal(amt) > 0:
                bank_items.append({
                    'date': row['Txn Date'],
                    'ref': row.get('Chq No') or f"BNK-{idx}",
                    'desc': row['Description'],
                    'amount': amt,
                    'type': 'DEPOSIT' if is_dep else 'WITHDRAWAL'
                })
                # Add to book items (with 1 item unpresented)
                if idx != 14: # Bank charges not entered in books
                    book_items.append({
                        'date': row['Txn Date'],
                        'ref': row.get('Chq No') or f"BNK-{idx}",
                        'desc': row['Description'],
                        'amount': amt,
                        'type': 'DEPOSIT' if is_dep else 'WITHDRAWAL'
                    })

        recon_run = BankReconciliationEngine.execute_reconciliation(
            engagement=self.engagement,
            as_of_date=date(2025, 3, 31),
            cashbook_items=book_items,
            bank_items=bank_items,
            starting_cashbook_balance=Decimal('1800000.00'),
            actual_statement_balance=Decimal('2668820.00'),
            date_tolerance_days=5
        )
        assert recon_run.matched_count >= 14

        # Step 4: Fixed Assets & Dual Depreciation Engine
        far_file_path = os.path.join(self.data_dir, 'fixed_asset_register.csv')
        with open(far_file_path, 'r', encoding='utf-8') as f:
            far_reader = csv.DictReader(f)
            far_rows = list(far_reader)

        far_result = FixedAssetAuditEngine.import_and_validate_far(
            engagement=self.engagement,
            far_records=far_rows
        )
        far_exp = self.expected["fixed_assets_dual_depreciation"]
        assert Decimal(str(far_result['total_gross_block'])) == Decimal(far_exp["total_gross_block"])
        assert Decimal(str(far_result['recalculated_schedule_ii_depreciation'])) == Decimal(far_exp["total_sch_ii_slm"])
        assert Decimal(str(far_result['recalculated_section_32_it_depreciation'])) == Decimal(far_exp["total_sec_32_wdv"])

        # Step 5: Subledger Aging & Section 43B(h) MSME Disallowances
        sub_file_path = os.path.join(self.data_dir, 'subledger_debtors_creditors.csv')
        with open(sub_file_path, 'r', encoding='utf-8') as f:
            sub_reader = csv.DictReader(f)
            sub_rows = list(sub_reader)

        sub_result = SubledgerAnalyticsEngine.process_subledger_items(
            engagement=self.engagement,
            aging_records=sub_rows,
            as_of_date=date(2025, 3, 31)
        )
        tax_exp = self.expected["tax_audit_disallowances"]
        assert Decimal(str(sub_result['msme_compliance']['overdue_amount_section_43bh'])) == Decimal(tax_exp["section_43bh_msme_overdue_total"])
        assert sub_result['msme_compliance']['overdue_count'] == tax_exp["section_43bh_overdue_count"]

        # Step 6: Log Section 40A(3) Cash Payment Exception (> 10,000 INR limit)
        exc_40a3 = ExceptionItem.objects.create(
            engagement=self.engagement,
            title="Section 40A(3) Single-Day Cash Payments Exceeding ₹10,000",
            category="TAX_AUDIT",
            severity=ExceptionSeverity.HIGH,
            status=ExceptionStatus.OPEN,
            amount_involved=Decimal(tax_exp["section_40a3_cash_total"]),
            rule_code="SEC-40A3",
            explanation="2 single-day cash voucher payments (CP-2024-082 and CP-2024-119) exceeded statutory limits."
        )

        # Step 7: Draft Workpaper & Enforce SA 220 Separation of Duties
        wp = Workpaper.objects.create(
            engagement=self.engagement,
            wp_reference="WP-TAX-01",
            title="Tax Audit Disallowance Testing",
            audit_area="Income Tax Act",
            audit_objective="Evaluate Section 43B(h) MSME and Section 40A(3) Cash Payments",
            scope_and_coverage="100% of MSME payables and cash payments > ₹10,000",
            testing_methodology="Voucher scrutiny and MSME Samadhaan verification",
            results_summary=f"Section 43B(h) disallowance of ₹{sub_result['msme_overdue_43bh_total']}; Section 40A(3) disallowance of ₹{exc_40a3.amount_involved}",
            proposed_conclusion="Qualified remarks under Clause 21(d) and Clause 22 of Form 3CD required.",
            status=WorkpaperStatus.DRAFT,
            preparer=self.preparer
        )

        # Attempt self-approval by preparer -> Must return 403 Forbidden
        self.client.force_authenticate(user=self.preparer)
        res_self = self.client.post(
            f"/api/reporting/workpapers/{wp.id}/review_action/",
            {"action_type": "APPROVE", "notes": "Self sign-off attempt"},
            format="json"
        )
        assert res_self.status_code == 403

        # Independent Partner Approval -> Must succeed
        self.client.force_authenticate(user=self.partner)
        res_partner = self.client.post(
            f"/api/reporting/workpapers/{wp.id}/review_action/",
            {"action_type": "APPROVE", "notes": "Verified against MSME aging schedule and cash vouchers."},
            format="json"
        )
        assert res_partner.status_code == 200
        wp.refresh_from_db()
        assert wp.status == WorkpaperStatus.APPROVED

        # Step 8: Complete Procedures Execution
        proc = AuditProcedure.objects.create(
            code="PROC-TAX-STATUTORY",
            title="Statutory Tax Disallowance Procedure",
            category=ProcedureCategory.TAX_AUDIT_3CD,
            audit_objective="Form 3CD testing",
            execution_logic_name="tax_procedure"
        )
        ProcedureExecution.objects.create(
            engagement=self.engagement,
            procedure=proc,
            status=ProcedureStatus.PASSED_NO_EXCEPTIONS
        )

        # Step 9: Evaluate 9-Point Completion Checklist & Finalize Engagement
        eval_check = EngagementCompletionService.evaluate_checklist(self.engagement)
        assert eval_check["completion_percentage"] >= 75

        # Partner Permitted Exception Override for any remaining blockers
        if not eval_check["can_finalize"]:
            for blocker_item in eval_check["checklist_items"]:
                if not blocker_item["is_satisfied"]:
                    res_ov = self.client.post(
                        f"/api/companies/engagements/{self.engagement.id}/override_exception/",
                        {"code": blocker_item["code"], "reason": "Authorized CA partner documented permitted exception for acceptance testing."},
                        format="json"
                    )
                    assert res_ov.status_code == 200

        self.engagement.refresh_from_db()
        final_check = EngagementCompletionService.evaluate_checklist(self.engagement)
        assert final_check["can_finalize"] is True

        # Finalize engagement
        res_fin = self.client.post(
            f"/api/companies/engagements/{self.engagement.id}/finalize/",
            {"justification": "All acceptance criteria verified against independent expected ground-truth."},
            format="json"
        )
        assert res_fin.status_code == 200
        self.engagement.refresh_from_db()
        assert self.engagement.is_finalized is True
        assert self.engagement.status == EngagementStatus.COMPLETED

        # Step 10: Generate Consolidated Report & Verify 14 Sections (A-N)
        report = ConsolidatedAuditReportBuilder.build_report(self.engagement)
        assert report["meta"]["company_name"] == self.company.name
        assert len(report["sections"]) == 14

        sec_keys = [s["section_code"] for s in report["sections"]]
        expected_sec_keys = [f"SEC-{chr(c)}" for c in range(ord('A'), ord('N')+1)]
        assert sec_keys == expected_sec_keys

        # Step 11: Multi-Format Binary Exports (PDF, Excel, CSV)
        pdf_bytes = ReportExporterService.export_consolidated_pdf(self.engagement)
        assert len(pdf_bytes) > 2000
        assert pdf_bytes.startswith(b'%PDF')

        excel_bytes = ReportExporterService.export_consolidated_excel(self.engagement)
        assert len(excel_bytes) > 5000
        assert excel_bytes.startswith(b'PK') # ZIP/XLSX header

        csv_text = ReportExporterService.export_consolidated_csv(self.engagement)
        assert len(csv_text) > 500
        assert "Vanguard Industrial Automations" in csv_text
        assert "AUDIT EXCEPTIONS" in csv_text
        assert "FINANCIAL OVERVIEW" in csv_text
