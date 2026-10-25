import os
import time
import tracemalloc
from decimal import Decimal
from datetime import date
import django

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.companies.models import Company, FinancialYear, Engagement
from apps.ingestion.parsers import DocumentParserService
from apps.accounting.services import TrialBalanceService, GeneralLedgerScrutinyService
from apps.reconciliation.services import BankReconciliationEngine
from apps.audit.services import AuditProcedureRunner
from apps.accounting.models import Transaction, LedgerAccount, ChartOfAccounts, AccountType

def run_benchmarks():
    print("=" * 70)
    print("CAPTRIX AI — PERFORMANCE & ACCURACY BENCHMARK SUITE")
    print("=" * 70)

    tracemalloc.start()
    start_total_time = time.perf_counter()

    # 1. Parsing Throughput Benchmark
    from django.conf import settings
    sample_file = os.path.join(settings.BASE_DIR.parent, "samples", "Apex_Infotech_Trial_Balance_FY24_25.xlsx")
    if not os.path.exists(sample_file):
        sample_file = os.path.join(settings.BASE_DIR, "samples", "Apex_Infotech_Trial_Balance_FY24_25.xlsx")
    t0 = time.perf_counter()
    parsed = DocumentParserService.parse_file(sample_file, "Apex_Infotech_Trial_Balance_FY24_25.xlsx")
    t_parse = time.perf_counter() - t0
    records_count = len(parsed['records'])
    throughput = (records_count / t_parse) if t_parse > 0 else 0
    print(f"[1] PARSING BENCHMARK:")
    print(f"    - File: {sample_file}")
    print(f"    - Parsed Records: {records_count} rows")
    print(f"    - Duration: {t_parse*1000:.2f} ms")
    print(f"    - Throughput: {throughput:.1f} rows/sec")

    # 2. Trial Balance Validation Benchmark
    t0 = time.perf_counter()
    tb_res = TrialBalanceService.calculate_trial_balance(
        [{'Particulars': f"Account_{i}", 'Debit': 10000.00, 'Credit': 0.00} for i in range(500)] +
        [{'Particulars': f"Capital_{i}", 'Debit': 0.00, 'Credit': 10000.00} for i in range(500)]
    )
    t_tb = time.perf_counter() - t0
    print(f"\n[2] TRIAL BALANCE VALIDATION BENCHMARK (1,000 Accounts):")
    print(f"    - Result Status: {tb_res['status']} (Diff: ₹{tb_res['difference_amount']})")
    print(f"    - Duration: {t_tb*1000:.2f} ms")

    # 3. Reconciliation Engine Benchmark
    company, _ = Company.objects.get_or_create(name="Benchmark Corp")
    fy, _ = FinancialYear.objects.get_or_create(company=company, label="FY 24-25", defaults={'start_date': date(2024,4,1), 'end_date': date(2025,3,31)})
    eng, _ = Engagement.objects.get_or_create(company=company, financial_year=fy, title="Benchmark Recon")
    
    cb_batch = [{'date': date(2025, 3, 1), 'ref': f'CHQ-{i:05d}', 'desc': f'Vendor {i}', 'amount': f'{1000 + i}.00', 'type': 'WITHDRAWAL'} for i in range(250)]
    b_batch = [{'date': date(2025, 3, 2), 'ref': f'CHQ-{i:05d}', 'desc': f'CLG VENDOR {i}', 'amount': f'{1000 + i}.00', 'type': 'WITHDRAWAL'} for i in range(250)]

    t0 = time.perf_counter()
    recon_run = BankReconciliationEngine.execute_reconciliation(
        engagement=eng,
        as_of_date=date(2025, 3, 31),
        cashbook_items=cb_batch,
        bank_items=b_batch,
        starting_cashbook_balance=Decimal('5000000.00'),
        actual_statement_balance=Decimal('5000000.00')
    )
    t_recon = time.perf_counter() - t0
    print(f"\n[3] RECONCILIATION ENGINE BENCHMARK (500 Items BRS Match):")
    print(f"    - Matched Count: {recon_run.matched_count}")
    print(f"    - Duration: {t_recon*1000:.2f} ms")
    print(f"    - Matching Speed: {(500 / t_recon):.1f} items/sec")

    # 4. Memory Usage & Total E2E
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    total_duration = time.perf_counter() - start_total_time

    print(f"\n[4] RESOURCE UTILIZATION & TOTAL TIME:")
    print(f"    - Peak Memory: {peak_mem / (1024 * 1024):.2f} MB")
    print(f"    - Current Memory: {current_mem / (1024 * 1024):.2f} MB")
    print(f"    - Total Benchmark Execution: {total_duration:.2f} s")
    print("=" * 70)

if __name__ == '__main__':
    run_benchmarks()
