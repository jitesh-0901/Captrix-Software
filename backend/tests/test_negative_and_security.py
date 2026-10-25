import io
import pytest
from decimal import Decimal
from datetime import date
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.companies.models import Company, FinancialYear, Engagement, EntityType, EngagementType
from apps.accounting.models import ChartOfAccounts, LedgerAccount, Transaction, TrialBalanceSnapshot, ScheduleIIIGroup, AccountType, VoucherType
from apps.accounting.services import TrialBalanceService
from apps.audit.models import ExceptionItem, ExceptionSeverity
from apps.ingestion.models import Document, DocumentStatus, DocumentType

@pytest.mark.django_db
class TestNegativeAndSecuritySuite:
    def setup_method(self):
        self.client = APIClient()

        # Company A Setup
        self.company_a = Company.objects.create(
            name="Apex Infotech Pvt Ltd",
            cin="U72200MH2021PTC356789",
            pan="AABCA9876K",
            gstin="27AABCA9876K1Z1",
            entity_type=EntityType.PVT_LTD
        )
        self.fy_a = FinancialYear.objects.create(
            company=self.company_a,
            label="FY 2024-25",
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31)
        )
        self.engagement_a = Engagement.objects.create(
            company=self.company_a,
            financial_year=self.fy_a,
            title="Statutory Audit FY 2024-25",
            engagement_type=EngagementType.STATUTORY,
            overall_materiality=Decimal('500000.00')
        )

        # Company B Setup (Strict Tenant Isolation)
        self.company_b = Company.objects.create(
            name="Zenith Robotics Ltd",
            cin="U29100KA2020PLC112233",
            pan="AAACZ5544M",
            gstin="29AAACZ5544M1Z2",
            entity_type=EntityType.PUB_LTD
        )
        self.fy_b = FinancialYear.objects.create(
            company=self.company_b,
            label="FY 2024-25",
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31)
        )
        self.engagement_b = Engagement.objects.create(
            company=self.company_b,
            financial_year=self.fy_b,
            title="Statutory Audit FY 2024-25",
            engagement_type=EngagementType.STATUTORY,
            overall_materiality=Decimal('1000000.00')
        )

    def test_unbalanced_trial_balance_fails_closed(self):
        """
        FAIL-CLOSED TEST: Unbalanced trial balance must NEVER fabricate balancing entries.
        It must mark is_balanced=False, calculate exact difference, and create a CRITICAL ExceptionItem.
        """
        unbalanced_rows = [
            {'Particulars': 'Share Capital', 'Debit': 0, 'Credit': 10000000},
            {'Particulars': 'Computer Systems', 'Debit': 6000000, 'Credit': 0},
            {'Particulars': 'HDFC Bank Account', 'Debit': 3800000, 'Credit': 0}, # Sum Dr = 98,00,000, Cr = 1,00,00,000 (Diff = 2,00,000)
        ]

        result = TrialBalanceService.calculate_trial_balance(
            rows=unbalanced_rows,
            as_of_date=date(2025, 3, 31),
            engagement=self.engagement_a
        )

        assert result['is_balanced'] is False
        assert result['status'] == 'UNBALANCED_DIFFERENCE'
        assert Decimal(result['difference_amount']) == Decimal('-200000.00')

        # Verify snapshot in DB
        snapshot = TrialBalanceSnapshot.objects.get(id=result['snapshot_id'])
        assert snapshot.is_balanced is False
        assert snapshot.difference_amount == Decimal('-200000.00')

        # Verify CRITICAL ExceptionItem was logged
        critical_exceptions = ExceptionItem.objects.filter(
            engagement=self.engagement_a,
            severity=ExceptionSeverity.CRITICAL
        )
        assert critical_exceptions.exists()
        exc = critical_exceptions.filter(rule_code="RULE_TB_UNBALANCED").first() or critical_exceptions.first()
        assert "Unbalanced Trial Balance" in exc.title
        assert exc.amount_involved == Decimal('200000.00')

    def test_empty_zero_byte_file_upload_rejected(self):
        """
        NEGATIVE TEST: Uploading an empty 0-byte file must be rejected with HTTP 400.
        """
        empty_file = SimpleUploadedFile("empty_ledger.xlsx", b"", content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response = self.client.post('/api/ingestion/documents/', {
            'file': empty_file,
            'engagement': self.engagement_a.id
        }, format='multipart')

        assert response.status_code == 400
        assert "empty" in response.data['error'].lower()

    def test_corrupted_file_upload_returns_422(self):
        """
        NEGATIVE TEST: Uploading corrupted file with invalid binary header must fail gracefully with HTTP 422.
        """
        corrupted_file = SimpleUploadedFile(
            "corrupted_tb.xlsx",
            b"PK\x03\x04CORRUPTED_NON_ZIP_DATA_GARBAGE_PAYLOAD",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response = self.client.post('/api/ingestion/documents/', {
            'file': corrupted_file,
            'engagement': self.engagement_a.id,
            'document_type': 'TRIAL_BALANCE'
        }, format='multipart')

        assert response.status_code == 422
        assert response.data['status'] == 'FAILED'

    def test_duplicate_file_upload_detection(self):
        """
        INTEGRITY TEST: Uploading identical file twice produces is_duplicate_hash warning via SHA-256 fingerprint.
        """
        file_content = b"Particulars,Debit,Credit\nShare Capital,0,100000\nBank,100000,0\n"
        upload1 = SimpleUploadedFile("clean_tb.csv", file_content, content_type="text/csv")
        upload2 = SimpleUploadedFile("clean_tb_copy.csv", file_content, content_type="text/csv")

        res1 = self.client.post('/api/ingestion/documents/', {
            'file': upload1,
            'engagement': self.engagement_a.id
        }, format='multipart')
        assert res1.status_code == 201
        assert res1.data['is_duplicate_hash'] is False

        res2 = self.client.post('/api/ingestion/documents/', {
            'file': upload2,
            'engagement': self.engagement_a.id
        }, format='multipart')
        assert res2.status_code == 201
        assert res2.data['is_duplicate_hash'] is True
        assert "duplicate" in res2.data['duplicate_warning'].lower()

    def test_multi_company_tenant_isolation(self):
        """
        SECURITY TEST: Ensure multi-company data isolation across transactions and trial balances.
        """
        # Create Ledger and Transaction for Company A
        ledger_a = LedgerAccount.objects.create(company=self.company_a, name="Company A Consulting Revenue")
        Transaction.objects.create(
            engagement=self.engagement_a,
            ledger_account=ledger_a,
            voucher_number="VCH-A-01",
            voucher_type=VoucherType.SALES,
            date=date(2025, 1, 15),
            credit_amount=Decimal('500000.00'),
            debit_amount=Decimal('0.00')
        )

        # Create Ledger and Transaction for Company B
        ledger_b = LedgerAccount.objects.create(company=self.company_b, name="Company B Robotics Hardware")
        Transaction.objects.create(
            engagement=self.engagement_b,
            ledger_account=ledger_b,
            voucher_number="VCH-B-99",
            voucher_type=VoucherType.SALES,
            date=date(2025, 2, 20),
            credit_amount=Decimal('950000.00'),
            debit_amount=Decimal('0.00')
        )

        # Query transactions filtered by Company A engagement
        res_a = self.client.get(f'/api/accounting/transactions/?engagement={self.engagement_a.id}')
        assert res_a.status_code == 200
        txns_a = res_a.data.get('results', res_a.data)
        assert len(txns_a) == 1
        assert txns_a[0]['voucher_number'] == "VCH-A-01"

        # Query transactions filtered by Company B engagement
        res_b = self.client.get(f'/api/accounting/transactions/?engagement={self.engagement_b.id}')
        assert res_b.status_code == 200
        txns_b = res_b.data.get('results', res_b.data)
        assert len(txns_b) == 1
        assert txns_b[0]['voucher_number'] == "VCH-B-99"

        # Verify no cross-contamination between Company A and Company B
        a_voucher_numbers = [t['voucher_number'] for t in txns_a]
        b_voucher_numbers = [t['voucher_number'] for t in txns_b]
        assert "VCH-B-99" not in a_voucher_numbers
        assert "VCH-A-01" not in b_voucher_numbers
