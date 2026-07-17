"""Integration — consulta pública SEPOMEX de CP (T-214, party).

``GET /api/v2/geo/postal-codes/<cp>/`` alimenta el autocompletado de
direcciones (CP → municipio/estado + lista de colonias). Público (AllowAny):
la captura de dirección puede ocurrir en checkout anónimo.
"""
from addons.geo.models import CatalogPostalCode

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.integration


def _row(**over):
    data = dict(
        postal_code='01000', settlement_name='San Ángel', settlement_type='Colonia',
        municipality='Álvaro Obregón', state='Ciudad de México', city='Ciudad de México',
        office_postal_code='01001', state_code='09', office_code='01001',
        postal_code_internal_code='', settlement_type_code='09', municipality_code='010',
        settlement_consecutive_id='0001', zone='Urbano', city_code='01',
    )
    data.update(over)
    return CatalogPostalCode.objects.create(**data)


@pytest.fixture
def client():
    return APIClient()


@pytest.mark.django_db
def test_lookup_returns_settlements_grouped_by_cp(client):
    _row(settlement_consecutive_id='0001', settlement_name='San Ángel')
    _row(settlement_consecutive_id='0005', settlement_name='Los Alpes')
    resp = client.get('/api/v2/geo/postal-codes/01000/')
    assert resp.status_code == 200
    body = resp.json()
    assert body['postal_code'] == '01000'
    assert body['state'] == 'Ciudad de México'
    assert body['municipality'] == 'Álvaro Obregón'
    names = [s['settlement_name'] for s in body['settlements']]
    # Orden alfabético por settlement_name.
    assert names == ['Los Alpes', 'San Ángel']


@pytest.mark.django_db
def test_lookup_unknown_cp_returns_404(client):
    resp = client.get('/api/v2/geo/postal-codes/99999/')
    assert resp.status_code == 404
    assert resp.json()['codigo_error'] == 'CP_NO_ENCONTRADO'


@pytest.mark.django_db
def test_lookup_is_public(client):
    """Sin autenticación (checkout anónimo) el endpoint responde 200."""
    _row(postal_code='28001', settlement_name='Centro',
         municipality='Colima', state='Colima', settlement_consecutive_id='0001')
    resp = client.get('/api/v2/geo/postal-codes/28001/')
    assert resp.status_code == 200


@pytest.mark.django_db
def test_lookup_filters_by_country(client):
    """El mismo CP en dos países se separa por el query param ``country``."""
    _row(country='MX', postal_code='28001', settlement_name='Centro',
         municipality='Colima', state='Colima', settlement_consecutive_id='0001')
    _row(country='ES', postal_code='28001', settlement_name='Salamanca',
         municipality='Madrid', state='Madrid', zone='',
         settlement_consecutive_id='0001')
    resp = client.get('/api/v2/geo/postal-codes/28001/?country=ES')
    assert resp.status_code == 200
    body = resp.json()
    assert body['municipality'] == 'Madrid'
    assert [s['settlement_name'] for s in body['settlements']] == ['Salamanca']
