from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from apps.core.views import HealthCheckView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', HealthCheckView.as_view(), name='root-health-check'),
    path('api/core/', include('apps.core.urls')),
    path('api/companies/', include('apps.companies.urls')),
    path('api/ingestion/', include('apps.ingestion.urls')),
    path('api/accounting/', include('apps.accounting.urls')),
    path('api/reconciliation/', include('apps.reconciliation.urls')),
    path('api/audit/', include('apps.audit.urls')),
    path('api/reporting/', include('apps.reporting.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
