import os
import pytest
from decimal import Decimal
from datetime import date
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.companies.models import Company, FinancialYear, Engagement, EntityType, EngagementType
from apps.ingestion.models import Document, DocumentStatus, DocumentType
from apps.core.security import sanitize_filename, validate_uploaded_file
from rest_framework.exceptions import ValidationError


@pytest.mark.django_db
class TestSecurityAccessControl:
    def setup_method(self):
        self.client = APIClient()

        # Company A (Tenant A)
        self.comp_a = Company.objects.create(name="Tenant Alpha Corp", pan="AAAAA1111A")
        self.fy_a = FinancialYear.objects.create(company=self.comp_a, label="FY 24-25", start_date=date(2024, 4, 1), end_date=date(2025, 3, 31))
        self.eng_a = Engagement.objects.create(company=self.comp_a, financial_year=self.fy_a, title="Audit Alpha")

        # Company B (Tenant B)
        self.comp_b = Company.objects.create(name="Tenant Beta Corp", pan="BBBBB2222B")
        self.fy_b = FinancialYear.objects.create(company=self.comp_b, label="FY 24-25", start_date=date(2024, 4, 1), end_date=date(2025, 3, 31))
        self.eng_b = Engagement.objects.create(company=self.comp_b, financial_year=self.fy_b, title="Audit Beta")

    def test_tenant_data_isolation_on_workpapers_and_reports(self):
        """
        TENANT ISOLATION TEST:
        Queries filtered by engagement strictly return only that tenant's records.
        """
        from apps.reporting.models import Workpaper
        wp_a = Workpaper.objects.create(engagement=self.eng_a, wp_reference="WP-ALPHA", title="Alpha WP")
        wp_b = Workpaper.objects.create(engagement=self.eng_b, wp_reference="WP-BETA", title="Beta WP")

        # Querying engagement A must NOT return engagement B's workpapers
        res_a = self.client.get(f"/api/reporting/workpapers/?engagement={self.eng_a.id}")
        assert res_a.status_code == 200
        refs = [w["wp_reference"] for w in (res_a.data.get("results") or res_a.data)]
        assert "WP-ALPHA" in refs
        assert "WP-BETA" not in refs

    def test_path_traversal_filename_sanitization(self):
        """
        PATH TRAVERSAL DEFENSE TEST:
        Uploads with malicious path traversal components (e.g. ../../etc/passwd)
        must be stripped to safe basename without directory separators.
        """
        malicious_filename = "../../../../secrets/config.xlsx"
        sanitized = sanitize_filename(malicious_filename)
        assert "/" not in sanitized
        assert ".." not in sanitized
        assert sanitized == "config.xlsx"

        windows_malicious = "..\\..\\windows\\system32\\hosts.csv"
        sanitized_win = sanitize_filename(windows_malicious)
        assert "\\" not in sanitized_win
        assert ".." not in sanitized_win
        assert sanitized_win == "hosts.csv"

    def test_unsupported_file_extension_rejected(self):
        """
        UNSAFE FILE TYPE REJECTION TEST:
        Executables, scripts, and non-financial extensions (.exe, .sh, .py, .bat)
        must be rejected with validation error.
        """
        dangerous_file = SimpleUploadedFile(
            name="malware.exe",
            content=b"MZ\x90\x00\x03\x00\x00\x00",
            content_type="application/x-msdownload"
        )

        res = self.client.post(
            "/api/ingestion/documents/",
            {
                "engagement": self.eng_a.id,
                "file": dangerous_file
            },
            format="multipart"
        )
        assert res.status_code == 400
        assert "Unsupported file extension" in res.data["error"]

    def test_zero_byte_empty_file_rejected(self):
        """
        EMPTY FILE REJECTION TEST:
        Empty 0-byte uploads must be rejected immediately without parser invocation.
        """
        empty_file = SimpleUploadedFile(
            name="empty_ledger.xlsx",
            content=b"",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        res = self.client.post(
            "/api/ingestion/documents/",
            {
                "engagement": self.eng_a.id,
                "file": empty_file
            },
            format="multipart"
        )
        assert res.status_code == 400
        assert "empty" in res.data["error"]
