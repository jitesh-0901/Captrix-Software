from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import WorkpaperViewSet, ProposedAdjustmentViewSet, GeneratedReportViewSet

router = DefaultRouter()
router.register(r'workpapers', WorkpaperViewSet, basename='workpaper')
router.register(r'adjustments', ProposedAdjustmentViewSet, basename='proposed-adjustment')
router.register(r'reports', GeneratedReportViewSet, basename='generated-report')

urlpatterns = [
    path('', include(router.urls)),
]
