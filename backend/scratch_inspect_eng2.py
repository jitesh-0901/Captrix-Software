import os, sys
sys.path.insert(0, os.path.abspath('backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from apps.companies.models import Engagement
from apps.accounting.services import TrialBalanceService
from apps.reporting.report_builder import ConsolidatedAuditReportBuilder

eng = Engagement.objects.get(id=2)
tb = eng.trial_balances.first()
print(f"Engagement 2 latest TB: {tb.id}, as_of: {tb.as_of_date}")
print(f"TB accounts count: {len(tb.accounts_snapshot)}")
for idx, acc in enumerate(tb.accounts_snapshot):
    code = acc.get('account_code')
    name = acc.get('account_name')
    dr = acc.get('debit')
    cr = acc.get('credit')
    grp = acc.get('schedule_iii_group')
    print(f"{idx+1}: {code} - {name} [Dr:{dr}, Cr:{cr}] Group: {grp}")

fs = TrialBalanceService.compile_financial_statements(tb.accounts_snapshot)
print("\n--- COMPILED FINANCIAL STATEMENTS ---")
print("BS Total Assets:", fs['balance_sheet']['total_assets'])
print("BS Assets details:", fs['balance_sheet']['assets'])
print("BS Total Eq & Liab:", fs['balance_sheet']['total_equity_and_liabilities'])
print("BS Eq & Liab details:", fs['balance_sheet']['equity_and_liabilities'])
print("PL Rev Ops:", fs['profit_and_loss']['revenue_from_operations'])
print("PL Other Income:", fs['profit_and_loss']['other_income'])
print("PL Total Revenue:", fs['profit_and_loss']['total_revenue'])
print("PL Expenses:", fs['profit_and_loss']['expenses'])

print("\n--- REPORT BUILDER ---")
rep = ConsolidatedAuditReportBuilder.build_report(eng)
print("Section C BS:", rep.get('section_c', {}).get('balance_sheet'))
print("Section C PL:", rep.get('section_c', {}).get('profit_loss'))
print("Section C Ratios:", rep.get('section_c', {}).get('ratios'))

print("\n--- EXPORTERS OUTPUT REPRODUCIBILITY ---")
# Check how exporters.py renders BS and PL
from apps.reporting.exporters import ReportExporterService
# We can check the data passed into PDF
