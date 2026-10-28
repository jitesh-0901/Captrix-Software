import pytest
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from apps.companies.models import Company, FinancialYear, Engagement, EngagementStatus, EngagementType
from apps.core.models import UserProfile
from apps.accounting.models import TrialBalanceSnapshot
from apps.reconciliation.models import ReconciliationRun, ReconciliationType, ReconciliationStatus
from apps.audit.models import ExceptionItem, ExceptionSeverity, ExceptionStatus, ProcedureExecution, ProcedureStatus
from apps.reporting.models import Workpaper, WorkpaperStatus
from apps.ingestion.models import Document, DocumentStatus, DocumentType
from apps.ingestion.parsers import parse_indian_amount, parse_field_amount
from apps.audit.finalization_service import AuditFinalizationService
from apps.companies.completion_service import EngagementCompletionService


@pytest.mark.django_db
class TestStrictMissingValueHandling:
    """Verifies that parse_indian_amount distinguishes legitimate zero movement from missing evidence."""

    def test_explicit_zero_always_preserves_zero(self):
        assert parse_indian_amount("0") == Decimal('0.00')
        assert parse_indian_amount("0.00") == Decimal('0.00')
        assert parse_indian_amount("0.0") == Decimal('0.00')
        assert parse_indian_amount(0) == Decimal('0.00')
        assert parse_indian_amount(Decimal('0.00')) == Decimal('0.00')
        assert parse_indian_amount("Nil") == Decimal('0.00')
        assert parse_indian_amount("NIL") == Decimal('0.00')
        assert parse_indian_amount("0.00", allow_blank_zero=False) == Decimal('0.00')
        assert parse_indian_amount("Nil", allow_blank_zero=False) == Decimal('0.00')

    def test_ledger_columns_allow_blank_zero_movement(self):
        # In a double-entry ledger/TB row, debit column is blank if entry is credit
        assert parse_indian_amount("", allow_blank_zero=True) == Decimal('0.00')
        assert parse_indian_amount("-", allow_blank_zero=True) == Decimal('0.00')
        assert parse_indian_amount("--", allow_blank_zero=True) == Decimal('0.00')

        # Using parse_field_amount in TB/GL context
        assert parse_field_amount("", "Debit", "TRIAL_BALANCE") == Decimal('0.00')
        assert parse_field_amount("-", "Credit", "GENERAL_LEDGER") == Decimal('0.00')
        assert parse_field_amount("", "Closing_Debit", "TRIAL_BALANCE") == Decimal('0.00')

    def test_transaction_fields_do_not_fabricate_zero_for_missing_values(self):
        # Bank statements, invoices, and fixed asset schedules must NEVER treat blank/missing as zero
        assert parse_indian_amount("", allow_blank_zero=False) is None
        assert parse_indian_amount("-", allow_blank_zero=False) is None
        assert parse_indian_amount("--", allow_blank_zero=False) is None
        assert parse_indian_amount("nan", allow_blank_zero=False) is None
        assert parse_indian_amount("N/A", allow_blank_zero=False) is None
        assert parse_indian_amount(None, allow_blank_zero=False) is None

        # Context-aware parse_field_amount
        assert parse_field_amount("", "Withdrawal", "BANK_STATEMENT") is None
        assert parse_field_amount("-", "Deposit", "BANK_STATEMENT") is None
        assert parse_field_amount("", "Invoice_Amount", "PURCHASE_REGISTER") is None
        assert parse_field_amount("-", "Gross_Block", "FIXED_ASSET_REGISTER") is None
        assert parse_field_amount("N/A", "Total_Amount", "SALES_REGISTER") is None

    def test_corrupted_strings_return_none(self):
        assert parse_indian_amount("CORRUPTED_TEXT") is None
        assert parse_indian_amount("NaN_INVALID", allow_blank_zero=True) is None
        assert parse_indian_amount("abc123xyz") is None


