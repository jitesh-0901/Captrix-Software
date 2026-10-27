import os, sys, django
sys.path.insert(0, os.path.abspath('backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from decimal import Decimal
from apps.companies.models import Engagement
from apps.ingestion.models import Document, ExtractedRecord, ProcessingRun
from apps.accounting.services import TrialBalanceService
from apps.accounting.models import TrialBalanceSnapshot
from apps.reconciliation.services import BankReconciliationEngine
from apps.reconciliation.models import ReconciliationRun
from apps.audit.services import FinancialRatiosEngine
from apps.ingestion.orchestrator import AutomationOrchestratorService

eng = Engagement.objects.get(id=2)
print(f"=== Testing Engagement {eng.id}: {eng.company.name} ===")

# 1. Trial Balance Check
doc25 = Document.objects.filter(engagement=eng, id=25).first()
recs25 = list(doc25.extracted_records.all())
tb_rows = [r.raw_data for r in recs25]
tb_res = TrialBalanceService.calculate_trial_balance(
    rows=tb_rows,
    as_of_date=eng.financial_year.end_date,
    engagement=eng,
    document=doc25
)

fin_stmts = TrialBalanceService.compile_financial_statements(tb_res['accounts'])
bs = fin_stmts['balance_sheet']
pl = fin_stmts['profit_and_loss']

print(f"\n1. Financial Statements:")
print(f"  Total Assets: INR {bs['total_assets']}")
print(f"  Total Equity & Liabilities: INR {bs['total_equity_and_liabilities']}")
print(f"  Balanced: {bs['is_balanced']}, Diff: {bs['difference']}")
print(f"  P&L Revenue from Operations: INR {pl['revenue_from_operations']}")
print(f"  P&L Other Income: INR {pl['other_income']}")
cl = bs['equity_and_liabilities']['current_liabilities']
print(f"  Trade Payables: INR {cl['trade_payables']}")
print(f"  Other Current Liab: INR {cl['other_current_liabilities']}")
print(f"  Current Liab Total: INR {cl['total']}")

# 2. Bank Reconciliation via AutomationOrchestratorService
doc26 = Document.objects.filter(engagement=eng, id=26).first()
doc27 = Document.objects.filter(engagement=eng, id=27).first()
run = ProcessingRun.objects.filter(engagement=eng).first()

print(f"\n2. Running _stage_reconciliation with Bank Doc {doc27.id} ({doc27.extracted_records.count()} recs) & GL Doc {doc26.id} ({doc26.extracted_records.count()} recs)...")
context = {'documents': [doc27, doc26]}
success, msg = AutomationOrchestratorService._stage_reconciliation(run, context)
print(f"Stage Result: success={success}, msg={msg}")

recon = ReconciliationRun.objects.filter(engagement=eng, recon_type='BANK').order_by('-created_at').first()
if recon:
    print(f"\nLatest Bank Recon {recon.id}:")
    print(f"  Balance per books: INR {recon.balance_per_books}")
    print(f"  Balance per statement: INR {recon.balance_per_statement}")
    print(f"  Timing differences: INR {recon.timing_differences_amount}")
    print(f"  Unreconciled diff: INR {recon.unreconciled_difference}")
    print(f"  Status: {recon.status}")
    print(f"  Matched count: {recon.matched_count}, Unmatched count: {recon.unmatched_count}")
    summary = recon.summary_data or {}
    print(f"  Stale cheques count: {summary.get('stale_cheques_count')}, amt: {summary.get('stale_cheques_amount')}")
    print(f"  Valid timing count: {summary.get('valid_timing_count')}, amt: {summary.get('valid_timing_amount')}")

# 3. Financial Ratios Check
ratios = FinancialRatiosEngine.compute_ratios(eng)
print(f"\n3. Financial Ratios ({len(ratios)} computed):")
for r in ratios:
    print(f"  {r['name']}: {r['value']} {r.get('unit', '')} | Status: {r['status']} | Formula: {r.get('formula')}")
