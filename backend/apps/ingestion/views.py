import os
import mimetypes
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import FileResponse, Http404
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from .models import Document, DocumentStatus, DocumentType, ProcessingJob, ExtractedRecord, ProcessingRun
from .serializers import DocumentSerializer, ProcessingJobSerializer, ExtractedRecordSerializer, ProcessingRunSerializer
from .services import IngestionPipelineService
from .orchestrator import AutomationOrchestratorService
from apps.companies.models import Engagement, Company
from apps.core.security import sanitize_filename, validate_uploaded_file
from rest_framework.exceptions import ValidationError

class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all().select_related('engagement')
    serializer_class = DocumentSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        qs = super().get_queryset()
        engagement_id = self.request.query_params.get('engagement')
        if engagement_id:
            qs = qs.filter(engagement_id=engagement_id)
        return qs

    def create(self, request, *args, **kwargs):
        file_obj = request.FILES.get('file')
        if not file_obj or file_obj.size == 0:
            return Response({'error': 'No file was provided or uploaded file is empty (0 bytes)'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            validate_uploaded_file(file_obj)
        except ValidationError as ve:
            return Response({'error': str(ve.detail[0] if isinstance(ve.detail, list) else ve.detail)}, status=status.HTTP_400_BAD_REQUEST)

        # Sanitize filename against directory traversal
        clean_name = sanitize_filename(file_obj.name)
        file_obj.name = clean_name

        engagement_id = request.data.get('engagement')
        company_name = request.data.get('company_name', '').strip()

        # Handle engagement selection or auto-creation for quick upload
        engagement = None
        if engagement_id:
            engagement = Engagement.objects.filter(id=engagement_id).first()

        if not engagement:
            if not company_name:
                company_name = "New Audit Entity"
            
            company, _ = Company.objects.get_or_create(
                name=company_name,
                defaults={'cin': 'U72900MH2021PTC123456', 'pan': 'AABCA1234F', 'gstin': '27AABCA1234F1Z5'}
            )
            fy, _ = company.financial_years.get_or_create(
                label='FY 2024-25',
                defaults={'start_date': '2024-04-01', 'end_date': '2025-03-31'}
            )
            engagement, _ = Engagement.objects.get_or_create(
                company=company,
                financial_year=fy,
                title='Statutory Audit FY 2024-25',
                defaults={'engagement_type': 'STATUTORY'}
            )

        # 1. Compute SHA-256 Hash
        file_hash = Document.calculate_sha256(file_obj)

        # 2. Check for duplicate upload
        existing_doc = Document.objects.filter(engagement=engagement, file_hash=file_hash).first()
        is_duplicate = False
        if existing_doc:
            is_duplicate = True

        mime_type, _ = mimetypes.guess_type(file_obj.name)
        mime_type = mime_type or 'application/octet-stream'

        # 3. Create Document record
        doc = Document.objects.create(
            engagement=engagement,
            original_filename=file_obj.name,
            file=file_obj,
            file_hash=file_hash,
            file_size_bytes=file_obj.size,
            mime_type=mime_type,
            document_type=request.data.get('document_type', DocumentType.UNKNOWN),
            status=DocumentStatus.UPLOADED
        )

        # 4. Trigger processing pipeline synchronously
        try:
            job = IngestionPipelineService.process_document(doc)
            serializer = self.get_serializer(doc)
            data = serializer.data
            data['is_duplicate_hash'] = is_duplicate
            if is_duplicate:
                data['duplicate_warning'] = f"Warning: Exact duplicate of previously uploaded document '{existing_doc.original_filename}'."
            return Response(data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({
                'id': doc.id,
                'status': 'FAILED',
                'error': str(e),
                'message': 'Failed during parsing or normalization phase'
            }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        doc = self.get_object()
        job = IngestionPipelineService.process_document(doc)
        return Response({'message': 'Reprocessing completed', 'job_id': job.id, 'status': doc.status})

    @action(detail=True, methods=['get'])
    def records(self, request, pk=None):
        doc = self.get_object()
        records = doc.extracted_records.all()
        page = self.paginate_queryset(records)
        if page is not None:
            serializer = ExtractedRecordSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = ExtractedRecordSerializer(records, many=True)
        return Response(serializer.data)


class ProcessingRunViewSet(viewsets.ModelViewSet):
    queryset = ProcessingRun.objects.all().select_related('company', 'engagement').prefetch_related('documents', 'generated_reports')
    serializer_class = ProcessingRunSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        qs = super().get_queryset()
        company_id = self.request.query_params.get('company') or self.request.query_params.get('company_id')
        if company_id:
            qs = qs.filter(company_id=company_id)
        engagement_id = self.request.query_params.get('engagement') or self.request.query_params.get('engagement_id')
        if engagement_id:
            qs = qs.filter(engagement_id=engagement_id)
        if self.request.user and self.request.user.is_authenticated and not self.request.user.is_staff:
            from django.db.models import Q
            qs = qs.filter(
                Q(company__engagements__lead_partner=self.request.user) |
                Q(company__engagements__audit_manager=self.request.user) |
                Q(initiated_by=self.request.user)
            ).distinct()
        return qs

    def get_object(self):
        lookup = self.kwargs.get('pk')
        if str(lookup).isdigit():
            obj = ProcessingRun.objects.filter(id=lookup).first()
            if obj:
                return obj
        obj = ProcessingRun.objects.filter(run_id=lookup).first()
        if not obj:
            raise Http404(f"ProcessingRun '{lookup}' not found.")
        return obj

    def create(self, request, *args, **kwargs):
        # Support single archive via 'archive', batch files via 'files', or single via 'file'
        archive = request.FILES.get('archive')
        files = request.FILES.getlist('files')
        if archive:
            files = [archive]
        elif not files:
            single_file = request.FILES.get('file')
            if single_file:
                files = [single_file]

        if not files:
            return Response({'error': 'No document archive or files provided. Please select client documents archive.'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate each file
        for f in files:
            if f.size == 0:
                return Response({'error': f"Uploaded file '{f.name}' is empty (0 bytes)."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                validate_uploaded_file(f)
            except ValidationError as ve:
                return Response({'error': f"File '{f.name}': {str(ve.detail[0] if isinstance(ve.detail, list) else ve.detail)}"}, status=status.HTTP_400_BAD_REQUEST)
            clean_name = sanitize_filename(f.name)
            f.name = clean_name

        company_id = request.data.get('company') or request.data.get('company_id')
        company_name = request.data.get('company_name', '').strip()
        engagement_id = request.data.get('engagement') or request.data.get('engagement_id')
        business_tier = request.data.get('business_tier', 'TIER_3_MID')

        company = None
        if company_id:
            company = Company.objects.filter(id=company_id).first()
        if not company and company_name:
            company, _ = Company.objects.get_or_create(
                name=company_name,
                defaults={'cin': 'U29100MH2020PTC345678', 'pan': 'AABCV9876K', 'gstin': '27AABCV9876K1Z8', 'business_tier': business_tier}
            )
        elif company and business_tier and company.business_tier != business_tier:
            company.business_tier = business_tier
            company.save(update_fields=['business_tier'])

        engagement = None
        if engagement_id:
            engagement = Engagement.objects.filter(id=engagement_id).first()
        if not engagement and company:
            fy, _ = company.financial_years.get_or_create(
                label=request.data.get('fy_label', 'FY 2024-25'),
                defaults={'start_date': '2024-04-01', 'end_date': '2025-03-31'}
            )
            engagement, _ = Engagement.objects.get_or_create(
                company=company,
                financial_year=fy,
                title=f"{request.data.get('audit_type', 'Statutory')} Audit {fy.label}",
                defaults={'engagement_type': request.data.get('audit_type', 'STATUTORY').upper()}
            )

        # 1. Initialize run
        run = AutomationOrchestratorService.create_run(
            files=files,
            company_name=company.name if company else company_name,
            financial_year_label=request.data.get('fy_label', 'FY 2024-25'),
            user=request.user if request.user.is_authenticated else None,
            engagement_id=engagement.id if engagement else None
        )

        # 2. Execute 14-stage pipeline
        run = AutomationOrchestratorService.execute_pipeline(
            run=run,
            uploaded_files=files,
            company_hint=company.name if company else company_name,
            fy_hint=request.data.get('fy_label', 'FY 2024-25')
        )

        serializer = self.get_serializer(run)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        run = self.get_object()
        run = AutomationOrchestratorService.execute_pipeline(run)
        serializer = self.get_serializer(run)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def latest(self, request):
        latest_run = ProcessingRun.objects.first()
        if not latest_run:
            return Response({'detail': 'No processing runs found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.get_serializer(latest_run)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def download_package(self, request, pk=None):
        run = self.get_object()
        if request.user and request.user.is_authenticated and not request.user.is_staff:
            is_authorized = (
                run.initiated_by == request.user or
                (run.engagement and (
                    run.engagement.lead_partner == request.user or
                    run.engagement.audit_manager == request.user or
                    run.engagement.company.engagements.filter(lead_partner=request.user).exists()
                ))
            )
            if not is_authorized:
                return Response({'error': "Unauthorized: You do not have permissions to download this entity's audit package."}, status=status.HTTP_403_FORBIDDEN)

        if not run.zip_package:
            if run.engagement:
                import io, zipfile
                from apps.reporting.exporters import ReportExporterService
                from django.core.files.base import ContentFile
                pdf_bytes = ReportExporterService.export_consolidated_pdf(run.engagement)
                excel_bytes = ReportExporterService.export_consolidated_excel(run.engagement)
                csv_text = ReportExporterService.export_consolidated_csv(run.engagement)
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
                    zf.writestr("Consolidated_Audit_Report.pdf", pdf_bytes)
                    zf.writestr("Consolidated_Audit_Schedules.xlsx", excel_bytes)
                    zf.writestr("Financial_Summary_Extract.csv", csv_text)
                zip_bytes = zip_buffer.getvalue()
                zip_buffer.close()
                zip_filename = f"{run.run_id}_Complete_Audit_Package.zip"
                run.zip_package.save(zip_filename, ContentFile(zip_bytes), save=True)
            else:
                return Response({'error': 'No audit package ZIP available for this run.'}, status=status.HTTP_404_NOT_FOUND)

        file_handle = run.zip_package.open('rb')
        response = FileResponse(file_handle, content_type='application/zip')
        filename = f"Captrix_Audit_Package_{run.run_id}.zip"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['X-Content-Type-Options'] = 'nosniff'
        return response

    @action(detail=False, methods=['post'])
    def run_synthetic_demo(self, request):
        """1-click automated run using verified synthetic acceptance company data."""
        # Restrict demo runner outside development and controlled testing environments
        if not settings.DEBUG and not os.environ.get('ALLOW_SYNTHETIC_DEMO'):
            return Response(
                {'error': 'Synthetic demo runner is restricted to development and testing environments.'},
                status=status.HTTP_403_FORBIDDEN
            )

        test_data_dir = os.path.join(settings.BASE_DIR, 'test_data', 'synthetic_company')
        if not os.path.exists(test_data_dir):
            return Response({'error': 'Synthetic test data directory not found.'}, status=status.HTTP_404_NOT_FOUND)

        demo_files = [
            'trial_balance_fy24_25.csv',
            'general_ledger_dump.csv',
            'bank_statement_fy24_25.csv',
            'gstr_2b_itc_statement.csv',
            'purchase_register.csv',
            'fixed_asset_register.csv',
            'subledger_debtors_creditors.csv',
        ]

        uploaded_files = []
        for fname in demo_files:
            fpath = os.path.join(test_data_dir, fname)
            if os.path.exists(fpath):
                with open(fpath, 'rb') as f:
                    content = f.read()
                    uploaded_files.append(SimpleUploadedFile(fname, content, content_type='text/csv'))

        if not uploaded_files:
            return Response({'error': 'No synthetic files found to run demo.'}, status=status.HTTP_404_NOT_FOUND)

        company, _ = Company.objects.get_or_create(
            name='[TEST DEMO] Vanguard Industrial Automations Private Limited',
            defaults={
                'cin': 'TEST-U29100MH2020PTC345678',
                'pan': 'TESTV9876K',
                'gstin': '27TESTV9876K1Z8',
                'registered_address': 'Plot 42, Demo Industrial Estate, Pune, MH (TEST ENVIRONMENT)'
            }
        )
        fy, _ = company.financial_years.get_or_create(
            label='FY 2024-25',
            defaults={'start_date': '2024-04-01', 'end_date': '2025-03-31'}
        )
        engagement, _ = Engagement.objects.get_or_create(
            company=company,
            financial_year=fy,
            title='[SYNTHETIC TEST DATASET] Statutory Audit FY 2024-25',
            defaults={'engagement_type': 'STATUTORY'}
        )

        run = AutomationOrchestratorService.create_run(
            files=uploaded_files,
            company_name=company.name,
            financial_year_label='FY 2024-25',
            user=request.user if request.user.is_authenticated else None,
            engagement_id=engagement.id
        )
        run.summary_metrics['is_synthetic_test_data'] = True
        run.save(update_fields=['summary_metrics'])

        run = AutomationOrchestratorService.execute_pipeline(
            run=run,
            uploaded_files=uploaded_files,
            company_hint=company.name,
            fy_hint='FY 2024-25'
        )
        run.summary_metrics['is_synthetic_test_data'] = True
        run.save(update_fields=['summary_metrics'])

        serializer = self.get_serializer(run)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


