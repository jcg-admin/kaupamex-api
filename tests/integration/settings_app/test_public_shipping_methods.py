"""
Integration tests — GET /api/v2/shipping-methods/ (GAP-C1)

Public endpoint: no auth required, returns only active methods.
"""
import pytest
from decimal import Decimal
from rest_framework.test import APIClient
from apps.settings_app.models import ShippingMethod


def make_method(**kwargs):
    defaults = dict(
        name='Estándar',
        cost=Decimal('100.00'),
        estimated_days=3,
        is_active=True,
        free_threshold=None,
    )
    defaults.update(kwargs)
    return ShippingMethod.objects.create(**defaults)


@pytest.mark.django_db
class TestPublicShippingMethodList:
    URL = '/api/v2/shipping-methods/'

    def setup_method(self):
        self.client = APIClient()

    def test_returns_200_without_auth(self):
        response = self.client.get(self.URL)
        assert response.status_code == 200

    def test_returns_only_active_methods(self):
        active   = make_method(name='Activo',   is_active=True)
        inactive = make_method(name='Inactivo', is_active=False)
        response = self.client.get(self.URL)
        ids = [item['id'] for item in response.data]
        assert active.pk in ids
        assert inactive.pk not in ids

    def test_response_shape(self):
        make_method()
        response = self.client.get(self.URL)
        assert response.status_code == 200
        item = response.data[0]
        assert set(item.keys()) == {'id', 'name', 'cost', 'estimated_days', 'free_threshold'}

    def test_admin_fields_not_exposed(self):
        make_method()
        response = self.client.get(self.URL)
        item = response.data[0]
        for field in ('is_active', 'zones', 'updated_at'):
            assert field not in item, f"Admin-only field '{field}' exposed in public endpoint"

    def test_empty_list_when_no_active_methods(self):
        make_method(is_active=False)
        response = self.client.get(self.URL)
        assert response.status_code == 200
        assert list(response.data) == []

    def test_ordered_by_cost_then_name(self):
        make_method(cost=Decimal('20.00'), name='Zeta')
        make_method(cost=Decimal('10.00'), name='Beta')
        make_method(cost=Decimal('10.00'), name='Alfa')
        response = self.client.get(self.URL)
        costs = [Decimal(str(item['cost'])) for item in response.data]
        assert costs == sorted(costs), "Results not ordered by cost ascending"
        ten_peso = [item for item in response.data if Decimal(str(item['cost'])) == Decimal('10.00')]
        assert ten_peso[0]['name'] == 'Alfa'
        assert ten_peso[1]['name'] == 'Beta'

    def test_post_not_allowed(self):
        response = self.client.post(self.URL, {})
        assert response.status_code == 405
