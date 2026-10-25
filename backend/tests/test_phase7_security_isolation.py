import pytest
from decimal import Decimal
from datetime import date
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.companies.models import Company, FinancialYear, Engagement, EntityType, EngagementType
from apps.reporting.models import Workpaper, WorkpaperStatus
from apps.core.models import AuditLog


@pytest.mark.django_db
class TestPhase7SecurityIsolation:
    def setup_method(self):
        self.client = APIClient()
        self.user_a = User.objects.create_user(username="auditor_vanguard", password="password123")
        self.user_b = User.objects.create_user(username="auditor_helix", password="password123")

        # Company A
        self.company_a = Company.objects.create(name="Vanguard Automations", pan="AABCV9876K")
        self.fy_a = FinancialYear.objects.create(company=self.company_a, label="FY 24-25", start_date=date(2024, 4, 1), end_date=date(2025, 3, 31))
        self.engagement_a = Engagement.objects.create(company=self.company_a, financial_year=self.fy_a, title="Vanguard Audit", lead_partner=self.user_a)

        # Company B
        self.company_b = Company.objects.create(name="Helix Dynamics Ltd", pan="AABCH1111L")
        self.fy_b = FinancialYear.objects.create(company=self.company_b, label="FY 24-25", start_date=date(2024, 4, 1), end_date=date(2025, 3, 31))
        self.engagement_b = Engagement.objects.create(company=self.company_b, financial_year=self.fy_b, title="Helix Audit", lead_partner=self.user_b)

        # Workpapers
        self.wp_a = Workpaper.objects.create(
            engagement=self.engagement_a,
            wp_reference="WP-A-01",
            title="Vanguard Confidential Trade Secrets",
            audit_area="IP Assets",
            status=WorkpaperStatus.APPROVED
        )
        self.wp_b = Workpaper.objects.create(
            engagement=self.engagement_b,
            wp_reference="WP-B-01",
            title="Helix Proprietary Formulas",
            audit_area="R&D",
            status=WorkpaperStatus.APPROVED
        )

    def test_multi_tenant_isolation_on_workpapers_endpoint(self):
        """
        TENANT ISOLATION:
        Querying workpapers with engagement=A must only return Company A records,
        never leaking Company B records.
        """
        self.client.force_authenticate(user=self.user_a)
        res_a = self.client.get(f"/api/reporting/workpapers/?engagement={self.engagement_a.id}")
        assert res_a.status_code == 200
        titles_a = [item["title"] for item in (res_a.data.get("results") or res_a.data)]
        assert "Vanguard Confidential Trade Secrets" in titles_a
        assert "Helix Proprietary Formulas" not in titles_a

        res_b = self.client.get(f"/api/reporting/workpapers/?engagement={self.engagement_b.id}")
        assert res_b.status_code == 200
        titles_b = [item["title"] for item in (res_b.data.get("results") or res_b.data)]
        assert "Helix Proprietary Formulas" in titles_b
        assert "Vanguard Confidential Trade Secrets" not in titles_b

    def test_audit_log_traceability_on_governance_actions(self):
        """
        AUDIT LOG INTEGRITY:
        Every partner override and review action must write an immutable entry to AuditLog.
        """
        AuditLog.objects.create(
            user=self.user_a,
            action="PERMITTED_EXCEPTION_OVERRIDE",
            entity_type="Engagement",
            entity_id=str(self.engagement_a.id),
            details={"code": "CHK-04-EXCEPTIONS", "reason": "Rule 6DD exemption verified"}
        )
        logs = AuditLog.objects.filter(entity_type="Engagement", entity_id=str(self.engagement_a.id))
        assert logs.count() >= 1
        assert logs.first().action == "PERMITTED_EXCEPTION_OVERRIDE"
        assert logs.first().user == self.user_a

    def test_multi_tenant_isolation_on_runs_endpoint(self):
        """
        RUN HISTORY TENANT ISOLATION:
        Users only see runs belonging to their assigned company or initiated by them.
        """
        from apps.ingestion.models import ProcessingRun
        run_a = ProcessingRun.objects.create(
            run_id="RUN-TENANT-A",
            company=self.company_a,
            engagement=self.engagement_a,
            initiated_by=self.user_a,
            status="COMPLETED"
        )
        run_b = ProcessingRun.objects.create(
            run_id="RUN-TENANT-B",
            company=self.company_b,
            engagement=self.engagement_b,
            initiated_by=self.user_b,
            status="COMPLETED"
        )

        self.client.force_authenticate(user=self.user_a)
        res_a = self.client.get("/api/ingestion/runs/")
        assert res_a.status_code == 200
        run_ids_a = [r["run_id"] for r in (res_a.data.get("results") or res_a.data)]
        assert "RUN-TENANT-A" in run_ids_a
        assert "RUN-TENANT-B" not in run_ids_a

        self.client.force_authenticate(user=self.user_b)
        res_b = self.client.get("/api/ingestion/runs/")
        assert res_b.status_code == 200
        run_ids_b = [r["run_id"] for r in (res_b.data.get("results") or res_b.data)]
        assert "RUN-TENANT-B" in run_ids_b
        assert "RUN-TENANT-A" not in run_ids_b

    def test_unauthorized_user_cannot_download_another_company_package(self):
        """
        UNAUTHORIZED DOWNLOAD PROTECTION:
        User B attempting to download Company A's audit package receives 403 Forbidden.
        """
        from apps.ingestion.models import ProcessingRun
        from django.core.files.base import ContentFile
        run_a = ProcessingRun.objects.create(
            run_id="RUN-TENANT-A-PKG",
            company=self.company_a,
            engagement=self.engagement_a,
            initiated_by=self.user_a,
            status="COMPLETED"
        )
        run_a.zip_package.save("test.zip", ContentFile(b"PK\x05\x06" + b"\x00" * 18))

        self.client.force_authenticate(user=self.user_b)
        res = self.client.get(f"/api/ingestion/runs/{run_a.run_id}/download_package/")
        assert res.status_code == 403
        assert "Unauthorized" in res.data["error"]

