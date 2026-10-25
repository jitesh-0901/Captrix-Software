from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AuditProcedureViewSet, ProcedureExecutionViewSet, ExceptionItemViewSet,
    FixedAssetViewSet, SubledgerAgingViewSet, RelatedPartyViewSet, StatutoryClauseAuditViewSet
)

from .corrections.views import AuditCorrectionsScheduleView, AuditCorrectionRulesView

router = DefaultRouter()
router.register(r'procedures', AuditProcedureViewSet, basename='audit-procedure')
router.register(r'executions', ProcedureExecutionViewSet, basename='procedure-execution')
router.register(r'exceptions', ExceptionItemViewSet, basename='exception-item')
router.register(r'fixed-assets', FixedAssetViewSet, basename='fixed-asset')
router.register(r'subledger-aging', SubledgerAgingViewSet, basename='subledger-aging')
router.register(r'related-parties', RelatedPartyViewSet, basename='related-party')
router.register(r'statutory-clauses', StatutoryClauseAuditViewSet, basename='statutory-clause')

urlpatterns = [
    path('corrections/schedule/', AuditCorrectionsScheduleView.as_view(), name='audit-corrections-schedule'),
    path('corrections/rules/', AuditCorrectionRulesView.as_view(), name='audit-corrections-rules'),
    path('', include(router.urls)),
]

