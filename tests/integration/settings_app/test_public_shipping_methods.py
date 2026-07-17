"""
Tests — GET /api/v2/shipping-methods/ (GAP-C1)

Endpoint público (sin auth) que expone los métodos de envío activos
para que el checkout pueda presentarlos dinámicamente en lugar de
usar SHIPPING_OPTIONS hardcoded.

UC-CFG-02 / GAP-C1: checkout shipping gap.
"""
import pytest
from decimal import Decimal
from addons.settings_app.models import ShippingMethod

pytestmark = pytest.mark.integration

URL = '/api/v2/shipping-methods/'


@pytest.fixture
def metodos(db):
    std = ShippingMethod.objects.create(
        name='Estándar', cost=Decimal('0.00'), estimated_days=5, is_active=True,
        free_threshold=None,
    )
    exp = ShippingMethod.objects.create(
        name='Express', cost=Decimal('280.00'), estimated_days=1, is_active=True,
        free_threshold=None,
    )
    inactivo = ShippingMethod.objects.create(
        name='Inactivo', cost=Decimal('0.00'), estimated_days=3, is_active=False,
    )
    return {'std': std, 'exp': exp, 'inactivo': inactivo}


class TestPublicShippingMethods:

    def test_retorna_200_sin_autenticar(self, api_client, metodos):
        """Endpoint público — no requiere JWT."""
        r = api_client.get(URL)
        assert r.status_code == 200

    def test_retorna_solo_activos(self, api_client, metodos):
        r = api_client.get(URL)
        nombres = [m['name'] for m in r.json()]
        assert 'Estándar' in nombres
        assert 'Express' in nombres
        assert 'Inactivo' not in nombres

    def test_campos_obligatorios(self, api_client, metodos):
        r = api_client.get(URL)
        primero = r.json()[0]
        assert 'id' in primero
        assert 'name' in primero
        assert 'cost' in primero
        assert 'estimated_days' in primero

    def test_no_expone_zonas_ni_admin_fields(self, api_client, metodos):
        """El endpoint público no expone campos de administración."""
        r = api_client.get(URL)
        for m in r.json():
            assert 'is_active' not in m
            assert 'updated_at' not in m

    def test_orden_por_costo(self, api_client, metodos):
        r = api_client.get(URL)
        costos = [Decimal(str(m['cost'])) for m in r.json()]
        assert costos == sorted(costos)

    def test_free_threshold_en_respuesta(self, api_client, db):
        ShippingMethod.objects.create(
            name='Estándar con umbral', cost=Decimal('99.00'),
            estimated_days=5, is_active=True,
            free_threshold=Decimal('500.00'),
        )
        r = api_client.get(URL)
        meth = next(m for m in r.json() if m['name'] == 'Estándar con umbral')
        assert Decimal(str(meth['free_threshold'])) == Decimal('500.00')

    def test_lista_vacia_si_no_hay_activos(self, api_client, db):
        ShippingMethod.objects.filter(is_active=True).update(is_active=False)
        r = api_client.get(URL)
        assert r.status_code == 200
        assert r.json() == []

    def test_post_not_allowed(self, api_client):
        r = api_client.post(URL, {})
        assert r.status_code == 405
