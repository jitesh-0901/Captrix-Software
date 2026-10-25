import pytest
from rest_framework.test import APIClient
from rest_framework import status


@pytest.mark.django_db
class TestHealthCheckEndpoint:
    def test_health_check_unauthenticated(self):
        client = APIClient()
        res = client.get('/api/core/health/')
        assert res.status_code == status.HTTP_200_OK
        data = res.data
        assert data['status'] == 'healthy'
        assert data['service'] == 'Captrix AI'
        assert data['version'] == '2.0.0'

    def test_root_api_health_check(self):
        client = APIClient()
        res = client.get('/api/health/')
        assert res.status_code == status.HTTP_200_OK
        assert res.data['status'] == 'healthy'
