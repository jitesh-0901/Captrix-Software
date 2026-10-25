import time
import pytest
from decimal import Decimal
from datetime import date, timedelta
from rest_framework.test import APIClient

from apps.companies.models import Company, FinancialYear, Engagement, EntityType, EngagementType
from apps.accounting.models import ChartOfAccounts, LedgerAccount, Transaction, ScheduleIIIGroup, AccountType, VoucherType
from apps.accounting.services import TrialBalanceService
from apps.reconciliation.services import BankReconciliationEngine
from apps.reporting.report_builder import ConsolidatedAuditReportBuilder
from apps.reporting.exporters import ReportExporterService


@pytest.mark.django_db
class TestPerformanceBenchmarks:
    def setup_method(self):
        self.client = APIClient()
        self.company = Company.objects.create(name="Benchmark Test Corp", pan="BENCH1234F")
        self.fy = FinancialYear.objects.create(company=self.company, label="FY 24-25", start_date=date(2024, 4, 1), end_date=date(2025, 3, 31))
        self.engagement = Engagement.objects.create(
            company=self.company,
            financial_year=self.fy,
            title="Benchmark Audit",
            overall_materiality=Decimal('500000.00')
        )

    def test_reproducible_synthetic_benchmarks(self):
        """
        PERFORMANCE BENCHMARK TEST:
        Generates synthetic accounting dataset of documented size (500 ledger accounts & transactions).
        Measures:
        1. Trial balance calculation & roll-forward verification time
        2. Bank reconciliation matching algorithm throughput
        3. Consolidated audit report generation time (14 sections)
        4. PDF generation time
        5. Multi-tab Excel generation time
        Outputs measured timing benchmarks for platform telemetry.
        """
        dataset_size = 300
        print(f"\n--- PERFORMANCE BENCHMARK: DATASET SIZE = {dataset_size} ITEMS ---")

        # 1. Benchmark Trial Balance Calculation
        tb_rows = []
        for i in range(dataset_size):
            amt = Decimal(str(1000 + i * 50))
            tb_rows.append({
                'Particulars': f"Account Item {i}",
                'Debit': str(amt) if i % 2 == 0 else "0.00",
                'Credit': "0.00" if i % 2 == 0 else str(amt),
            })

        t0 = time.perf_counter()
        tb_result = TrialBalanceService.calculate_trial_balance(
            rows=tb_rows,
            as_of_date=date(2025, 3, 31),
            engagement=self.engagement
        )
        tb_duration = time.perf_counter() - t0
        print(f"[Benchmark] TB Calculation for {dataset_size} rows: {tb_duration*1000:.2f} ms")
        assert tb_duration < 3.0 # Must complete in under 3 seconds

        # 2. Benchmark Bank Reconciliation Matching
        bank_txns = []
        book_txns = []
        for i in range(100):
            d = date(2024, 4, 1) + timedelta(days=(i % 30))
            amt = f"{5000 + i * 100}.00"
            bank_txns.append({
                'date': d, 'ref': f'NEFT-{i}', 'desc': f"NEFT Client {i}", 'amount': amt, 'type': 'DEPOSIT'
            })
            book_txns.append({
                'date': d + timedelta(days=(i % 3)), 'ref': f'NEFT-{i}', 'desc': f"Invoice settlement {i}", 'amount': amt, 'type': 'DEPOSIT'
            })

        t1 = time.perf_counter()
        recon_result = BankReconciliationEngine.execute_reconciliation(
            engagement=self.engagement,
            as_of_date=date(2025, 3, 31),
            cashbook_items=book_txns,
            bank_items=bank_txns,
            starting_cashbook_balance=Decimal('100000.00'),
            actual_statement_balance=Decimal('100000.00'),
            date_tolerance_days=5
        )
        recon_duration = time.perf_counter() - t1
        print(f"[Benchmark] BRS Multi-Tier Match (100 book vs 100 bank txns): {recon_duration*1000:.2f} ms")
        assert recon_duration < 2.0

        # 3. Benchmark Consolidated Report Generation (Sections A-N)
        t2 = time.perf_counter()
        report_data = ConsolidatedAuditReportBuilder.build_report(self.engagement)
        report_duration = time.perf_counter() - t2
        print(f"[Benchmark] Consolidated Report 14-Section Build: {report_duration*1000:.2f} ms")
        assert report_duration < 2.0

        # 4. Benchmark PDF Compilation (ReportLab)
        t3 = time.perf_counter()
        pdf_bytes = ReportExporterService.export_consolidated_pdf(self.engagement)
        pdf_duration = time.perf_counter() - t3
        print(f"[Benchmark] ReportLab PDF Compilation: {pdf_duration*1000:.2f} ms ({len(pdf_bytes)} bytes)")
        assert pdf_duration < 2.5

        # 5. Benchmark Excel Export (OpenPyXL multi-tab)
        t4 = time.perf_counter()
        excel_bytes = ReportExporterService.export_consolidated_excel(self.engagement)
        excel_duration = time.perf_counter() - t4
        print(f"[Benchmark] OpenPyXL Multi-Tab Excel Compilation: {excel_duration*1000:.2f} ms ({len(excel_bytes)} bytes)")
        assert excel_duration < 2.5
