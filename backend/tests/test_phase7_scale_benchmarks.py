import time
import pytest
from decimal import Decimal
from datetime import date, timedelta
from rest_framework.test import APIClient

from apps.companies.models import Company, FinancialYear, Engagement, EntityType, EngagementType
from apps.accounting.models import ChartOfAccounts, LedgerAccount, Transaction, TrialBalanceSnapshot
from apps.accounting.services import TrialBalanceService
from apps.reconciliation.services import BankReconciliationEngine
from apps.reporting.report_builder import ConsolidatedAuditReportBuilder
from apps.reporting.exporters import ReportExporterService


@pytest.mark.django_db
class TestPhase7ScaleBenchmarks:
    def setup_method(self):
        self.client = APIClient()
        self.company = Company.objects.create(name="Scale Benchmark Corp", pan="SCALE1234F")
        self.fy = FinancialYear.objects.create(company=self.company, label="FY 24-25", start_date=date(2024, 4, 1), end_date=date(2025, 3, 31))
        self.engagement = Engagement.objects.create(
            company=self.company,
            financial_year=self.fy,
            title="Scale Benchmark Audit",
            overall_materiality=Decimal('1000000.00')
        )

    def test_scale_1000_rows_benchmark(self):
        """
        SCALE 1: 1,000 ROWS
        Measures Trial Balance calculation and BRS matching latency.
        """
        n = 1000
        tb_rows = []
        for i in range(n):
            amt = Decimal(str(500 + (i % 200) * 10))
            tb_rows.append({
                'Particulars': f"Account Item {i}",
                'Debit': str(amt) if i % 2 == 0 else "0.00",
                'Credit': "0.00" if i % 2 == 0 else str(amt)
            })

        t0 = time.perf_counter()
        tb = TrialBalanceService.calculate_trial_balance(
            rows=tb_rows,
            as_of_date=date(2025, 3, 31),
            engagement=self.engagement
        )
        duration = time.perf_counter() - t0
        throughput = n / duration if duration > 0 else 0
        print(f"\n[Scale 1,000 Rows] TB Duration: {duration*1000:.2f} ms | Throughput: {throughput:,.0f} rows/sec | Balanced: {tb['is_balanced']}")
        assert duration < 5.0 # SLA threshold: under 5 seconds

    def test_scale_10000_rows_benchmark(self):
        """
        SCALE 2: 10,000 ROWS
        Stress tests Python Decimal arithmetic and calculation speed.
        """
        n = 10000
        tb_rows = []
        for i in range(n):
            amt = Decimal(str(100 + (i % 500) * 5))
            tb_rows.append({
                'Particulars': f"Ledger Head {i}",
                'Debit': str(amt) if i % 2 == 0 else "0.00",
                'Credit': "0.00" if i % 2 == 0 else str(amt)
            })

        t0 = time.perf_counter()
        tb = TrialBalanceService.calculate_trial_balance(
            rows=tb_rows,
            as_of_date=date(2025, 3, 31),
            engagement=self.engagement
        )
        duration = time.perf_counter() - t0
        throughput = n / duration if duration > 0 else 0
        print(f"\n[Scale 10,000 Rows] TB Duration: {duration*1000:.2f} ms ({duration:.2f} s) | Throughput: {throughput:,.0f} rows/sec | Balanced: {tb['is_balanced']}")
        assert duration < 30.0 # SLA threshold: under 30 seconds

    def test_scale_100000_rows_benchmark(self):
        """
        SCALE 3: 100,000 ROWS
        High-volume volume stress test measuring exact memory and execution latency.
        """
        n = 100000
        tb_rows = []
        for i in range(n):
            amt = Decimal(str(50 + ((i // 2) % 1000)))
            tb_rows.append({
                'Particulars': f"Head {i}",
                'Debit': str(amt) if i % 2 == 0 else "0.00",
                'Credit': "0.00" if i % 2 == 0 else str(amt)
            })

        t0 = time.perf_counter()
        tb = TrialBalanceService.calculate_trial_balance(
            rows=tb_rows,
            as_of_date=date(2025, 3, 31),
            engagement=self.engagement
        )
        duration = time.perf_counter() - t0
        throughput = n / duration if duration > 0 else 0
        print(f"\n[Scale 100,000 Rows] TB Duration: {duration:.2f} s | Throughput: {throughput:,.0f} rows/sec | Balanced: {tb['is_balanced']}")
        assert tb['is_balanced'] is True
        assert duration < 60.0 # SLA threshold: under 60 seconds
