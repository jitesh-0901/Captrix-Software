from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import ChartOfAccounts, LedgerAccount, Transaction, TrialBalanceSnapshot
from .serializers import ChartOfAccountsSerializer, LedgerAccountSerializer, TransactionSerializer, TrialBalanceSnapshotSerializer
from .services import TrialBalanceService, GeneralLedgerScrutinyService
from apps.companies.models import Engagement
from decimal import Decimal

class ChartOfAccountsViewSet(viewsets.ModelViewSet):
    queryset = ChartOfAccounts.objects.all()
    serializer_class = ChartOfAccountsSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        company_id = self.request.query_params.get('company')
        if company_id:
            qs = qs.filter(company_id=company_id)
        return qs

class LedgerAccountViewSet(viewsets.ModelViewSet):
    queryset = LedgerAccount.objects.all().select_related('coa', 'company')
    serializer_class = LedgerAccountSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        company_id = self.request.query_params.get('company')
        mapping_status = self.request.query_params.get('mapping_status')
        if company_id:
            qs = qs.filter(company_id=company_id)
        if mapping_status:
            qs = qs.filter(mapping_status=mapping_status)
        return qs

    @action(detail=False, methods=['get'])
    def unmapped(self, request):
        """Returns accounts that require auditor classification review (fail-closed)"""
        company_id = request.query_params.get('company')
        qs = self.get_queryset()
        if company_id:
            qs = qs.filter(company_id=company_id)
        from django.db.models import Q
        unmapped_accounts = qs.filter(
            Q(mapping_status__in=['UNMAPPED', 'REVIEW_REQUIRED']) |
            Q(schedule_iii_division='NOT_APPLICABLE') |
            Q(coa__isnull=True)
        )
        serializer = self.get_serializer(unmapped_accounts, many=True)
        return Response({
            'count': unmapped_accounts.count(),
            'fail_closed_alert': unmapped_accounts.exists(),
            'unmapped_accounts': serializer.data
        })

    @action(detail=True, methods=['post'])
    def approve_mapping(self, request, pk=None):
        """Auditor review and explicit approval of Schedule III presentation grouping"""
        account = self.get_object()
        sch_group = request.data.get('schedule_iii_group')
        sch_div = request.data.get('schedule_iii_division', 'DIVISION_I')
        notes = request.data.get('mapping_notes', 'Auditor verified and approved Schedule III mapping')

        if sch_group and account.coa:
            account.coa.schedule_iii_group = sch_group
            account.coa.save(update_fields=['schedule_iii_group'])

        account.schedule_iii_division = sch_div
        account.mapping_status = 'APPROVED'
        account.mapping_notes = notes
        account.save(update_fields=['schedule_iii_division', 'mapping_status', 'mapping_notes'])

        serializer = self.get_serializer(account)
        return Response({
            'message': f"Account '{account.name}' mapping approved successfully",
            'account': serializer.data
        })

    @action(detail=False, methods=['post'])
    def batch_map(self, request):
        """Batch review and mapping of accounts to Schedule III groups"""
        mappings = request.data.get('mappings', [])
        updated_count = 0
        for m in mappings:
            acc_id = m.get('account_id')
            sch_grp = m.get('schedule_iii_group')
            sch_div = m.get('schedule_iii_division', 'DIVISION_I')
            notes = m.get('mapping_notes', 'Batch approved')
            acc = LedgerAccount.objects.filter(id=acc_id).first()
            if acc:
                if sch_grp and acc.coa:
                    acc.coa.schedule_iii_group = sch_grp
                    acc.coa.save(update_fields=['schedule_iii_group'])
                acc.schedule_iii_division = sch_div
                acc.mapping_status = 'APPROVED'
                acc.mapping_notes = notes
                acc.save(update_fields=['schedule_iii_division', 'mapping_status', 'mapping_notes'])
                updated_count += 1

        return Response({'message': f"Successfully updated {updated_count} account mappings"})

    @action(detail=False, methods=['get'])
    def adjusted_balances(self, request):
        """Side-by-side presentation of original balances vs adjusted balances with AJE layer"""
        engagement_id = request.query_params.get('engagement')
        engagement = Engagement.objects.filter(id=engagement_id).first() if engagement_id else Engagement.objects.first()
        if not engagement:
            return Response({'error': 'No engagement found'}, status=status.HTTP_404_NOT_FOUND)

        from apps.reporting.models import ProposedAdjustment
        # Fetch all proposed and accepted adjustments
        ajs = ProposedAdjustment.objects.filter(engagement=engagement)
        
        # Accumulate net adjustments by account name
        adj_map = {} # name -> {'debit': Decimal, 'credit': Decimal}
        for adj in ajs:
            entries = adj.journal_entries or []
            for entry in entries:
                acc_name = entry.get('account', '').strip()
                dr = Decimal(str(entry.get('debit', 0)))
                cr = Decimal(str(entry.get('credit', 0)))
                if acc_name not in adj_map:
                    adj_map[acc_name] = {'debit': Decimal('0.00'), 'credit': Decimal('0.00')}
                adj_map[acc_name]['debit'] += dr
                adj_map[acc_name]['credit'] += cr

        accounts = LedgerAccount.objects.filter(company=engagement.company).select_related('coa')
        results = []
        for acc in accounts:
            orig = acc.closing_balance
            acc_adjs = adj_map.get(acc.name, {'debit': Decimal('0.00'), 'credit': Decimal('0.00')})
            # Net adjustment: if debit balance type, dr increases, cr decreases
            is_dr = (acc.closing_balance_type == 'DEBIT')
            net_adj = (acc_adjs['debit'] - acc_adjs['credit']) if is_dr else (acc_adjs['credit'] - acc_adjs['debit'])
            adjusted = orig + net_adj

            acc.adjusted_balance = adjusted
            acc.adjusted_balance_type = acc.closing_balance_type
            acc.save(update_fields=['adjusted_balance', 'adjusted_balance_type'])

            results.append({
                'id': acc.id,
                'name': acc.name,
                'code': acc.code,
                'account_type': acc.coa.account_type if acc.coa else 'ASSET',
                'schedule_iii_group': acc.coa.schedule_iii_group if acc.coa else 'UNMAPPED',
                'schedule_iii_division': acc.schedule_iii_division,
                'mapping_status': acc.mapping_status,
                'original_balance': str(orig),
                'balance_type': acc.closing_balance_type,
                'adjustments_debit': str(acc_adjs['debit']),
                'adjustments_credit': str(acc_adjs['credit']),
                'net_adjustment': str(net_adj),
                'adjusted_balance': str(adjusted),
                'has_adjustments': (acc_adjs['debit'] > 0 or acc_adjs['credit'] > 0)
            })

        return Response({
            'engagement_id': engagement.id,
            'total_accounts': len(results),
            'total_adjustments_count': ajs.count(),
            'balances': results
        })


