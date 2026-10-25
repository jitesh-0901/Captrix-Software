from rest_framework import serializers
from .models import ChartOfAccounts, LedgerAccount, Transaction, TrialBalanceSnapshot

class ChartOfAccountsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChartOfAccounts
        fields = '__all__'

class LedgerAccountSerializer(serializers.ModelSerializer):
    coa_code = serializers.CharField(source='coa.account_code', read_only=True)
    schedule_group = serializers.CharField(source='coa.schedule_iii_group', read_only=True)

    class Meta:
        model = LedgerAccount
        fields = '__all__'

class TransactionSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='ledger_account.name', read_only=True)

    class Meta:
        model = Transaction
        fields = '__all__'

class TrialBalanceSnapshotSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='engagement.company.name', read_only=True)

    class Meta:
        model = TrialBalanceSnapshot
        fields = '__all__'
