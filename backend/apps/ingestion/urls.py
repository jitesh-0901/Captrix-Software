from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DocumentViewSet, ProcessingRunViewSet

router = DefaultRouter()
router.register(r'documents', DocumentViewSet, basename='document')
router.register(r'runs', ProcessingRunViewSet, basename='processing-run')

urlpatterns = [
    path('', include(router.urls)),
]