@pytest.mark.django_db
class TestMissingReconciliationEvidenceGate:
    """Verifies that mandatory reconciliation procedures fail closed when evidence is missing."""

    @pytest.fixture
    def setup_engagement(self):
        company = Company.objects.create(name="Apex Manufacturing Ltd", pan="AAACA1234D")
        fy = FinancialYear.objects.create(company=company, label="FY 2024-25", start_date="2024-04-01", end_date="2025-03-31")
        partner = User.objects.create_user(username="lead_partner@firm.com", password="password123")
        UserProfile.objects.create(user=partner, role="PARTNER", membership_number="514829", firm_name="Apex & Co, CAs")
        engagement = Engagement.objects.create(
            company=company,
            financial_year=fy,
            title="Statutory Audit FY 2024-25",
            engagement_type=EngagementType.STATUTORY,
            lead_partner=partner,
            overall_materiality=Decimal('500000.00'),
            performance_materiality=Decimal('375000.00')
        )
        return engagement, partner

    def test_statutory_audit_blocks_when_bank_reconciliation_missing(self, setup_engagement):
        engagement, partner = setup_engagement

        # Create TB with active Bank balance
        TrialBalanceSnapshot.objects.create(
            engagement=engagement,
            as_of_date=engagement.financial_year.end_date,
            is_balanced=True,
            total_debits=Decimal('1000000.00'),
            total_credits=Decimal('1000000.00'),
            difference_amount=Decimal('0.00'),
            accounts_snapshot=[
                {'code': '100100', 'name': 'HDFC Current Bank Account', 'schedule_iii_group': 'CASH_CASH_EQUIVALENTS', 'closing_balance': '500000.00', 'debit': '500000.00', 'credit': '0.00'},
                {'code': '300100', 'name': 'Share Capital', 'schedule_iii_group': 'EQUITY_SHARE_CAPITAL', 'closing_balance': '500000.00', 'debit': '0.00', 'credit': '500000.00'}
            ]
        )

        readiness = AuditFinalizationService.evaluate_finalization_readiness(engagement, user=partner)
        assert not readiness['can_finalize']
        assert any('bank reconciliation' in b.lower() and 'missing' in b.lower() for b in readiness['blockers'])

    def test_missing_subledger_reconciliation_blocks_finalization(self, setup_engagement):
        engagement, partner = setup_engagement

        # TB has ₹15,00,000 in Trade Payables, but zero Creditors Aging subledger uploaded
        TrialBalanceSnapshot.objects.create(
            engagement=engagement,
            as_of_date=engagement.financial_year.end_date,
            is_balanced=True,
            total_debits=Decimal('1500000.00'),
            total_credits=Decimal('1500000.00'),
            difference_amount=Decimal('0.00'),
            accounts_snapshot=[
                {'code': '100100', 'name': 'Cash on Hand', 'schedule_iii_group': 'CASH_CASH_EQUIVALENTS', 'closing_balance': '1500000.00', 'debit': '1500000.00', 'credit': '0.00'},
                {'code': '200100', 'name': 'Trade Payables Control', 'schedule_iii_group': 'TRADE_PAYABLES', 'closing_balance': '1500000.00', 'debit': '0.00', 'credit': '1500000.00'}
            ]
        )

        readiness = AuditFinalizationService.evaluate_finalization_readiness(engagement, user=partner)
        assert not readiness['can_finalize']
        assert any('creditors subledger reconciliation is missing' in b.lower() for b in readiness['blockers'])


