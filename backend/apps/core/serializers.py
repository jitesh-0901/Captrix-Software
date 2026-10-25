from rest_framework import serializers
from django.contrib.auth.models import User
from .models import UserProfile, AuditLog

class UserSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source='profile.role', read_only=True)
    membership_number = serializers.CharField(source='profile.membership_number', read_only=True)
    firm_name = serializers.CharField(source='profile.firm_name', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'membership_number', 'firm_name']

class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = AuditLog
        fields = ['id', 'user_name', 'action', 'entity_type', 'entity_id', 'details', 'timestamp']
