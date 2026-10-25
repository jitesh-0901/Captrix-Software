from rest_framework import serializers
from .models import Workpaper, ProposedAdjustment, GeneratedReport

class WorkpaperSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='engagement.company.name', read_only=True)
    preparer_name = serializers.CharField(source='preparer.username', read_only=True)
    reviewer_name = serializers.CharField(source='reviewer.username', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.username', read_only=True)

    class Meta:
        model = Workpaper
        fields = '__all__'

class ProposedAdjustmentSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='engagement.company.name', read_only=True)

    class Meta:
        model = ProposedAdjustment
        fields = '__all__'

class GeneratedReportSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    company_name = serializers.CharField(source='engagement.company.name', read_only=True)

    class Meta:
        model = GeneratedReport
        fields = '__all__'

    def get_file_url(self, obj):
        if obj.file:
            return obj.file.url
        return None
