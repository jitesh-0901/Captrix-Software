from django.db import models
from django.contrib.auth.models import User

class UserRole(models.TextChoices):
    ADMIN = 'ADMIN', 'System Administrator'
    PARTNER = 'PARTNER', 'Engagement Partner'
    MANAGER = 'MANAGER', 'Audit Manager'
    SENIOR_AUDITOR = 'SENIOR_AUDITOR', 'Senior Auditor'
    PREPARER = 'PREPARER', 'Audit Preparer'
    REVIEWER = 'REVIEWER', 'Audit Reviewer'

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=30, choices=UserRole.choices, default=UserRole.MANAGER)
    membership_number = models.CharField(max_length=50, blank=True, help_text="ICAI Membership Number for Qualified CAs")
    firm_name = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"

class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=100, blank=True)
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {self.action} on {self.entity_type} {self.entity_id}"
