"""
Tests — VoucherUsage single-use-by-user (T-302, DEC-BC-10).

Verifica:
  - test_voucher_used_twice_same_user_rejects_409: el mismo user no puede
    aplicar 2 veces el mismo voucher al carrito cuando ya hay uno aplicado.
  - test_current_uses_increments_atomic: current_uses se incrementa en el
    checkout dentro de la transaccion atomica.
"""
import pytest
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch

from tests.factories.product_factory import make_category, make_product
from addons.stock.services import InventoryService
from addons.delivery.models import ShippingZone
from addons.delivery.models import ShippingMethod
from addons.loyalty.models import Voucher, VoucherUsage

pytestmark = pytest.mark.integration

VOUCHER_APPLY_URL = '/api/v2/cart/voucher/'
ITEMS_URL         = '/api/v2/cart/items/'


def _future(**kw):
    return timezone.now() + timedelta(**kw)


@pytest.fixture
def zone_cdmx(db):
    zone, _ = ShippingZone.objects.get_or_create(
        zip_code_prefix='06', defaults={'name': 'Ciudad de México', 'is_active': True}
    )
    return zone


@pytest.fixture
def voucher_single(db):
    return Voucher.objects.create(
        code='SINGLE10',
        voucher_type='FIXED',
        discount_value=Decimal('10.00'),
        valid_from=timezone.now() - timedelta(days=1),
        valid_until=_future(days=30),
        is_active=True,
        max_uses=100,
        current_uses=0,
    )


@pytest.fixture
def cat_vou(db):
    return make_category('Cat Voucher')


@pytest.fixture
def product_vou(db, cat_vou):
    return make_product(
        name='Producto Voucher', default_code='VOU-001',
        price=Decimal('200.00'), stock=10, categ=cat_vou,
    )


class TestVoucherAlreadyApplied:
    """DEC-BC-20: VOUCHER_ALREADY_APPLIED 409."""

    def test_voucher_used_twice_same_user_rejects_409(
        self, api_client, auth_client, voucher_single, product_vou, db
    ):
        """
        Aplicar voucher dos veces seguidas al mismo carrito retorna 409
        con VOUCHER_ALREADY_APPLIED en el segundo intento.
        """
        # Agregar un item para que el carrito tenga subtotal
        auth_client.post(ITEMS_URL, {'product_id': product_vou.pk, 'quantity': 1})

        # Primera aplicacion → 200
        res1 = auth_client.post(VOUCHER_APPLY_URL, {'code': voucher_single.code})
        assert res1.status_code == 200, f'Primera aplicacion debio ser 200; {res1.data}'

        # Segunda aplicacion (misma sesion, mismo carrito) → 409
        res2 = auth_client.post(VOUCHER_APPLY_URL, {'code': voucher_single.code})
        assert res2.status_code == 409, (
            f'Segunda aplicacion debio ser 409 VOUCHER_ALREADY_APPLIED; '
            f'status={res2.status_code}, data={res2.data}'
        )
        assert res2.data.get('codigo_error') == 'VOUCHER_ALREADY_APPLIED'


class TestVoucherUsageCreatedOnCheckout:
    """DEC-BC-10: current_uses + VoucherUsage al hacer checkout."""

    def test_current_uses_increments_atomic(
        self, api_client, auth_client, user, voucher_single, product_vou, zone_cdmx, db
    ):
        """
        Hacer checkout con voucher aplicado incrementa current_uses
        y crea VoucherUsage(user, voucher).
        """

        # Agregar item y aplicar voucher
        auth_client.post(ITEMS_URL, {'product_id': product_vou.pk, 'quantity': 1})
        auth_client.post(VOUCHER_APPLY_URL, {'code': voucher_single.code})

        initial_uses = Voucher.objects.get(pk=voucher_single.pk).current_uses

        # DEC-BC-25: el checkout exige un método de envío activo.
        ship = ShippingMethod.objects.create(
            name='Estándar', cost=Decimal('0.00'), estimated_days=5, is_active=True)

        checkout_data = {
            'address': {
                'recipient_name': 'Test',
                'street': 'Calle 1',
                'city': 'CDMX',
                'state': 'CMX',
                'zip_code': '06600',
                'country': 'MX',
            },
            'shipping_method_id': ship.pk,
        }

        # Mock InventoryService para no depender de stock
        with patch.object(InventoryService, 'check_availability', return_value=[]), \
             patch.object(InventoryService, 'decrement', return_value=None):
            res = auth_client.post('/api/v2/orders/', checkout_data, format='json')

        assert res.status_code == 201, f'Checkout fallo: {res.data}'

        # current_uses debe haber incrementado
        voucher_single.refresh_from_db()
        assert voucher_single.current_uses == initial_uses + 1, (
            f'current_uses debio incrementar; era {initial_uses}, '
            f'ahora {voucher_single.current_uses}'
        )

        # VoucherUsage debe existir
        exists = VoucherUsage.objects.filter(user=user, voucher=voucher_single).exists()
        assert exists, 'VoucherUsage no fue creado en checkout'
