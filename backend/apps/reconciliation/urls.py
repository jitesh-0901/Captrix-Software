from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ReconciliationRunViewSet, ReconciliationItemViewSet

router = DefaultRouter()
router.register(r'runs', ReconciliationRunViewSet, basename='reconciliation-run')
router.register(r'items', ReconciliationItemViewSet, basename='reconciliation-item')

urlpatterns = [
    path('', include(router.urls)),
]
