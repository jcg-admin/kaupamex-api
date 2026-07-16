"""
Tests — Catálogo de zonas de envío + tiempos de entrega (H-12).

CRUD admin sobre /api/v2/admin/shipping-zones/ (ShippingZoneViewSet) y lista
pública /api/v2/shipping-zones/ (ShippingZoneListPublicView). Cubre éxito,
permisos, validación min/max y soft-delete.
"""
import pytest
from decimal import Decimal

from apps.addons.orders.models import ShippingZone
from apps.addons.geo.models import CatalogPostalCode

pytestmark = pytest.mark.integration


def _cp(postal_code, state, consec):
    """Crea una fila SEPOMEX mínima para probar la relación zona↔CP."""
    return CatalogPostalCode.objects.create(
        country='MX', postal_code=postal_code, settlement_name='Centro',
        settlement_type='Colonia', municipality='Cuauhtémoc', state=state,
        settlement_consecutive_id=consec,
    )

LIST_URL   = '/api/v2/admin/shipping-zones/'
DETAIL_URL = lambda pk: f'/api/v2/admin/shipping-zones/{pk}/'
PUBLIC_URL = '/api/v2/shipping-zones/'


@pytest.fixture(autouse=True)
def _tabla_zonas_vacia(db):
    """Aísla del seed de zonas (migración de datos 0012_seed_shipping_zones).

    Las migraciones de datos siembran C.P. reales (01, 06, 44, 64, …); sin
    limpiar, crear un prefijo ya sembrado choca con la unique de
    ``zip_code_prefix`` (migración 0017) y ``64000`` deja de ser "sin zona".
    El delete lo revierte la transacción del fixture ``db`` de pytest-django,
    así que otros módulos siguen viendo el seed. Corre antes de ``zona`` por
    ser autouse.
    """
    ShippingZone.objects.all().delete()


@pytest.fixture
def zona(db):
    return ShippingZone.objects.create(
        name='Guadalajara', zip_code_prefix='44', is_active=True,
        estimated_days_min=2, estimated_days_max=4, cost=Decimal('89.00'),
    )


class TestShippingZonesAdmin:

    # --- permisos ---
    def test_anon_recibe_401(self, api_client, db):
        assert api_client.get(LIST_URL).status_code == 401

    def test_comprador_recibe_403(self, auth_client, db):
        assert auth_client.get(LIST_URL).status_code == 403

    # --- éxito ---
    def test_admin_crea_zona(self, admin_client, db):
        r = admin_client.post(LIST_URL, {
            'name': 'CDMX',
            'zip_code_prefix': '01',
            'estimated_days_min': 1,
            'estimated_days_max': 3,
            'cost': '120.00',
        }, format='json')
        assert r.status_code == 201
        assert r.json()['estimated_days_max'] == 3
        assert ShippingZone.objects.filter(zip_code_prefix='01').exists()

    def test_admin_lista_zonas(self, admin_client, zona, db):
        r = admin_client.get(LIST_URL)
        assert r.status_code == 200
        body = r.json()
        rows = body['results'] if isinstance(body, dict) and 'results' in body else body
        prefixes = [z['zip_code_prefix'] for z in rows]
        assert '44' in prefixes

    def test_admin_edita_zona(self, admin_client, zona, db):
        r = admin_client.patch(DETAIL_URL(zona.id), {'estimated_days_max': 6}, format='json')
        assert r.status_code == 200
        zona.refresh_from_db()
        assert zona.estimated_days_max == 6

    def test_soft_delete_desactiva(self, admin_client, zona, db):
        r = admin_client.delete(DETAIL_URL(zona.id))
        assert r.status_code == 204
        zona.refresh_from_db()
        assert zona.is_active is False

    # --- validación ---
    def test_max_menor_que_min_falla(self, admin_client, db):
        r = admin_client.post(LIST_URL, {
            'name': 'Mala', 'zip_code_prefix': '99',
            'estimated_days_min': 5, 'estimated_days_max': 2,
        }, format='json')
        assert r.status_code == 400
        assert 'estimated_days_max' in r.json()


class TestShippingZonesSepomex:
    """Relación catálogo de zonas ↔ SEPOMEX (apps.addons.geo.CatalogPostalCode)."""

    def test_coverage_vacio_sin_sepomex(self, admin_client, zona, db):
        # Sin datos SEPOMEX cargados, coverage es 0 asentamientos / sin estados,
        # pero el campo existe (relación expuesta).
        r = admin_client.get(DETAIL_URL(zona.id))
        assert r.status_code == 200
        cov = r.json()['coverage']
        assert cov == {'settlement_count': 0, 'states': []}

    def test_validacion_omitida_sin_sepomex(self, admin_client, db):
        # Graceful: catálogo vacío → no se bloquea un prefijo aunque no exista CP.
        r = admin_client.post(LIST_URL, {
            'name': 'Sin catálogo', 'zip_code_prefix': '01',
            'estimated_days_min': 1, 'estimated_days_max': 3,
        }, format='json')
        assert r.status_code == 201

    def test_prefijo_valido_con_sepomex(self, admin_client, db):
        _cp('06000', 'Ciudad de México', '0001')
        _cp('06010', 'Ciudad de México', '0001')
        r = admin_client.post(LIST_URL, {
            'name': 'Centro CDMX', 'zip_code_prefix': '06',
            'estimated_days_min': 1, 'estimated_days_max': 2,
        }, format='json')
        assert r.status_code == 201, r.content
        cov = r.json()['coverage']
        assert cov['settlement_count'] == 2
        assert cov['states'] == ['Ciudad de México']

    def test_prefijo_invalido_con_sepomex(self, admin_client, db):
        # Con SEPOMEX cargado, un prefijo sin CP real se rechaza.
        _cp('06000', 'Ciudad de México', '0001')
        r = admin_client.post(LIST_URL, {
            'name': 'Fantasma', 'zip_code_prefix': '99',
            'estimated_days_min': 1, 'estimated_days_max': 2,
        }, format='json')
        assert r.status_code == 400
        assert 'zip_code_prefix' in r.json()


class TestShippingZonesPublic:

    def test_publico_lista_solo_activas(self, api_client, zona, db):
        ShippingZone.objects.create(
            name='Inactiva', zip_code_prefix='77', is_active=False,
        )
        r = api_client.get(PUBLIC_URL)
        assert r.status_code == 200
        body = r.json()
        rows = body['results'] if isinstance(body, dict) and 'results' in body else body
        prefixes = [z['zip_code_prefix'] for z in rows]
        assert '44' in prefixes
        assert '77' not in prefixes
