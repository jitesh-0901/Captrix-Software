from rest_framework import serializers
from .models import ReconciliationRun, ReconciliationItem

class ReconciliationItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReconciliationItem
        fields = '__all__'

class ReconciliationRunSerializer(serializers.ModelSerializer):
    items = ReconciliationItemSerializer(many=True, read_only=True)
    company_name = serializers.CharField(source='engagement.company.name', read_only=True)

    class Meta:
        model = ReconciliationRun
        fields = '__all__'
