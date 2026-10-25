import pytest
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from apps.companies.models import Company, FinancialYear, Engagement, EngagementWorkflowConfig, BusinessTier, EntityType, EngagementType
from apps.reporting.models import Workpaper, WorkpaperStatus
from apps.audit.models import ExceptionItem, AuditAssertion, ExceptionSeverity, ExceptionStatus

class EnterpriseTieringAndReviewQueueTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.partner = User.objects.create_user(username='partner_ca', password='password123')
        self.preparer = User.objects.create_user(username='preparer_user', password='password123')
        self.manager = User.objects.create_user(username='manager_user', password='password123')

        # Create multi-tier company structure
        self.parent_company = Company.objects.create(
            name='Global Conglomerate Holdings Ltd',
            cin='U72200MH2020PLC123456',
            pan='AAACG1234F',
            gstin='27AAACG1234F1Z1',
            entity_type=EntityType.PUB_LTD,
            business_tier=BusinessTier.TIER_4_ENTERPRISE,
            branch_name='Corporate Headquarters',
            branch_code='HO-01'
        )

        self.branch_company = Company.objects.create(
            name='Global Conglomerate Bangalore Branch',
            cin='U72200KA2020PLC123456',
            pan='AAACG1234F',
            gstin='29AAACG1234F1Z8',
            entity_type=EntityType.PUB_LTD,
            business_tier=BusinessTier.TIER_4_ENTERPRISE,
            parent_company=self.parent_company,
            branch_name='Bangalore Technology Hub',
            branch_code='BR-BLR-02'
        )

        self.fy = FinancialYear.objects.create(
            company=self.parent_company,
            label='FY 2024-25',
            start_date='2024-04-01',
            end_date='2025-03-31'
        )

        self.engagement = Engagement.objects.create(
            company=self.parent_company,
            financial_year=self.fy,
            title='Statutory Audit FY 2024-25',
            engagement_type=EngagementType.STATUTORY,
            overall_materiality=Decimal('1000000.00'),
            performance_materiality=Decimal('750000.00'),
            clearly_trivial_threshold=Decimal('50000.00'),
            lead_partner=self.partner,
            audit_manager=self.manager
        )

    def test_multi_branch_hierarchy_and_enterprise_tier(self):
        """Verifies enterprise parent-subsidiary/branch hierarchy and tier assignment"""
        self.assertEqual(self.branch_company.parent_company, self.parent_company)
        self.assertEqual(self.branch_company.business_tier, BusinessTier.TIER_4_ENTERPRISE)
        self.assertEqual(self.parent_company.branches_or_subsidiaries.count(), 1)
        self.assertEqual(self.parent_company.branches_or_subsidiaries.first().branch_name, 'Bangalore Technology Hub')

    def test_dynamic_document_matrix_endpoint(self):
        """Verifies GET /api/companies/engagements/{id}/document_matrix/ returns tier-tailored documents"""
        response = self.client.get(f'/api/companies/engagements/{self.engagement.id}/document_matrix/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['company_tier'], BusinessTier.TIER_4_ENTERPRISE)
        matrix = data['matrix']
        titles = [d['title'] for d in matrix]
        self.assertIn('Signed Trial Balance', titles)
        self.assertIn('General Ledger Dump', titles)
        self.assertIn('Bank Statements & BRS', titles)
        # For Tier 4 Enterprise, branch consolidation and IFC matrix are present
        self.assertIn('Branch Trial Balances & Intercompany Matrix', titles)
        self.assertIn('Internal Financial Controls (IFC) Risk Matrix', titles)

    def test_structured_exception_item_with_assertion_and_finding_id(self):
        """Verifies ExceptionItem structured fields: finding_reference, assertion, and management_response"""
        exc = ExceptionItem.objects.create(
            engagement=self.engagement,
            finding_reference='EXC-001',
            title='Unreconciled Intercompany Debit Balance',
            category='CONSOLIDATION',
            severity=ExceptionSeverity.HIGH,
            assertion=AuditAssertion.ACCURACY,
            status=ExceptionStatus.OPEN,
            amount_involved=Decimal('350000.00'),
            explanation='Branch trial balance shows mismatch against corporate control account.',
            recommended_action='Obtain confirmation of balance from Bangalore branch controller.',
            management_response='Timing difference due to transit funds cleared on April 2nd.'
        )
        self.assertEqual(exc.finding_reference, 'EXC-001')
        self.assertEqual(exc.assertion, AuditAssertion.ACCURACY)
        self.assertEqual(exc.management_response, 'Timing difference due to transit funds cleared on April 2nd.')

    def test_review_queue_endpoint_and_separation_of_duties(self):
        """Verifies /review_queue/ API and separation of duties enforcement (SA 220)"""
        wp = Workpaper.objects.create(
            engagement=self.engagement,
            wp_reference='WP-A101',
            title='Cash & Bank Balances Verification',
            audit_area='Current Assets',
            audit_objective='Verify bank balances against statements',
            scope_and_coverage='100% of operational bank accounts',
            testing_methodology='External confirmation and BRS scrutiny',
            results_summary='All accounts reconciled without exceptions',
            proposed_conclusion='Satisfactory audit evidence obtained',
            status=WorkpaperStatus.READY_FOR_REVIEW,
            preparer=self.preparer
        )

        # 1. Fetch Review Queue
        res = self.client.get(f'/api/reporting/workpapers/review_queue/?engagement={self.engagement.id}')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        queue_data = res.json()
        self.assertEqual(queue_data['metrics']['ready_for_review'], 1)
        self.assertEqual(len(queue_data['items']), 1)

        # 2. Separation of duties violation: preparer cannot approve their own workpaper
        self.client.force_authenticate(user=self.preparer)
        fail_res = self.client.post(f'/api/reporting/workpapers/{wp.id}/review_action/', {
            'action_type': 'APPROVE',
            'reason': 'I approve my own work.'
        })
        self.assertEqual(fail_res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Separation of duties violation', fail_res.json()['error'])

        # 3. Manager/Partner approval succeeds
        self.client.force_authenticate(user=self.partner)
        approve_res = self.client.post(f'/api/reporting/workpapers/{wp.id}/review_action/', {
            'action_type': 'APPROVE',
            'reason': 'Approved by engagement partner after reviewing third-party bank confirmations.',
            'verify_evidence': True
        })
        self.assertEqual(approve_res.status_code, status.HTTP_200_OK)
        wp.refresh_from_db()
        self.assertEqual(wp.status, WorkpaperStatus.APPROVED)
        self.assertTrue(wp.evidence_verified)
        self.assertEqual(wp.reviewed_by, self.partner)
