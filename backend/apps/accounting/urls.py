from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ChartOfAccountsViewSet, LedgerAccountViewSet, TransactionViewSet, TrialBalanceViewSet

router = DefaultRouter()
router.register(r'coa', ChartOfAccountsViewSet, basename='chart-of-accounts')
router.register(r'ledgers', LedgerAccountViewSet, basename='ledger-account')
router.register(r'transactions', TransactionViewSet, basename='transaction')
router.register(r'trial-balances', TrialBalanceViewSet, basename='trial-balance')

urlpatterns = [
    path('', include(router.urls)),
]
