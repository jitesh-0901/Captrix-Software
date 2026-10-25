from rest_framework import serializers
from .models import Company, FinancialYear, Engagement, EngagementWorkflowConfig

class EngagementWorkflowConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = EngagementWorkflowConfig
        fields = '__all__'

class FinancialYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialYear
        fields = '__all__'

class EngagementSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    fy_label = serializers.CharField(source='financial_year.label', read_only=True)
    workflow_config = EngagementWorkflowConfigSerializer(read_only=True)

    class Meta:
        model = Engagement
        fields = '__all__'


class CompanySerializer(serializers.ModelSerializer):
    financial_years = FinancialYearSerializer(many=True, read_only=True)
    engagements = EngagementSerializer(many=True, read_only=True)

    class Meta:
        model = Company
        fields = '__all__'
