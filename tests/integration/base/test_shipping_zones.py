"""
Tests — Catalogo publico de zonas de envio (H-12).

Cobertura reducida (2026-08): el CRUD admin
(``/api/v2/admin/shipping-zones/``, ``ShippingZoneViewSet``) y la relacion
zona<->SEPOMEX expuesta en el detalle admin no tienen endpoint montado
(``config/urls.py`` no registra ``admin/shipping-zones``; medido con el
resolver de Django, 0 rutas). Lo unico vivo es la lista publica
(``ShippingZoneListPublicView``, montada en ``config/urls.py`` como
``/api/v2/shipping-zones/``) — eso es lo que este archivo cubre ahora.
"""
import pytest
from decimal import Decimal

from addons.delivery.models import ShippingZone

pytestmark = pytest.mark.integration

PUBLIC_URL = '/api/v2/shipping-zones/'


@pytest.fixture(autouse=True)
def _tabla_zonas_vacia(db):
    """Aisla del seed de zonas (migracion de datos 0012_seed_shipping_zones).

    Las migraciones de datos siembran C.P. reales (01, 06, 44, 64, ...); sin
    limpiar, crear un prefijo ya sembrado choca con la unique de
    ``zip_code_prefix`` (migracion 0017). El delete lo revierte la
    transaccion del fixture ``db`` de pytest-django.
    """
    ShippingZone.objects.all().delete()


@pytest.fixture
def zona(db):
    return ShippingZone.objects.create(
        name='Guadalajara', zip_code_prefix='44', is_active=True,
        estimated_days_min=2, estimated_days_max=4, cost=Decimal('89.00'),
    )


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
