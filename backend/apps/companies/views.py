from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Company, FinancialYear, Engagement, EngagementWorkflowConfig, EntityType, EngagementType
from .serializers import (
    CompanySerializer, FinancialYearSerializer, EngagementSerializer,
    EngagementWorkflowConfigSerializer
)
from decimal import Decimal


class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all().prefetch_related('financial_years', 'engagements')
    serializer_class = CompanySerializer

    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        company = self.get_object()
        fys = company.financial_years.all()
        engagements = company.engagements.all()
        return Response({
            'id': company.id,
            'name': company.name,
            'cin': company.cin,
            'pan': company.pan,
            'gstin': company.gstin,
            'financial_years_count': fys.count(),
            'engagements_count': engagements.count(),
        })

    def perform_destroy(self, instance):
        from apps.ingestion.models import ProcessingRun, Document
        ProcessingRun.objects.filter(company=instance).delete()
        eng_ids = list(instance.engagements.values_list('id', flat=True))
        Document.objects.filter(engagement_id__in=eng_ids).delete()
        instance.delete()

    @action(detail=False, methods=['delete', 'post'])
    def clear_all(self, request):
        count = Company.objects.all().count()
        Company.objects.all().delete()
        from apps.ingestion.models import ProcessingRun, Document
        ProcessingRun.objects.all().delete()
        Document.objects.all().delete()
        return Response({
            'message': f'Successfully removed {count} client entities',
            'deleted_count': count
        }, status=status.HTTP_200_OK)

class FinancialYearViewSet(viewsets.ModelViewSet):
    queryset = FinancialYear.objects.all()
    serializer_class = FinancialYearSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        company_id = self.request.query_params.get('company')
        if company_id:
            qs = qs.filter(company_id=company_id)
        return qs

