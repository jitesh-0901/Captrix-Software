import os
import io
import pytest
from decimal import Decimal
from datetime import date
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.companies.models import Company, FinancialYear, Engagement, EntityType, EngagementType
from apps.accounting.models import ChartOfAccounts, LedgerAccount, Transaction, TrialBalanceSnapshot, VoucherType
from apps.accounting.services import TrialBalanceService
from apps.ingestion.parsers import parse_indian_amount, parse_flexible_date, DocumentParserService
from apps.core.security import validate_uploaded_file, sanitize_filename


@pytest.mark.django_db
class TestPhase7InvalidInputs:
    def setup_method(self):
        self.client = APIClient()
        self.company = Company.objects.create(
            name="Vanguard Testing Corp",
            cin="U29100MH2020PTC345678",
            pan="AABCV9876K",
            entity_type=EntityType.PVT_LTD
        )
        self.fy = FinancialYear.objects.create(
            company=self.company,
            label="FY 2024-25",
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31)
        )
        self.engagement = Engagement.objects.create(
            company=self.company,
            financial_year=self.fy,
            title="Acceptance Testing Engagement",
            engagement_type=EngagementType.STATUTORY,
            overall_materiality=Decimal('500000.00')
        )

    def test_unbalanced_trial_balance_fails_closed_without_synthetic_plugs(self):
        """
        FAIL-CLOSED TB TEST:
        An unbalanced trial balance with an intentional variance (+25,000 INR) must:
        1. Set is_balanced = False
        2. Record difference_amount = Decimal('25000.00')
        3. Never invent synthetic balancing plugs or alter source numbers
        """
        unbalanced_rows = [
            {'Particulars': 'Plant & Machinery', 'Debit': '45,00,000.00', 'Credit': '0.00'},
            {'Particulars': 'SBI Current A/c', 'Debit': '18,25,000.00', 'Credit': '0.00'}, # +25,000 error
            {'Particulars': 'Equity Capital', 'Debit': '0.00', 'Credit': '50,00,000.00'},
            {'Particulars': 'Trade Payables', 'Debit': '0.00', 'Credit': '13,00,000.00'},
        ]
        # Debits = 63,25,000.00, Credits = 63,00,000.00 -> Diff = 25,000.00
        tb = TrialBalanceService.calculate_trial_balance(
            rows=unbalanced_rows,
            as_of_date=date(2025, 3, 31),
            engagement=self.engagement
        )
        assert tb['is_balanced'] is False
        assert Decimal(tb['total_debits']) == Decimal('6325000.00')
        assert Decimal(tb['total_credits']) == Decimal('6300000.00')
        assert Decimal(tb['difference_amount']) == Decimal('25000.00')
        # Check snapshot accounts: No 'Suspense' or plug account was auto-injected
        account_names = [a.get('account_name') for a in tb['accounts']]
        assert "Suspense Account" not in account_names
        assert "Rounding Adjustment" not in account_names
        # Check that a critical audit exception was automatically logged
        assert self.engagement.exceptions.filter(rule_code="RULE_TB_UNBALANCED").exists()

    def test_missing_and_corrupted_numeric_amounts_never_invented(self):
        """
        DATA INTEGRITY TEST:
        Missing or corrupt numeric fields must return None or parse to explicit 0.00 where designated,
        and never hallucinate non-zero numbers.
        """
        assert parse_indian_amount(None) is None
        assert parse_indian_amount("") == Decimal('0.00')
        assert parse_indian_amount("-") == Decimal('0.00')
        assert parse_indian_amount("NIL") == Decimal('0.00')
        assert parse_indian_amount("CORRUPTED_VALUE_TXT") is None
        assert parse_indian_amount("₹ 1,25,500.50") == Decimal('125500.50')
        assert parse_indian_amount("(45,000.00)") == Decimal('-45000.00')

    def test_ambiguous_date_formats_parsed_without_hallucination(self):
        """
        DATE PARSING TEST:
        Must properly standardize various Indian business date formats (DD/MM/YYYY, ISO, DD-Mon-YYYY)
        without inventing random dates for invalid strings.
        """
        assert parse_flexible_date("2024-04-15") == "2024-04-15"
        assert parse_flexible_date("15/04/2024") == "2024-04-15"
        assert parse_flexible_date("15-Apr-2024") == "2024-04-15"
        assert parse_flexible_date("invalid_date_string") is None
        assert parse_flexible_date("") is None

    def test_unsupported_file_types_and_zero_byte_rejection(self):
        """
        SECURITY & BOUNDARY TEST:
        Executable scripts and zero-byte files must be rejected with ValueError.
        """
        from rest_framework.exceptions import ValidationError
        empty_file = SimpleUploadedFile("empty_ledger.csv", b"", content_type="text/csv")
        with pytest.raises(ValidationError, match="empty"):
            validate_uploaded_file(empty_file)

        exe_file = SimpleUploadedFile("malicious_script.exe", b"binarycontent", content_type="application/octet-stream")
        with pytest.raises(ValidationError, match="Unsupported file extension"):
            validate_uploaded_file(exe_file)

    def test_path_traversal_filename_sanitization(self):
        """
        PATH TRAVERSAL DEFENSE:
        Malicious relative path traversal in filename must be neutralized.
        """
        dangerous_name = "../../../etc/passwd.csv"
        safe_name = sanitize_filename(dangerous_name)
        assert "../" not in safe_name
        assert ".." not in safe_name
        assert safe_name.endswith(".csv")
