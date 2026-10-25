import os
import sys
import django

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import pytest
from rest_framework.test import APIRequestFactory
from apps.companies.models import Company, Engagement
from apps.companies.views import CompanyViewSet, EngagementViewSet

@pytest.mark.django_db(transaction=True)
def test_company_deletion_never_resurrects():
    factory = APIRequestFactory()

    # 1. Create a company and engagement
    company = Company.objects.create(name="Assurance Enterprise Client Pvt Ltd")
    fy = company.financial_years.create(label="FY 2024-25", start_date="2024-04-01", end_date="2025-03-31")
    Engagement.objects.create(company=company, financial_year=fy, title="Statutory Audit FY 2024-25")

    assert Company.objects.count() == 1
    assert Engagement.objects.count() == 1

    # 2. Delete the company via CompanyViewSet destroy
    co_view = CompanyViewSet.as_view({'delete': 'destroy'})
    del_req = factory.delete(f'/api/companies/companies/{company.id}/')
    del_resp = co_view(del_req, pk=company.id)
    assert del_resp.status_code == 204

    # Verify DB is completely empty
    assert Company.objects.count() == 0
    assert Engagement.objects.count() == 0

    # 3. Requesting latest engagement must return 404 (NotFound) and NEVER recreate any company
    eng_view = EngagementViewSet.as_view({'get': 'workflow_config'})
    req = factory.get('/api/companies/engagements/latest/workflow_config/')
    resp = eng_view(req, pk='latest')
    assert resp.status_code == 404
    assert Company.objects.count() == 0

    # 4. Requesting company list must return 0 results and count must remain 0
    co_list_view = CompanyViewSet.as_view({'get': 'list'})
    list_req = factory.get('/api/companies/companies/')
    list_resp = co_list_view(list_req)
    assert list_resp.status_code == 200
    assert list_resp.data['count'] == 0
    assert len(list_resp.data['results']) == 0
    assert Company.objects.count() == 0

    # 5. Test clear_all endpoint
    co2 = Company.objects.create(name="Another Client Pvt Ltd")
    assert Company.objects.count() == 1
    clear_view = CompanyViewSet.as_view({'post': 'clear_all'})
    clear_req = factory.post('/api/companies/companies/clear_all/')
    clear_resp = clear_view(clear_req)
    assert clear_resp.status_code == 200
    assert Company.objects.count() == 0

    # Final check: DB remains 0!
    assert Company.objects.count() == 0
    print("\nSUCCESS: All deletion persistence tests passed! Ghost company never resurrects.")

if __name__ == '__main__':
    test_company_deletion_never_resurrects()
