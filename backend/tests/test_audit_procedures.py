import pytest
from decimal import Decimal
from datetime import date
from apps.companies.models import Company, FinancialYear, Engagement
from apps.audit.services import AuditProcedureRunner
from apps.audit.models import ExceptionItem, ProcedureStatus, ExceptionSeverity
from apps.reporting.services import DemoDataService, ReportGeneratorService

@pytest.mark.django_db
def test_full_demo_dataset_and_report_generation():
    """Tests complete end-to-end flow: Seeding Demo Entity -> Running All Procedures -> PDF Report Generation"""
    # 1. Seed complete Indian entity
    eng = DemoDataService.generate_demo_dataset()
    assert eng.company.name == "Apex Infotech Private Limited"
    assert eng.financial_year.label == "FY 2024-25"

    # 2. Verify Trial Balance
    tb = eng.trial_balances.first()
    assert tb is not None
    assert tb.is_balanced is True
    assert tb.difference_amount == Decimal('0.00')

    # 3. Verify Scrutiny Exceptions
    exceptions = ExceptionItem.objects.filter(engagement=eng)
    assert exceptions.count() >= 1

    # Check Section 40A(3) exception is flagged
    sec40a3_exc = exceptions.filter(title__icontains="40A(3)").first()
    assert sec40a3_exc is not None
    assert sec40a3_exc.severity == ExceptionSeverity.CRITICAL

    # 4. Verify Workpapers
    wps = eng.workpapers.all()
    assert wps.count() >= 3
    assert wps.filter(wp_reference="WP-A101").exists()

    # 5. Verify PDF Report Generation
    report = ReportGeneratorService.generate_pdf_report(eng)
    assert report is not None
    assert report.file is not None
    assert report.file.name.endswith('.pdf')
