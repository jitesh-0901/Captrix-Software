import os, sys, django
sys.path.insert(0, os.path.abspath('backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.companies.models import Engagement
from apps.reporting.report_builder import ConsolidatedAuditReportBuilder
from apps.reporting.exporters import ReportExporterService
from apps.reporting.models import GeneratedReport, ReportType

eng = Engagement.objects.get(id=2)
print(f"=== Generating Verified Consolidated Audit Reports for Engagement {eng.id}: {eng.company.name} ===")

rep_data = ConsolidatedAuditReportBuilder.build_report(eng)
print("Consolidated report built successfully.")

sec_c = rep_data.get('section_c', {})
print(f"Section C Assets: {sec_c.get('total_assets')}")
print(f"Section C Equity & Liab: {sec_c.get('total_equity_and_liabilities')}")
print(f"Section C Revenue: {sec_c.get('revenue_from_operations')}")
print(f"Section C Trade Payables: {sec_c.get('trade_payables')}")
print(f"Section C Cash & Bank: {sec_c.get('cash_and_bank_balances')}")

out_dir = os.path.abspath('test_reports')
os.makedirs(out_dir, exist_ok=True)
pdf_path = os.path.join(out_dir, f"verified_consolidated_audit_report_{eng.id}.pdf")
xlsx_path = os.path.join(out_dir, f"verified_consolidated_audit_report_{eng.id}.xlsx")

print(f"\n1. Exporting Consolidated PDF to: {pdf_path}")
pdf_bytes = ReportExporterService.export_consolidated_pdf(eng)
with open(pdf_path, 'wb') as f:
    f.write(pdf_bytes)
print(f"PDF exported successfully ({len(pdf_bytes):,} bytes).")

print(f"\n2. Exporting Consolidated XLSX to: {xlsx_path}")
xlsx_bytes = ReportExporterService.export_consolidated_excel(eng)
with open(xlsx_path, 'wb') as f:
    f.write(xlsx_bytes)
print(f"XLSX exported successfully ({len(xlsx_bytes):,} bytes).")

# Save GeneratedReport record in database
gen_rep = GeneratedReport.objects.create(
    engagement=eng,
    report_type=ReportType.CONSOLIDATED_AUDIT_REPORT,
    title=f"Consolidated Statutory Audit Report - {eng.company.name} ({eng.financial_year.label})",
    report_data=rep_data
)
print(f"\nSaved GeneratedReport ID {gen_rep.id} in database.")
