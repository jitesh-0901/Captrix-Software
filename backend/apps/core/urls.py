from django.urls import path
from .views import CurrentUserView, AuditLogListView, HealthCheckView

urlpatterns = [
    path('me/', CurrentUserView.as_view(), name='current-user'),
    path('logs/', AuditLogListView.as_view(), name='audit-logs'),
    path('health/', HealthCheckView.as_view(), name='health-check'),
]
