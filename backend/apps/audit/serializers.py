from rest_framework import serializers
from .models import (
    AuditProcedure, ProcedureExecution, ExceptionItem,
    FixedAsset, SubledgerAgingItem, RelatedParty, StatutoryClauseAudit
)

class AuditProcedureSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditProcedure
        fields = '__all__'

class ProcedureExecutionSerializer(serializers.ModelSerializer):
    procedure_code = serializers.CharField(source='procedure.code', read_only=True)
    procedure_title = serializers.CharField(source='procedure.title', read_only=True)
    category = serializers.CharField(source='procedure.category', read_only=True)

    class Meta:
        model = ProcedureExecution
        fields = '__all__'

class ExceptionItemSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='engagement.company.name', read_only=True)

    class Meta:
        model = ExceptionItem
        fields = '__all__'

class FixedAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = FixedAsset
        fields = '__all__'

class SubledgerAgingItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubledgerAgingItem
        fields = '__all__'

class RelatedPartySerializer(serializers.ModelSerializer):
    class Meta:
        model = RelatedParty
        fields = '__all__'

class StatutoryClauseAuditSerializer(serializers.ModelSerializer):
    class Meta:
        model = StatutoryClauseAudit
        fields = '__all__'
        extra_kwargs = {
            'engagement': {'required': False},
            'form_type': {'required': False},
            'clause_number': {'required': False},
            'clause_title': {'required': False},
        }

