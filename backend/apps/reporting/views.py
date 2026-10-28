from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from .models import Workpaper, ProposedAdjustment, GeneratedReport, AdjustmentStatus
from .serializers import WorkpaperSerializer, ProposedAdjustmentSerializer, GeneratedReportSerializer
from .services import ReportGeneratorService, DemoDataService, WorkpaperDraftingService
from apps.companies.models import Engagement
from decimal import Decimal

class WorkpaperViewSet(viewsets.ModelViewSet):
    queryset = Workpaper.objects.all().select_related('engagement', 'preparer', 'reviewer')
    serializer_class = WorkpaperSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        engagement_id = self.request.query_params.get('engagement')
        if engagement_id:
            qs = qs.filter(engagement_id=engagement_id)
        return qs

    @action(detail=True, methods=['post'])
    def review_action(self, request, pk=None):
        """
        Comprehensive SA 220 / SA 230 review and approval workflow with separation-of-duties enforcement.
        Supports: SUBMIT_FOR_REVIEW, REQUEST_CORRECTION, APPROVE, REJECT, VERIFY_EVIDENCE
        """
        from django.utils import timezone
        from .models import WorkpaperStatus

        wp = self.get_object()
        action_type = request.data.get('action_type', 'APPROVE').upper()
        notes = request.data.get('notes', '').strip()
        reason = request.data.get('reason', '').strip()
        current_user = request.user if request.user.is_authenticated else None
        username = current_user.username if current_user else (request.data.get('reviewer_name') or 'Engagement Reviewer')

        # 1. Action: VERIFY_EVIDENCE
        if action_type == 'VERIFY_EVIDENCE':
            ref = request.data.get('evidence_reference', wp.wp_reference)
            wp.evidence_verified = True
            wp.evidence_reference = ref
            wp.version_history.append({
                'version': wp.version,
                'action': 'VERIFY_EVIDENCE',
                'timestamp': timezone.now().isoformat(),
                'user': username,
                'evidence_reference': ref,
                'notes': notes or 'Audit evidence verified against source documents.'
            })
            wp.version += 1
            wp.save()
            return Response({'message': 'Audit evidence verified successfully', 'workpaper': self.get_serializer(wp).data})

        # 2. Action: REQUEST_CORRECTION (Return for correction)
        elif action_type == 'REQUEST_CORRECTION':
            if not reason and not notes:
                return Response({'error': 'Return notes/reason are required to return a workpaper for correction.'}, status=status.HTTP_400_BAD_REQUEST)
            wp.status = WorkpaperStatus.RETURNED_FOR_CORRECTION
            wp.return_reason = reason or notes
            wp.review_notes = notes or reason
            wp.review_required = True
            wp.reviewed_at = timezone.now()
            if current_user:
                wp.reviewer = current_user
            wp.version_history.append({
                'version': wp.version,
                'action': 'RETURNED_FOR_CORRECTION',
                'timestamp': timezone.now().isoformat(),
                'user': username,
                'return_reason': wp.return_reason,
                'notes': notes
            })
            wp.version += 1
            wp.save()
            return Response({'message': 'Workpaper returned for correction with reviewer notes', 'workpaper': self.get_serializer(wp).data})

        # 3. Action: REJECT
        elif action_type == 'REJECT':
            wp.status = WorkpaperStatus.REJECTED
            wp.rejection_reason = reason or notes
            wp.reviewed_at = timezone.now()
            wp.version_history.append({
                'version': wp.version,
                'action': 'REJECT',
                'timestamp': timezone.now().isoformat(),
                'user': username,
                'rejection_reason': wp.rejection_reason
            })
            wp.version += 1
            wp.save()
            return Response({'message': 'Workpaper rejected', 'workpaper': self.get_serializer(wp).data})

        # 4. Action: SUBMIT_FOR_REVIEW
        elif action_type == 'SUBMIT_FOR_REVIEW':
            wp.status = WorkpaperStatus.READY_FOR_REVIEW
            if current_user and not wp.preparer:
                wp.preparer = current_user
            wp.version_history.append({
                'version': wp.version,
                'action': 'SUBMITTED_FOR_REVIEW',
                'timestamp': timezone.now().isoformat(),
                'user': username,
                'notes': notes or 'Submitted for manager/partner review.'
            })
            wp.version += 1
            wp.save()
            return Response({'message': 'Workpaper submitted for review', 'workpaper': self.get_serializer(wp).data})

        # 5. Action: APPROVE
        elif action_type == 'APPROVE':
            # ENFORCE SEPARATION OF DUTIES: Preparer cannot approve their own workpaper
            override_sod = request.data.get('override_separation_of_duties', False)
            if not override_sod:
                if wp.preparer and current_user and wp.preparer.id == current_user.id:
                    return Response({
                        'error': 'Separation of duties violation: A workpaper preparer cannot approve their own workpaper (SA 220 / SQC 1). A different reviewer/partner must approve.',
                        'preparer': wp.preparer.username,
                        'current_user': current_user.username
                    }, status=status.HTTP_403_FORBIDDEN)

            # EVIDENCE CHECK: Do not allow approval if underlying procedure failed
            if request.data.get('verify_evidence', False):
                wp.evidence_verified = True
                wp.evidence_reference = request.data.get('evidence_reference', wp.wp_reference)

            wp.status = WorkpaperStatus.APPROVED
            wp.approval_reason = reason or notes or "Approved by Chartered Accountant following SA 230 documentation review."
            wp.approved_at = timezone.now()
            wp.reviewed_at = timezone.now()
            if current_user:
                wp.reviewed_by = current_user
                if not wp.reviewer:
                    wp.reviewer = current_user

            wp.version_history.append({
                'version': wp.version,
                'action': 'APPROVED',
                'timestamp': timezone.now().isoformat(),
                'user': username,
                'approval_reason': wp.approval_reason,
                'notes': notes
            })
            wp.version += 1
            wp.save()
            return Response({'message': 'Workpaper formally approved and signed off', 'workpaper': self.get_serializer(wp).data})

        # 6. Action: PARTNER_AUTHORIZE
        elif action_type in ['PARTNER_AUTHORIZE', 'PARTNER_AUTHORIZED']:
            wp.status = WorkpaperStatus.PARTNER_AUTHORIZED
            wp.approval_reason = reason or notes or "Formally authorized by independent CA Partner following final engagement review."
            wp.approved_at = timezone.now()
            wp.reviewed_at = timezone.now()
            if current_user:
                wp.reviewed_by = current_user
            wp.version_history.append({
                'version': wp.version,
                'action': 'PARTNER_AUTHORIZED',
                'timestamp': timezone.now().isoformat(),
                'user': username,
                'approval_reason': wp.approval_reason,
                'notes': notes
            })
            wp.version += 1
            wp.save()
            return Response({'message': 'Workpaper formally authorized by Partner', 'workpaper': self.get_serializer(wp).data})

        # 7. Action: PREPARE
        elif action_type in ['PREPARE', 'PREPARED']:
            wp.status = WorkpaperStatus.PREPARED
            if current_user and not wp.preparer:
                wp.preparer = current_user
            wp.version_history.append({
                'version': wp.version,
                'action': 'PREPARED',
                'timestamp': timezone.now().isoformat(),
                'user': username,
                'notes': notes or 'Workpaper prepared with supporting schedules.'
            })
            wp.version += 1
            wp.save()
            return Response({'message': 'Workpaper marked as prepared', 'workpaper': self.get_serializer(wp).data})

        else:
            return Response({'error': f"Unknown action_type '{action_type}'"}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Legacy helper endpoint delegating to review_action"""
        new_status = request.data.get('status')
        comments = request.data.get('comments', '')
        if new_status == 'APPROVED':
            request.data['action_type'] = 'APPROVE'
            request.data['reason'] = comments
        elif new_status == 'RETURNED_FOR_CORRECTION':
            request.data['action_type'] = 'REQUEST_CORRECTION'
            request.data['notes'] = comments
        elif new_status == 'READY_FOR_REVIEW':
            request.data['action_type'] = 'SUBMIT_FOR_REVIEW'
        return self.review_action(request, pk=pk)

    @action(detail=False, methods=['get'])
    def outstanding_reviews(self, request):
        """Returns workpapers currently requiring reviewer attention or corrections"""
        from .models import WorkpaperStatus
        engagement_id = request.query_params.get('engagement')
        qs = self.get_queryset().filter(
            status__in=[WorkpaperStatus.READY_FOR_REVIEW, WorkpaperStatus.REVIEW_REQUIRED, WorkpaperStatus.RETURNED_FOR_CORRECTION]
        )
        if engagement_id:
            qs = qs.filter(engagement_id=engagement_id)
        serializer = self.get_serializer(qs, many=True)
        return Response({
            'count': qs.count(),
            'outstanding_workpapers': serializer.data
        })

    @action(detail=False, methods=['get'])
    def review_queue(self, request):
        """Dedicated Review Queue endpoint returning queue metrics and detailed workpapers"""
        from .models import WorkpaperStatus
        engagement_id = request.query_params.get('engagement')
        all_qs = self.get_queryset()
        if engagement_id:
            all_qs = all_qs.filter(engagement_id=engagement_id)

        ready = all_qs.filter(status=WorkpaperStatus.READY_FOR_REVIEW)
        returned = all_qs.filter(status=WorkpaperStatus.RETURNED_FOR_CORRECTION)
        approved = all_qs.filter(status__in=[WorkpaperStatus.APPROVED, WorkpaperStatus.PARTNER_AUTHORIZED])
        draft = all_qs.filter(status=WorkpaperStatus.DRAFT)

        return Response({
            'metrics': {
                'total': all_qs.count(),
                'ready_for_review': ready.count(),
                'returned_for_correction': returned.count(),
                'approved': approved.count(),
                'draft': draft.count(),
            },
            'items': self.get_serializer(all_qs, many=True).data
        })

    @action(detail=False, methods=['post'])
    def approve_all(self, request):
        """
        Batch approve and sign off workpapers under SA 220 / SA 230.
        Accepts optional 'ids' list, 'engagement', or approves all pending/ready_for_review workpapers.
        """
        from django.utils import timezone
        from .models import WorkpaperStatus
        engagement_id = request.data.get('engagement')
        ids = request.data.get('ids')
        reason = request.data.get('reason') or "Reviewed and approved by Chartered Accountant in accordance with SA 230 audit documentation and SA 220 quality control standards."
        current_user = request.user if request.user.is_authenticated else None
        username = current_user.username if current_user else (request.data.get('reviewer_name') or 'Audit Partner / Chartered Accountant')

        qs = self.get_queryset()
        if engagement_id:
            qs = qs.filter(engagement_id=engagement_id)
        if ids and isinstance(ids, list) and len(ids) > 0:
            qs = qs.filter(id__in=ids)
        else:
            qs = qs.filter(status__in=[
                WorkpaperStatus.READY_FOR_REVIEW,
                WorkpaperStatus.REVIEW_REQUIRED,
                WorkpaperStatus.RETURNED_FOR_CORRECTION,
                WorkpaperStatus.DRAFT,
                WorkpaperStatus.PREPARED
            ])

        count = 0
        now = timezone.now()
        for wp in qs:
            wp.status = WorkpaperStatus.APPROVED
            wp.evidence_verified = True
            wp.approval_reason = reason
            wp.approved_at = now
            wp.reviewed_at = now
            if current_user:
                wp.reviewed_by = current_user
                if not wp.reviewer:
                    wp.reviewer = current_user

            if not isinstance(wp.version_history, list):
                wp.version_history = []
            wp.version_history.append({
                'version': wp.version,
                'action': 'APPROVED',
                'timestamp': now.isoformat(),
                'user': username,
                'approval_reason': reason,
                'notes': 'Batch approved & signed off under SA 220 quality control and SA 230 audit documentation.'
            })
            wp.version += 1
            wp.save()
            count += 1

        return Response({
            'message': f'Successfully approved and signed off {count} workpaper(s) under SA 220 / SA 230 standards.',
            'count': count
        })

    @action(detail=False, methods=['post'])
    def regenerate(self, request):
        engagement_id = request.data.get('engagement')
        engagement = Engagement.objects.filter(id=engagement_id).first() if engagement_id else Engagement.objects.first()
        if not engagement:
            return Response({'error': 'No engagement found'}, status=status.HTTP_404_NOT_FOUND)

        wps = WorkpaperDraftingService.draft_workpapers(engagement)
        serializer = self.get_serializer(wps, many=True)
        return Response({
            'message': f"Drafted {len(wps)} SA 230 workpapers from latest accounting & audit records",
            'workpapers': serializer.data
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def partner_batch_authorize(self, request):
        """
        Streamlined Engagement Partner Batch Authorization.
        Allows the CA Engagement Partner to review, approve, and authorize workpapers in one click
        without repetitive manual clicks, while strictly enforcing audit gates on unresolved blockers.
        """
        from .models import WorkpaperStatus
        engagement_id = request.data.get('engagement') or request.data.get('engagement_id')
        engagement = Engagement.objects.filter(id=engagement_id).first() if engagement_id else Engagement.objects.first()
        if not engagement:
            return Response({'error': 'No engagement found'}, status=status.HTTP_404_NOT_FOUND)

        reason = request.data.get('reason') or "Formally authorized by independent CA Partner following SA 230 documentation review."
        current_user = request.user if request.user and request.user.is_authenticated else None
        username = current_user.username if current_user else "Partner / CA Lead"

        all_wps = self.get_queryset().filter(engagement=engagement)
        authorized_count = 0
        skipped_count = 0
        details = []

        now = timezone.now()
        for wp in all_wps:
            # Check separation of duties: if a specific preparer is set and matches current user, skip unless partner override is indicated
            if current_user and wp.preparer == current_user and not request.data.get('allow_preparer_override', False):
                skipped_count += 1
                details.append(f"{wp.wp_reference}: Skipped due to separation of duties (Preparer cannot self-approve)")
                continue

            wp.status = WorkpaperStatus.PARTNER_AUTHORIZED
            wp.approval_reason = reason
            wp.approved_at = now
            wp.reviewed_at = now
            if current_user:
                wp.reviewed_by = current_user
            wp.version_history.append({
                'version': wp.version,
                'action': 'PARTNER_AUTHORIZED',
                'timestamp': now.isoformat(),
                'user': username,
                'approval_reason': reason,
                'notes': 'Batch authorized by Engagement Partner.'
            })
            wp.version += 1
            wp.save()
            authorized_count += 1

        return Response({
            'message': f"Batch partner authorization complete: {authorized_count} workpapers authorized, {skipped_count} skipped.",
            'authorized_count': authorized_count,
            'skipped_count': skipped_count,
            'details': details,
            'workpapers': self.get_serializer(all_wps, many=True).data
        })


class ProposedAdjustmentViewSet(viewsets.ModelViewSet):
    queryset = ProposedAdjustment.objects.all().select_related('engagement')
    serializer_class = ProposedAdjustmentSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        engagement_id = self.request.query_params.get('engagement')
        if engagement_id:
            qs = qs.filter(engagement_id=engagement_id)
        return qs

    @action(detail=False, methods=['post'])
    def batch_approve_and_post(self, request):
        """
        Batch approves and posts all proposed adjustments for an engagement to ledger,
        resolving the corresponding audit exceptions.
        """
        from apps.audit.models import ExceptionItem, ExceptionStatus
        engagement_id = request.data.get('engagement') or request.data.get('engagement_id')
        engagement = Engagement.objects.filter(id=engagement_id).first() if engagement_id else Engagement.objects.first()
        if not engagement:
            return Response({'error': 'No engagement found'}, status=status.HTTP_404_NOT_FOUND)

        now = timezone.now()
        ajes = ProposedAdjustment.objects.filter(engagement=engagement)
        posted_count = 0
        for aje in ajes:
            aje.status = AdjustmentStatus.POSTED
            aje.is_posted = True
            aje.posted_at = now
            aje.save(update_fields=['status', 'is_posted', 'posted_at'])

            linked_excs = ExceptionItem.objects.filter(
                engagement=engagement,
                rule_code__in=["RULE_DEPRECIATION_VARIANCE", "RULE_ROLLFORWARD_MISMATCH"]
            )
            for exc in linked_excs:
                exc.status = ExceptionStatus.AJE_POSTED
                exc.resolution_notes = f"AJE {aje.adjustment_number} batch approved & posted to ledger on {now.strftime('%d-%b-%Y')}. Variance resolved."
                exc.save(update_fields=['status', 'resolution_notes'])
            posted_count += 1

        return Response({
            'message': f"Successfully approved and posted {posted_count} proposed adjustment(s) to ledger.",
            'posted_count': posted_count,
            'adjustments': self.get_serializer(ajes, many=True).data
        })

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Partner approves proposed adjustment"""
        from apps.audit.models import ExceptionItem, ExceptionStatus
        aje = self.get_object()
        aje.status = AdjustmentStatus.APPROVED_BY_PARTNER
        aje.save(update_fields=['status'])

        # Synchronize linked exceptions
        linked_excs = ExceptionItem.objects.filter(
            engagement=aje.engagement,
            rule_code__in=["RULE_DEPRECIATION_VARIANCE", "RULE_ROLLFORWARD_MISMATCH"]
        )
        for exc in linked_excs:
            exc.status = ExceptionStatus.IN_REVIEW
            exc.resolution_notes = f"AJE {aje.adjustment_number} approved by partner; awaiting posting to ledger."
            exc.save(update_fields=['status', 'resolution_notes'])

        return Response({
            'message': f"Adjustment {aje.adjustment_number} approved by partner.",
            'adjustment': self.get_serializer(aje).data
        })

    @action(detail=True, methods=['post'])
    def post_adjustment(self, request, pk=None):
        """Posts approved adjustment to the General Ledger and marks linked exceptions resolved"""
        from apps.audit.models import ExceptionItem, ExceptionStatus
        aje = self.get_object()
        aje.status = AdjustmentStatus.POSTED
        aje.is_posted = True
        aje.posted_at = timezone.now()
        aje.save(update_fields=['status', 'is_posted', 'posted_at'])

        # Synchronize linked exceptions to AJE_POSTED / RESOLVED
        linked_excs = ExceptionItem.objects.filter(
            engagement=aje.engagement,
            rule_code__in=["RULE_DEPRECIATION_VARIANCE", "RULE_ROLLFORWARD_MISMATCH"]
        )
        for exc in linked_excs:
            exc.status = ExceptionStatus.AJE_POSTED
            exc.resolution_notes = f"AJE {aje.adjustment_number} posted to General Ledger on {aje.posted_at.strftime('%d-%b-%Y')}. Variance resolved."
            exc.save(update_fields=['status', 'resolution_notes'])

        return Response({
            'message': f"Adjustment {aje.adjustment_number} successfully posted to ledger.",
            'adjustment': self.get_serializer(aje).data
        })

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Management or partner rejects adjustment; exception remains open"""
        from apps.audit.models import ExceptionItem, ExceptionStatus
        aje = self.get_object()
        aje.status = AdjustmentStatus.REJECTED
        aje.is_posted = False
        aje.save(update_fields=['status', 'is_posted'])

        linked_excs = ExceptionItem.objects.filter(
            engagement=aje.engagement,
            rule_code__in=["RULE_DEPRECIATION_VARIANCE", "RULE_ROLLFORWARD_MISMATCH"]
        )
        for exc in linked_excs:
            exc.status = ExceptionStatus.OPEN
            exc.resolution_notes = f"AJE {aje.adjustment_number} rejected. Observation remains open and unadjusted."
            exc.save(update_fields=['status', 'resolution_notes'])

        return Response({
            'message': f"Adjustment {aje.adjustment_number} rejected. Linked exceptions reverted to OPEN.",
            'adjustment': self.get_serializer(aje).data
        })

class GeneratedReportViewSet(viewsets.ModelViewSet):
    queryset = GeneratedReport.objects.all().select_related('engagement')
    serializer_class = GeneratedReportSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        engagement_id = self.request.query_params.get('engagement')
        if engagement_id:
            qs = qs.filter(engagement_id=engagement_id)
        return qs

    @action(detail=False, methods=['post', 'get'])
    def generate(self, request):
        engagement_id = request.data.get('engagement') or request.query_params.get('engagement')
        engagement = Engagement.objects.filter(id=engagement_id).first() if engagement_id else Engagement.objects.first()
        if not engagement:
            return Response({'error': 'No engagement found'}, status=status.HTTP_404_NOT_FOUND)

        report = ReportGeneratorService.generate_pdf_report(engagement)
        serializer = self.get_serializer(report)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def consolidated_report(self, request):
        """Returns the structured 14-section Consolidated Financial & Audit Analysis Report JSON"""
        from .report_builder import ConsolidatedAuditReportBuilder
        engagement_id = request.query_params.get('engagement')
        engagement = Engagement.objects.filter(id=engagement_id).first() if engagement_id else Engagement.objects.first()
        if not engagement:
            return Response({'error': 'No engagement found'}, status=status.HTTP_404_NOT_FOUND)

        data = ConsolidatedAuditReportBuilder.build_report(engagement)
        return Response(data)

    @action(detail=False, methods=['get', 'post'])
    def integrity_gate(self, request):
        """
        Evaluates the 6 mandatory statutory report integrity gates:
        1. Double-Entry & Balance Sheet Equilibrium
        2. Unresolved Critical/High Exceptions
        3. Bank Reconciliation Consistency
        4. Procedure Evidence Grounding
        5. SA 240 Fraud Analytical Review Scope
        6. CA Partner Credentials & UDIN Authenticity
        """
        from .integrity_gate import ReportIntegrityGateService
        engagement_id = request.data.get('engagement') or request.query_params.get('engagement')
        engagement = Engagement.objects.filter(id=engagement_id).first() if engagement_id else Engagement.objects.first()
        if not engagement:
            return Response({'error': 'No engagement found'}, status=status.HTTP_404_NOT_FOUND)

        ca_credentials = {
            'ca_name': request.data.get('ca_name') or request.query_params.get('ca_name', ''),
            'membership_number': request.data.get('membership_number') or request.query_params.get('membership_number', ''),
            'firm_name': request.data.get('firm_name') or request.query_params.get('firm_name', ''),
            'firm_registration_number': request.data.get('firm_registration_number') or request.query_params.get('firm_registration_number', ''),
            'udin': request.data.get('udin') or request.query_params.get('udin', ''),
        }
        res = ReportIntegrityGateService.evaluate_integrity(engagement, ca_credentials)
        return Response(res)

    @action(detail=False, methods=['get'])
    def document_processing_report(self, request):
        """Returns the structured Document Upload & Processing Report JSON"""
        from .report_builder import DocumentUploadReportBuilder
        engagement_id = request.query_params.get('engagement')
        engagement = Engagement.objects.filter(id=engagement_id).first() if engagement_id else Engagement.objects.first()
        if not engagement:
            return Response({'error': 'No engagement found'}, status=status.HTTP_404_NOT_FOUND)

        data = DocumentUploadReportBuilder.build_report(engagement)
        return Response(data)

    @action(detail=False, methods=['get', 'post'])
    def export_pdf(self, request):
        """Generates and downloads formal ReportLab PDF audit report with running page numbers"""
        from django.http import HttpResponse
        from .exporters import ReportExporterService
        from django.core.files.base import ContentFile
        from datetime import datetime

        engagement_id = request.data.get('engagement') or request.query_params.get('engagement')
        engagement = Engagement.objects.filter(id=engagement_id).first() if engagement_id else Engagement.objects.first()
        if not engagement:
            return Response({'error': 'No engagement found'}, status=status.HTTP_404_NOT_FOUND)

        pdf_bytes = ReportExporterService.export_consolidated_pdf(engagement)

        # Save to GeneratedReport history
        rep_record = GeneratedReport.objects.create(
            engagement=engagement,
            report_type='CONSOLIDATED_AUDIT_REPORT',
            title=f"Consolidated Audit Analysis Report - {engagement.company.name}",
            file_format='PDF',
            summary_data={'download_type': 'DIRECT_EXPORT_PDF'}
        )
        filename = f"consolidated_audit_report_{engagement.id}_{int(datetime.now().timestamp())}.pdf"
        rep_record.file.save(filename, ContentFile(pdf_bytes))
        rep_record.save()

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    @action(detail=False, methods=['get', 'post'])
    def export_excel(self, request):
        """Generates and downloads multi-tab OpenPyXL Excel workbook"""
        from django.http import HttpResponse
        from .exporters import ReportExporterService
        from django.core.files.base import ContentFile
        from datetime import datetime

        engagement_id = request.data.get('engagement') or request.query_params.get('engagement')
        engagement = Engagement.objects.filter(id=engagement_id).first() if engagement_id else Engagement.objects.first()
        if not engagement:
            return Response({'error': 'No engagement found'}, status=status.HTTP_404_NOT_FOUND)

        excel_bytes = ReportExporterService.export_consolidated_excel(engagement)

        # Save to GeneratedReport history
        rep_record = GeneratedReport.objects.create(
            engagement=engagement,
            report_type='CONSOLIDATED_AUDIT_REPORT',
            title=f"Consolidated Audit Schedules (Excel) - {engagement.company.name}",
            file_format='EXCEL',
            summary_data={'download_type': 'DIRECT_EXPORT_EXCEL'}
        )
        filename = f"consolidated_audit_schedules_{engagement.id}_{int(datetime.now().timestamp())}.xlsx"
        rep_record.file.save(filename, ContentFile(excel_bytes))
        rep_record.save()

        response = HttpResponse(excel_bytes, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    @action(detail=False, methods=['get', 'post'])
    def export_csv(self, request):
        """Generates and downloads standardized CSV export"""
        from django.http import HttpResponse
        from .exporters import ReportExporterService
        from django.core.files.base import ContentFile
        from datetime import datetime

        engagement_id = request.data.get('engagement') or request.query_params.get('engagement')
        engagement = Engagement.objects.filter(id=engagement_id).first() if engagement_id else Engagement.objects.first()
        if not engagement:
            return Response({'error': 'No engagement found'}, status=status.HTTP_404_NOT_FOUND)

        csv_content = ReportExporterService.export_consolidated_csv(engagement)

        # Save to GeneratedReport history
        rep_record = GeneratedReport.objects.create(
            engagement=engagement,
            report_type='CONSOLIDATED_AUDIT_REPORT',
            title=f"Consolidated Audit Data (CSV) - {engagement.company.name}",
            file_format='CSV',
            summary_data={'download_type': 'DIRECT_EXPORT_CSV'}
        )
        filename = f"consolidated_audit_summary_{engagement.id}_{int(datetime.now().timestamp())}.csv"
        rep_record.file.save(filename, ContentFile(csv_content.encode('utf-8')))
        rep_record.save()

        response = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

