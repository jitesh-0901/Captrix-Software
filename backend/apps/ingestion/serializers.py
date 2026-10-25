from rest_framework import serializers
from .models import Document, ProcessingJob, ExtractedRecord, ProcessingRun
from apps.reporting.serializers import GeneratedReportSerializer

class ProcessingJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessingJob
        fields = '__all__'

class ExtractedRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtractedRecord
        fields = '__all__'

class DocumentSerializer(serializers.ModelSerializer):
    jobs = ProcessingJobSerializer(many=True, read_only=True)
    engagement_title = serializers.CharField(source='engagement.title', read_only=True)

    class Meta:
        model = Document
        fields = '__all__'
        read_only_fields = ['file_hash', 'file_size_bytes', 'mime_type', 'status', 'extracted_summary', 'error_message']

class ProcessingRunSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    engagement_title = serializers.CharField(source='engagement.title', read_only=True)
    documents = DocumentSerializer(many=True, read_only=True)
    generated_reports = GeneratedReportSerializer(many=True, read_only=True)
    zip_package_url = serializers.SerializerMethodField()

    class Meta:
        model = ProcessingRun
        fields = '__all__'

    def get_zip_package_url(self, obj):
        if obj.zip_package:
            return obj.zip_package.url
        return None