@pytest.mark.django_db
class TestSingleFinalizationAuthorityAndSecurity:
    """Verifies that completion service authoritatively delegates and security rules prevent unauthorized access."""

    @pytest.fixture
    def setup_users_and_engagement(self):
        company = Company.objects.create(name="Bharat Tech Solutions Ltd", pan="AABCB9876E")
        fy = FinancialYear.objects.create(company=company, label="FY 2024-25", start_date="2024-04-01", end_date="2025-03-31")

        partner = User.objects.create_user(username="partner_ca", password="secretpassword")
        UserProfile.objects.create(user=partner, role="PARTNER", membership_number="514829", firm_name="B.T. Sharma & Co")

        junior = User.objects.create_user(username="junior_intern", password="secretpassword")
        UserProfile.objects.create(user=junior, role="PREPARER")

        engagement = Engagement.objects.create(
            company=company,
            financial_year=fy,
            title="Statutory Audit FY 2024-25",
            engagement_type=EngagementType.STATUTORY,
            lead_partner=partner,
            overall_materiality=Decimal('500000.00')
        )
        return company, engagement, partner, junior

    def test_anonymous_user_cannot_finalize(self, setup_users_and_engagement):
        _, engagement, _, _ = setup_users_and_engagement
        client = APIClient()

        # Anonymous POST to finalize
        res = client.post(f"/api/companies/engagements/{engagement.id}/finalize/", {
            'justification': 'Anonymous attempt'
        }, format='json')

        assert res.status_code == 401
        assert "Authentication required" in res.data['message']

    def test_unauthorized_user_cannot_finalize(self, setup_users_and_engagement):
        _, engagement, _, junior = setup_users_and_engagement
        client = APIClient()
        client.force_authenticate(user=junior)

        res = client.post(f"/api/companies/engagements/{engagement.id}/finalize/", {
            'justification': 'Junior attempt'
        }, format='json')

        assert res.status_code == 403
        assert "not authorized" in res.data['message']

    def test_authorized_ca_partner_persists_credentials_and_finalizes(self, setup_users_and_engagement):
        company, engagement, partner, _ = setup_users_and_engagement
        client = APIClient()
        client.force_authenticate(user=partner)

        # Setup balanced TB and satisfied gates
        tb = TrialBalanceSnapshot.objects.create(
            engagement=engagement,
            as_of_date=engagement.financial_year.end_date,
            is_balanced=True,
            total_debits=Decimal('100000.00'),
            total_credits=Decimal('100000.00'),
            difference_amount=Decimal('0.00'),
            accounts_snapshot=[
                {'code': '100100', 'name': 'Cash Account', 'schedule_iii_group': 'CASH_CASH_EQUIVALENTS', 'closing_balance': '100000.00', 'debit': '100000.00', 'credit': '0.00'},
                {'code': '300100', 'name': 'Share Capital', 'schedule_iii_group': 'EQUITY_SHARE_CAPITAL', 'closing_balance': '100000.00', 'debit': '0.00', 'credit': '100000.00'}
            ]
        )

        # Satisfy Bank BRS
        ReconciliationRun.objects.create(
            engagement=engagement,
            recon_type='BANK',
            status=ReconciliationStatus.BALANCED,
            as_of_date=engagement.financial_year.end_date,
            balance_per_books=Decimal('100000.00'),
            balance_per_statement=Decimal('100000.00'),
            unreconciled_difference=Decimal('0.00'),
            unmatched_count=0
        )

        # Satisfy Workpaper
        Workpaper.objects.create(
            engagement=engagement,
            wp_reference="WP-GEN-01",
            title="Audit Completion Summary",
            audit_area="GENERAL",
            audit_objective="Evaluate final audit completion",
            scope_and_coverage="Full engagement",
            testing_methodology="Substantive testing",
            results_summary="All procedures completed satisfactorily",
            proposed_conclusion="Unqualified opinion",
            status=WorkpaperStatus.APPROVED
        )

        ca_payload = {
            'ca_name': 'CA. Rajesh Sharma',
            'ca_member_no': '514829',
            'ca_firm_no': '012345N',
            'udin': '25514829AAAA123456',
            'justification': 'All substantive audit procedures cleared and confirmed.'
        }

        res = client.post(f"/api/companies/engagements/{engagement.id}/finalize/", ca_payload, format='json')
        assert res.status_code == 200
        assert res.data['success'] is True
        assert res.data['status'] == 'COMPLETED'
        assert res.data['udin'] == '25514829AAAA123456'

        # Refresh database and verify persistence
        engagement.refresh_from_db()
        assert engagement.is_finalized is True
        assert engagement.udin == '25514829AAAA123456'
        assert engagement.finalization_metadata['ca_name'] == 'CA. Rajesh Sharma'
        assert engagement.finalization_metadata['ca_member_no'] == '514829'
        assert engagement.finalization_metadata['ca_firm_no'] == '012345N'

    def test_completion_service_delegates_to_audit_finalization_service(self, setup_users_and_engagement):
        _, engagement, partner, _ = setup_users_and_engagement

        # Call EngagementCompletionService.finalize_engagement directly
        res = EngagementCompletionService.finalize_engagement(
            engagement=engagement,
            user=partner,
            justification="Testing delegation"
        )

        # Unresolved blockers must fail closed through the authoritative service
        assert res['success'] is False
        assert len(res['blockers']) > 0
