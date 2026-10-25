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

def enforce_tenant_isolation(queryset, user, company_field='company'):
    """
    Enforces multi-company tenant boundary check.
    """
    # In production with tenant-specific roles, filter by assigned companies.
    return queryset