class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.all().select_related('ledger_account', 'engagement')
    serializer_class = TransactionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        engagement_id = self.request.query_params.get('engagement')
        is_unusual = self.request.query_params.get('is_unusual')
        voucher_type = self.request.query_params.get('voucher_type')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')

        account_id = self.request.query_params.get('account')
        search = self.request.query_params.get('search')

        if engagement_id:
            qs = qs.filter(engagement_id=engagement_id)
        if account_id:
            qs = qs.filter(ledger_account_id=account_id)
        if is_unusual is not None:
            qs = qs.filter(is_unusual=is_unusual.lower() in ['true', '1'])
        if voucher_type:
            qs = qs.filter(voucher_type=voucher_type)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(voucher_number__icontains=search) |
                Q(narration__icontains=search) |
                Q(counterparty__icontains=search) |
                Q(ledger_account__name__icontains=search)
            )

        return qs

    @action(detail=False, methods=['get'])
    def scrutiny(self, request):
        engagement_id = request.query_params.get('engagement')
        qs = self.get_queryset()
        if engagement_id:
            qs = qs.filter(engagement_id=engagement_id)
        txns = list(qs)
        results = GeneralLedgerScrutinyService.scrutinize_transactions(txns)
        return Response(results)

    @action(detail=True, methods=['get'])
    def evidence(self, request, pk=None):
        """Returns cryptographic source-of-truth evidence and raw extracted record"""
        txn = self.get_object()
        doc = txn.document
        extracted_rec = None
        if doc and txn.source_reference:
            from apps.ingestion.models import ExtractedRecord
            extracted_rec = ExtractedRecord.objects.filter(
                document=doc,
                source_location=txn.source_reference
            ).first()

        return Response({
            'transaction_id': txn.id,
            'voucher_number': txn.voucher_number,
            'voucher_type': txn.voucher_type,
            'date': txn.date.isoformat(),
            'account_name': txn.ledger_account.name,
            'debit_amount': str(txn.debit_amount),
            'credit_amount': str(txn.credit_amount),
            'source_reference': txn.source_reference,
            'risk_flags': txn.risk_flags,
            'document': {
                'id': doc.id if doc else None,
                'filename': doc.original_filename if doc else 'Direct Manual Ledger',
                'file_hash': doc.file_hash if doc else None,
                'uploaded_at': doc.uploaded_at.isoformat() if doc else None,
                'mime_type': doc.mime_type if doc else None
            } if doc else None,
            'extracted_record': {
                'id': extracted_rec.id,
                'row_index': extracted_rec.row_index,
                'source_location': extracted_rec.source_location,
                'raw_data': extracted_rec.raw_data,
                'normalized_data': extracted_rec.normalized_data,
                'confidence_score': str(extracted_rec.confidence_score),
                'validation_status': extracted_rec.validation_status
            } if extracted_rec else None
        })

