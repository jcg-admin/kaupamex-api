"""Contrato de los dos catálogos públicos de envío (GAP-C1 / H-12).

Ambos endpoints son **anónimos**: el comprador necesita ver costos y tiempos de
entrega antes de autenticarse, igual que en la referencia, donde
``website_sale`` expone los transportistas (``delivery.carrier``) en el
checkout sin exigir sesión.

Sólo se listan los registros **activos**: un método o zona dado de baja no debe
seguir ofreciéndose. La lista es de sólo lectura — el alta es admin (UC-CFG-02).

**Procedencia.** Las dos vistas se referenciaban en ``config/urls.py:95,98``
pero **no existían en ningún archivo** del árbol: murieron con la familia
``settings_app`` y sólo quedó la ruta, que rompía el URLconf con
``NameError``. Ver H-API-215.
"""
from decimal import Decimal

import pytest
from django.urls import reverse

from addons.delivery.models import ShippingMethod, ShippingZone

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


class TestShippingMethodListPublic:
    def test_anonimo_puede_listar(self, api_client):
        ShippingMethod.objects.create(
            name='Estándar', cost=Decimal('99.00'), estimated_days=5)
        resp = api_client.get(reverse('public-shipping-methods'))
        assert resp.status_code == 200
        assert [m['name'] for m in resp.data] == ['Estándar']

    def test_omite_los_inactivos(self, api_client):
        ShippingMethod.objects.create(
            name='Vigente', cost=Decimal('99.00'), estimated_days=5)
        ShippingMethod.objects.create(
            name='Retirado', cost=Decimal('50.00'), estimated_days=9,
            is_active=False)
        resp = api_client.get(reverse('public-shipping-methods'))
        assert [m['name'] for m in resp.data] == ['Vigente']

    def test_expone_costo_umbral_y_dias(self, api_client):
        ShippingMethod.objects.create(
            name='Express', cost=Decimal('199.00'), estimated_days=2,
            free_threshold=Decimal('1300.00'))
        item = api_client.get(reverse('public-shipping-methods')).data[0]
        assert item['cost'] == '199.00'
        assert item['estimated_days'] == 2
        assert item['free_threshold'] == '1300.00'


class TestShippingZoneListPublic:
    def test_anonimo_puede_listar(self, api_client):
        ShippingZone.objects.create(name='Guadalajara', zip_code_prefix='44')
        resp = api_client.get(reverse('public-shipping-zones'))
        assert resp.status_code == 200
        assert [z['zip_code_prefix'] for z in resp.data] == ['44']

    def test_omite_las_inactivas(self, api_client):
        ShippingZone.objects.create(name='Vigente', zip_code_prefix='44')
        ShippingZone.objects.create(
            name='Retirada', zip_code_prefix='99', is_active=False)
        resp = api_client.get(reverse('public-shipping-zones'))
        assert [z['name'] for z in resp.data] == ['Vigente']

    def test_expone_la_ventana_de_dias(self, api_client):
        ShippingZone.objects.create(
            name='CDMX', zip_code_prefix='01',
            estimated_days_min=1, estimated_days_max=3,
            free_threshold=Decimal('800.00'))
        item = api_client.get(reverse('public-shipping-zones')).data[0]
        assert item['estimated_days_min'] == 1
        assert item['estimated_days_max'] == 3
        assert item['free_threshold'] == '800.00'