class EngagementViewSet(viewsets.ModelViewSet):
    queryset = Engagement.objects.all().select_related('company', 'financial_year')
    serializer_class = EngagementSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        company_id = self.request.query_params.get('company')
        if company_id:
            qs = qs.filter(company_id=company_id)
        return qs

    def get_object(self):
        from rest_framework.exceptions import NotFound
        lookup = self.kwargs.get('pk')
        if str(lookup).lower() in ['latest', 'current', 'active', '0']:
            obj = self.get_queryset().first()
            if obj:
                return obj
            raise NotFound("No active audit engagement found. Please upload documents or select a client.")

        if str(lookup).isdigit():
            obj = self.get_queryset().filter(pk=lookup).first()
            if obj:
                return obj
            raise NotFound(f"Engagement with ID {lookup} not found.")

        raise NotFound("No active audit engagement found.")

    @action(detail=True, methods=['get', 'post', 'patch'])
    def workflow_config(self, request, pk=None):
        engagement = self.get_object()
        config, created = EngagementWorkflowConfig.objects.get_or_create(
            engagement=engagement,
            defaults=self._get_default_workflow_params(engagement)
        )
        if request.method in ['POST', 'PATCH']:
            serializer = EngagementWorkflowConfigSerializer(config, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer = EngagementWorkflowConfigSerializer(config)
        return Response(serializer.data)

    def _get_default_workflow_params(self, engagement):
        e_type = engagement.engagement_type
        is_corporate = engagement.company.entity_type in [EntityType.PVT_LTD, EntityType.PUB_LTD]

        if e_type == EngagementType.STATUTORY:
            return {
                'scope_description': "Statutory audit of financial statements under Companies Act 2013.",
                'applicable_framework': 'COMPANIES_ACT_2013',
                'caro_applicable': is_corporate,
                'form_3cd_applicable': True,
                'form_type': '3CA' if is_corporate else '3CB',
                'msmed_applicable': True,
                'schedule_iii_division': 'DIVISION_I',
                'required_documents': [
                    {'title': 'Signed Trial Balance', 'status': 'RECEIVED'},
                    {'title': 'General Ledger Dump', 'status': 'RECEIVED'},
                    {'title': 'Bank Statements & BRS', 'status': 'RECEIVED'},
                    {'title': 'Fixed Asset Register (FAR)', 'status': 'RECEIVED'},
                    {'title': 'Sundry Debtors Ageing Schedule', 'status': 'RECEIVED'},
                    {'title': 'Sundry Creditors & MSME Classification', 'status': 'RECEIVED'},
                    {'title': 'Inventory Valuation & Stock Sheets', 'status': 'RECEIVED'},
                    {'title': 'Statutory Dues Challans (PF/ESI/GST/TDS)', 'status': 'RECEIVED'}
                ],
                'milestones': {'planning': 'COMPLETED', 'risk_assessment': 'COMPLETED', 'fieldwork': 'IN_PROGRESS', 'final_review': 'PENDING'},
                'completion_criteria': {'all_wps_approved': False, 'zero_critical_exceptions': False, 'tb_balanced': True},
                'completion_status': 'IN_PROGRESS'
            }
        elif e_type == EngagementType.TAX_AUDIT:
            return {
                'scope_description': "Tax audit under Section 44AB of Income Tax Act 1961.",
                'applicable_framework': 'INCOME_TAX_ACT_1961',
                'caro_applicable': False,
                'form_3cd_applicable': True,
                'form_type': '3CA' if is_corporate else '3CB',
                'msmed_applicable': True,
                'schedule_iii_division': 'NOT_APPLICABLE',
                'required_documents': [
                    {'title': 'Form 3CD Clause 21(d) Cash Payments Sheet', 'status': 'RECEIVED'},
                    {'title': 'Section 43B(h) MSME Payables Schedule', 'status': 'RECEIVED'},
                    {'title': 'Chapter XVII-B TDS Scrutiny Register', 'status': 'RECEIVED'},
                    {'title': 'Form 26AS & AIS Statements', 'status': 'RECEIVED'},
                    {'title': 'Section 269SS/269T Loan Verification Schedule', 'status': 'RECEIVED'}
                ],
                'milestones': {'clause_scoping': 'COMPLETED', 'testing': 'IN_PROGRESS', 'report_drafting': 'PENDING'},
                'completion_criteria': {'clauses_verified': False, 'challans_matched': True},
                'completion_status': 'IN_PROGRESS'
            }
        elif e_type == EngagementType.STOCK_AUDIT:
            return {
                'scope_description': "Stock & Book Debts inspection for bank working capital hypothecation.",
                'applicable_framework': 'RBI_WORKING_CAPITAL_LENDING_NORMS',
                'caro_applicable': False,
                'form_3cd_applicable': False,
                'form_type': 'NONE',
                'msmed_applicable': False,
                'schedule_iii_division': 'NOT_APPLICABLE',
                'required_documents': [
                    {'title': 'Monthly Stock Statements submitted to Bank', 'status': 'RECEIVED'},
                    {'title': 'Stock Physical Verification Tally Sheets', 'status': 'RECEIVED'},
                    {'title': 'Age-wise Book Debts (Sundry Debtors)', 'status': 'RECEIVED'},
                    {'title': 'Drawing Power (DP) Calculation Ledger', 'status': 'RECEIVED'},
                    {'title': 'Stock Insurance Policy with Bank Clause', 'status': 'RECEIVED'}
                ],
                'milestones': {'stock_verification': 'IN_PROGRESS', 'dp_recalculation': 'PENDING'},
                'completion_criteria': {'dp_reconciled': True, 'insurance_adequate': True},
                'completion_status': 'IN_PROGRESS'
            }
        elif e_type == EngagementType.LLP_AUDIT:
            return {
                'scope_description': "Statutory audit of LLP under Rule 24 of LLP Rules 2009.",
                'applicable_framework': 'LLP_ACT_2008',
                'caro_applicable': False, # Exempt!
                'form_3cd_applicable': False,
                'form_type': '3CB',
                'msmed_applicable': True,
                'schedule_iii_division': 'NOT_APPLICABLE',
                'required_documents': [
                    {'title': 'LLP Agreement and Supplements', 'status': 'RECEIVED'},
                    {'title': 'Statement of Account & Solvency (Form 8)', 'status': 'RECEIVED'},
                    {'title': 'Partner Contribution & Current Accounts', 'status': 'RECEIVED'}
                ],
                'milestones': {'solvency_check': 'IN_PROGRESS', 'form_8_review': 'PENDING'},
                'completion_criteria': {'partner_accounts_reconciled': True},
                'completion_status': 'IN_PROGRESS'
            }
        elif e_type == EngagementType.BANK_AUDIT:
            return {
                'scope_description': "Concurrent / Statutory bank branch audit under RBI guidelines.",
                'applicable_framework': 'RBI_PRUDENTIAL_NORMS_IRAC',
                'caro_applicable': False,
                'form_3cd_applicable': False,
                'form_type': 'NONE',
                'msmed_applicable': False,
                'schedule_iii_division': 'NOT_APPLICABLE',
                'required_documents': [
                    {'title': 'Loan Sanction Files & Security Documents', 'status': 'RECEIVED'},
                    {'title': 'IRAC NPA Classification Report', 'status': 'RECEIVED'},
                    {'title': 'Early Warning Signals (SMA 0/1/2) Report', 'status': 'RECEIVED'}
                ],
                'milestones': {'irac_testing': 'IN_PROGRESS', 'npa_review': 'PENDING'},
                'completion_criteria': {'irac_classification_verified': True},
                'completion_status': 'IN_PROGRESS'
            }
        else: # INTERNAL or other
            return {
                'scope_description': "Internal audit of risk management and operational controls.",
                'applicable_framework': 'ICAI_STANDARDS_ON_INTERNAL_AUDIT_SIA',
                'caro_applicable': False,
                'form_3cd_applicable': False,
                'form_type': 'NONE',
                'msmed_applicable': False,
                'schedule_iii_division': 'NOT_APPLICABLE',
                'required_documents': [
                    {'title': 'Internal Financial Controls (IFC) Matrix', 'status': 'RECEIVED'},
                    {'title': 'Delegation of Authority (DoA) Manual', 'status': 'RECEIVED'}
                ],
                'milestones': {'process_walkthrough': 'IN_PROGRESS', 'remediation': 'PENDING'},
                'completion_criteria': {'findings_reviewed': True},
                'completion_status': 'IN_PROGRESS'
            }

    @action(detail=True, methods=['post'])
    def calculate_materiality(self, request, pk=None):
        """Calculates SA 320 materiality based on input benchmark figure"""
        engagement = self.get_object()
        benchmark = request.data.get('benchmark', engagement.materiality_benchmark)
        benchmark_amount = Decimal(str(request.data.get('benchmark_amount', '10000000.00')))
        percentage = Decimal(str(request.data.get('percentage', str(engagement.benchmark_percentage))))

        overall = (benchmark_amount * percentage) / Decimal('100.00')
        performance = overall * Decimal('0.75')
        clearly_trivial = overall * Decimal('0.05')

        engagement.materiality_benchmark = benchmark
        engagement.benchmark_percentage = percentage
        engagement.overall_materiality = overall
        engagement.performance_materiality = performance
        engagement.clearly_trivial_threshold = clearly_trivial
        engagement.save()

        return Response({
            'benchmark': benchmark,
            'benchmark_amount': str(benchmark_amount),
            'benchmark_percentage': str(percentage),
            'overall_materiality': str(overall),
            'performance_materiality': str(performance),
            'clearly_trivial_threshold': str(clearly_trivial)
        })

    @action(detail=True, methods=['get'])
    def document_matrix(self, request, pk=None):
        """Returns the dynamic document requirements checklist matrix tailored to business tier and engagement"""
        engagement = self.get_object()
        company = engagement.company
        matrix = EngagementWorkflowConfig.get_document_matrix_for(
            entity_type=company.entity_type,
            business_tier=company.business_tier,
            engagement_type=engagement.engagement_type
        )
        return Response({
            'company_tier': company.business_tier,
            'entity_type': company.entity_type,
            'engagement_type': engagement.engagement_type,
            'matrix': matrix
        })

    @action(detail=True, methods=['get'])
    def completion_checklist(self, request, pk=None):
        """Returns the real-time 9-point statutory engagement completion checklist"""
        from .completion_service import EngagementCompletionService
        engagement = self.get_object()
        result = EngagementCompletionService.evaluate_checklist(engagement)
        return Response(result)

    @action(detail=True, methods=['post'])
    def finalize(self, request, pk=None):
        """Attempts to finalize the engagement. Fails closed if mandatory blockers remain."""
        from .completion_service import EngagementCompletionService
        engagement = self.get_object()
        justification = request.data.get('justification', '')
        result = EngagementCompletionService.finalize_engagement(engagement, user=request.user, justification=justification)
        if not result['success']:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)

    @action(detail=True, methods=['post'])
    def override_exception(self, request, pk=None):
        """Allows authorized CA partner to record a permitted exception with written justification"""
        from .completion_service import EngagementCompletionService
        engagement = self.get_object()
        code = request.data.get('code')
        reason = request.data.get('reason')
        if not code or not reason:
            return Response({'error': 'Both code and reason are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = EngagementCompletionService.record_permitted_exception(engagement, code=code, reason=reason, user=request.user)
            return Response(result)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class EngagementWorkflowConfigViewSet(viewsets.ModelViewSet):
    queryset = EngagementWorkflowConfig.objects.all().select_related('engagement')
    serializer_class = EngagementWorkflowConfigSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        engagement_id = self.request.query_params.get('engagement')
        if engagement_id:
            qs = qs.filter(engagement_id=engagement_id)
        return qs