class TrialBalanceViewSet(viewsets.ModelViewSet):
    queryset = TrialBalanceSnapshot.objects.all().select_related('engagement')
    serializer_class = TrialBalanceSnapshotSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        engagement_id = self.request.query_params.get('engagement')
        if engagement_id:
            qs = qs.filter(engagement_id=engagement_id)
        return qs

    @action(detail=False, methods=['post'])
    def verify(self, request):
        """Verifies an uploaded set of trial balance accounts"""
        rows = request.data.get('rows', [])
        engagement_id = request.data.get('engagement')
        engagement = Engagement.objects.filter(id=engagement_id).first() if engagement_id else None

        result = TrialBalanceService.calculate_trial_balance(rows, engagement=engagement)
        return Response(result)

    @action(detail=False, methods=['get'])
    def movements(self, request):
        """Returns account movement and roll-forward analysis"""
        engagement_id = request.query_params.get('engagement')
        engagement = Engagement.objects.filter(id=engagement_id).first() if engagement_id else Engagement.objects.first()
        if not engagement:
            return Response([], status=status.HTTP_200_OK)

        analysis = TrialBalanceService.get_movement_analysis(engagement)
        return Response(analysis)

    @action(detail=False, methods=['get'])
    def latest(self, request):
        engagement_id = request.query_params.get('engagement')
        qs = self.get_queryset()
        if engagement_id:
            qs = qs.filter(engagement_id=engagement_id)
        tb = qs.first()
        if not tb:
            return Response(None, status=status.HTTP_200_OK)
        serializer = self.get_serializer(tb)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def financial_statements(self, request):
        """Returns the formal Schedule III Balance Sheet, Statement of Profit and Loss, and Financial Ratios"""
        engagement_id = request.query_params.get('engagement')
        qs = self.get_queryset()
        if engagement_id:
            qs = qs.filter(engagement_id=engagement_id)
        tb = qs.first()
        if not tb or not tb.accounts_snapshot:
            return Response(None, status=status.HTTP_200_OK)

        statements = TrialBalanceService.compile_financial_statements(tb.accounts_snapshot)
        return Response(statements)

