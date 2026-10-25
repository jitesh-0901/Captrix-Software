from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from django.contrib.auth.models import User
from django.conf import settings
from .models import UserProfile, AuditLog
from .serializers import UserSerializer, AuditLogSerializer

class CurrentUserView(APIView):
    def get(self, request):
        # Fallback or dev default user if not authenticated
        user = request.user if request.user.is_authenticated else User.objects.first()
        if not user:
            user = User.objects.create_user(
                username='auditor@captrix.ai',
                email='auditor@captrix.ai',
                first_name='Rohan',
                last_name='Sharma'
            )
            UserProfile.objects.create(
                user=user,
                role='PARTNER',
                membership_number='ICAI-FCA-402918',
                firm_name='Sharma & Associates, Chartered Accountants'
            )
        serializer = UserSerializer(user)
        return Response(serializer.data)

class AuditLogListView(generics.ListAPIView):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer


class HealthCheckView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({
            'status': 'healthy',
            'service': 'Captrix AI',
            'version': '2.0.0',
            'environment': 'production' if not settings.DEBUG else 'development'
        }, status=status.HTTP_200_OK)
