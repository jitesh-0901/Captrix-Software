import os
import re
from rest_framework.exceptions import PermissionDenied, ValidationError

ALLOWED_EXTENSIONS = {'.xlsx', '.xls', '.csv', '.pdf', '.png', '.jpg', '.jpeg', '.zip'}
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024 # 100 MB

def sanitize_filename(filename: str) -> str:
    """
    Strips directory traversal sequences (../, ..\\) and dangerous shell/path characters.
    """
    clean_name = os.path.basename(filename)
    clean_name = re.sub(r'[^\w\.\-\s]', '_', clean_name)
    return clean_name.strip()

def validate_uploaded_file(file_obj) -> None:
    """
    Validates file extension, size, and prevents 0-byte or path traversal payloads.
    """
    if not file_obj or file_obj.size == 0:
        raise ValidationError("Uploaded file is empty (0 bytes).")
    
    if file_obj.size > MAX_FILE_SIZE_BYTES:
        raise ValidationError(f"File exceeds maximum permissible size of {MAX_FILE_SIZE_BYTES / (1024*1024)} MB.")

    _, ext = os.path.splitext(file_obj.name)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        raise ValidationError(f"Unsupported file extension '{ext}'. Permitted extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

from django.db.models import Q

def enforce_tenant_isolation(queryset, user, company_field='company'):
    """
    Enforces multi-company tenant boundary check.
    Ensures users can only access their authorized company and engagement data.
    Superusers and system administrators can view all records.
    """
    if user is None:
        return queryset

    if not user.is_authenticated:
        return queryset.none()

    if user.is_superuser or user.is_staff:
        return queryset

    profile = getattr(user, 'profile', None)
    role = getattr(profile, 'role', None) if profile else None
    if role == 'ADMIN':
        return queryset

    model = queryset.model
    model_name = model.__name__

    if model_name == 'Company':
        return queryset.filter(
            Q(engagements__lead_partner=user) | Q(engagements__audit_manager=user)
        ).distinct()

    if model_name == 'Engagement':
        return queryset.filter(
            Q(lead_partner=user) | Q(audit_manager=user)
        ).distinct()

    if hasattr(model, 'engagement'):
        return queryset.filter(
            Q(engagement__lead_partner=user) | Q(engagement__audit_manager=user)
        ).distinct()

    if hasattr(model, company_field):
        return queryset.filter(
            Q(**{f"{company_field}__engagements__lead_partner": user}) |
            Q(**{f"{company_field}__engagements__audit_manager": user})
        ).distinct()

    return queryset

def check_engagement_access(user, engagement) -> bool:
    """
    Verifies if user has permission to access an engagement.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    profile = getattr(user, 'profile', None)
    role = getattr(profile, 'role', None) if profile else None
    if role == 'ADMIN':
        return True
    return bool(engagement.lead_partner_id == user.id or engagement.audit_manager_id == user.id)
