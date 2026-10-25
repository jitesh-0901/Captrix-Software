from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CompanyViewSet, FinancialYearViewSet, EngagementViewSet, EngagementWorkflowConfigViewSet

router = DefaultRouter()
router.register(r'companies', CompanyViewSet, basename='company')
router.register(r'financial-years', FinancialYearViewSet, basename='financial-year')
router.register(r'engagements', EngagementViewSet, basename='engagement')
router.register(r'workflow-configs', EngagementWorkflowConfigViewSet, basename='workflow-config')


urlpatterns = [
    path('', include(router.urls)),
]
