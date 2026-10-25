from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import ReconciliationRun, ReconciliationItem
from .serializers import ReconciliationRunSerializer, ReconciliationItemSerializer
from .services import BankReconciliationEngine, GstItcReconciliationEngine
from apps.companies.models import Engagement
from decimal import Decimal

class ReconciliationRunViewSet(viewsets.ModelViewSet):
    queryset = ReconciliationRun.objects.all().select_related('engagement').prefetch_related('items')
    serializer_class = ReconciliationRunSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        engagement_id = self.request.query_params.get('engagement')
        recon_type = self.request.query_params.get('type')
        if engagement_id:
            qs = qs.filter(engagement_id=engagement_id)
        if recon_type:
            qs = qs.filter(recon_type=recon_type)
        return qs

    @action(detail=True, methods=['post'])
    def approve_match(self, request, pk=None):
        item_id = request.data.get('item_id')
        item = ReconciliationItem.objects.filter(reconciliation_run_id=pk, id=item_id).first()
        if not item:
            return Response({'error': 'Item not found'}, status=status.HTTP_404_NOT_FOUND)
        item.is_approved = True
        item.match_notes = request.data.get('notes', item.match_notes)
        item.save()

        # Update run unresolved count
        run = item.reconciliation_run
        unapproved = run.items.filter(is_matched=False, match_type='SUGGESTED', is_approved=False).count()
        run.unresolved_count = unapproved
        if run.unreconciled_difference < Decimal('0.01') and unapproved == 0:
            run.status = 'BALANCED'
        run.save(update_fields=['unresolved_count', 'status'])

        return Response({'message': 'Match approved successfully', 'item_id': item.id, 'run_status': run.status})

    @action(detail=False, methods=['post'])
    def run_cross_document(self, request):
        """Triggers complete suite of cross-document reconciliations"""
        engagement_id = request.data.get('engagement')
        engagement = Engagement.objects.filter(id=engagement_id).first() if engagement_id else Engagement.objects.first()
        if not engagement:
            return Response({'error': 'No engagement found'}, status=status.HTTP_404_NOT_FOUND)

        from .services import CrossDocumentReconciliationEngine
        runs = CrossDocumentReconciliationEngine.run_all_cross_reconciliations(engagement)
        serializer = self.get_serializer(runs, many=True)
        return Response({
            'message': f"Executed {len(runs)} cross-document reconciliations",
            'runs': serializer.data
        }, status=status.HTTP_201_CREATED)

class ReconciliationItemViewSet(viewsets.ModelViewSet):
    queryset = ReconciliationItem.objects.all()
    serializer_class = ReconciliationItemSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        run_id = self.request.query_params.get('run_id')
        is_matched = self.request.query_params.get('is_matched')
        if run_id:
            qs = qs.filter(reconciliation_run_id=run_id)
        if is_matched is not None:
            qs = qs.filter(is_matched=is_matched.lower() in ['true', '1'])
        return qs
