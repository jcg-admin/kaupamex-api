"""
Tests — señal order_created en checkout (T-508, DEC-BC-19).

Verifica:
  - test_order_created_signal_fired_on_checkout: la señal order_created
    se emite exactamente una vez al completar el checkout exitoso.
"""
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from apps.catalogue.models import Category, Product
from apps.inventory.services import InventoryService
from apps.orders.models import ShippingZone
from apps.settings_app.models import ShippingMethod
from apps.orders.signals import order_created

pytestmark = pytest.mark.integration

CHECKOUT_URL = '/api/v2/orders/'
ITEMS_URL    = '/api/v2/cart/items/'

ADDR = {
    'recipient_name': 'Signal Test',
    'street': 'Calle Señal 1',
    'city': 'CDMX',
    'state': 'CMX',
    'zip_code': '06600',
    'country': 'MX',
}


@pytest.fixture
def zone_cdmx(db):
    zone, _ = ShippingZone.objects.get_or_create(
        zip_code_prefix='06', defaults={'name': 'Ciudad de México', 'is_active': True}
    )
    return zone


@pytest.fixture
def cat_sig(db):
    return Category.objects.create(name='Cat Signal', slug='cat-signal', is_active=True)


@pytest.fixture
def prod_sig(db, cat_sig):
    _p = Product.objects.create(
        name='Prod Signal', slug='prod-signal', sku='SIG-001',
        description='',
        price=Decimal('150.00'), stock=10,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat_sig)
    return _p


class TestOrderCreatedSignal:

    def test_order_created_signal_fired_on_checkout(
        self, auth_client, prod_sig, zone_cdmx, db
    ):
        """
        T-508: checkout exitoso emite la señal order_created exactamente una vez.
        """
        handler = MagicMock()
        order_created.connect(handler)
        # DEC-BC-25: el checkout exige un método de envío activo.
        ship = ShippingMethod.objects.create(
            name='Estándar', cost=Decimal('0.00'), estimated_days=5, is_active=True)

        try:
            auth_client.post(ITEMS_URL, {'product_id': prod_sig.pk, 'quantity': 1}, format='json')

            with patch.object(InventoryService, 'check_availability', return_value=[]), \
                 patch.object(InventoryService, 'decrement', return_value=None):
                res = auth_client.post(
                    CHECKOUT_URL,
                    {'address': ADDR, 'shipping_method_id': ship.pk},
                    format='json')

            assert res.status_code == 201, f'Checkout fallo: {res.data}'

            assert handler.call_count == 1, (
                f'order_created debio emitirse exactamente 1 vez; '
                f'fue llamada {handler.call_count} veces'
            )
            call_kwargs = handler.call_args[1]
            assert 'order' in call_kwargs, (
                'La señal debe incluir kwarg "order"'
            )
            assert call_kwargs['order'].order_number.startswith('PY-'), (
                f'order.order_number invalido: {call_kwargs["order"].order_number}'
            )
        finally:
            order_created.disconnect(handler)
