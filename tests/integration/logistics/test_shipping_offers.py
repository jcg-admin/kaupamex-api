"""
Integration tests — POST /api/v2/shipping-offers (Shipment Offer API nativa).

Cubre: endpoint público (AllowAny), validación → HTTP 400, ranking de
paqueterías elegibles y reporte de inelegibles con motivo.

English JSON keys per DEC-DOC-005.
"""
from decimal import Decimal
from apps.logistics.models import CarrierRateCard, Courier

import pytest

pytestmark = pytest.mark.integration

OFFERS_URL = '/api/v2/shipping-offers/'


def _card(code, name, **kw):
    courier = Courier.objects.create(name=name, code=code, is_active=True)
    defaults = dict(
        base_cost=Decimal('50.00'), cost_per_kg=Decimal('10.00'),
        transit_days=3, environmental=CarrierRateCard.ENV_MEDIUM,
        allows_hazardous=False, is_active=True,
    )
    defaults.update(kw)
    return CarrierRateCard.objects.create(courier=courier, **defaults)


@pytest.fixture
def one_pkg():
    return {'packages': [{
        'length': '10', 'width': '10', 'height': '10',
        'weight': '2', 'value': '100',
    }]}


class TestShippingOffersPublic:
    def test_anonimo_puede_cotizar(self, api_client, one_pkg, db):
        _card('fast', 'Fast')
        r = api_client.post(OFFERS_URL, one_pkg, format='json')
        assert r.status_code == 200, r.content
        assert 'offers' in r.data and 'ineligible' in r.data

    def test_paquetes_vacios_400(self, api_client, db):
        r = api_client.post(OFFERS_URL, {'packages': []}, format='json')
        assert r.status_code == 400

    def test_sin_packages_400(self, api_client, db):
        r = api_client.post(OFFERS_URL, {}, format='json')
        assert r.status_code == 400

    def test_dimension_no_positiva_400(self, api_client, db):
        payload = {'packages': [{
            'length': '0', 'width': '10', 'height': '10',
            'weight': '1', 'value': '100',
        }]}
        r = api_client.post(OFFERS_URL, payload, format='json')
        assert r.status_code == 400

    def test_ranking_por_costo(self, api_client, one_pkg, db):
        _card('caro', 'Caro', base_cost=Decimal('500.00'), cost_per_kg=Decimal('0'))
        _card('barato', 'Barato', base_cost=Decimal('50.00'), cost_per_kg=Decimal('0'))
        r = api_client.post(OFFERS_URL, one_pkg, format='json')
        assert r.status_code == 200
        carriers = [o['carrier'] for o in r.data['offers']]
        assert carriers[0] == 'Barato'

    def test_inelegible_reporta_motivo(self, api_client, db):
        _card('liviano', 'Liviano', max_package_weight_kg=Decimal('1.00'))
        payload = {'packages': [{
            'length': '10', 'width': '10', 'height': '10',
            'weight': '5', 'value': '100',
        }]}
        r = api_client.post(OFFERS_URL, payload, format='json')
        assert r.status_code == 200
        assert r.data['offers'] == []
        assert r.data['ineligible'][0]['carrier'] == 'Liviano'
        assert r.data['ineligible'][0]['reasons']

    def test_solo_paqueterias_activas(self, api_client, one_pkg, db):
        _card('activa', 'Activa')
        _card('inactiva', 'Inactiva', is_active=False)
        r = api_client.post(OFFERS_URL, one_pkg, format='json')
        carriers = {o['carrier'] for o in r.data['offers']}
        assert 'Activa' in carriers
        assert 'Inactiva' not in carriers
