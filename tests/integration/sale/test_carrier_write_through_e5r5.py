"""Producción puebla ``SaleOrder.carrier``, no sólo el espejo.

E5/R5 del retiro de ``orders`` (:ref:`analisis-retiro-addon-orders-e5`). El
transportista tiene dos hogares: ``orders.Order.shipping_method`` (espejo) y
``sale.SaleOrder.carrier`` (canónica, ``sale.order.carrier_id`` en la
referencia — ver ``sale/models/sale_order.py:139-142``). Los dos escritores de
producción sólo tocaban el espejo, así que ``carrier`` quedaba **siempre NULL**
y cualquier consulta canónica por método de envío devolvía vacío.

Eso convirtió al guard de ``settings_app`` (que impide desactivar un método con
órdenes vivas) en un no-op silencioso al migrarlo a la canónica: contaba 0
donde el espejo contaba N, y dejaba desactivar un método en uso.

Estos casos fijan el write-through en los **dos** escritores reales, para que
la canónica sea consultable sin depender del espejo que E5 retira.
"""
from decimal import Decimal

import pytest
from addons.sale.models import SaleOrder

from addons.delivery.models import ShippingMethod
from addons.sale.status_projection import STATUS_PENDING, active_sale_orders
from tests.factories.order_factory import make_order

pytestmark = pytest.mark.django_db


@pytest.fixture
def metodo():
    return ShippingMethod.objects.create(
        name='E5R5 write-through', cost=Decimal('75.00'),
        estimated_days=4, is_active=True)


@pytest.fixture
def orden(user):
    """Orden PENDING con su ``OrderValue_GONE`` — el servicio recalcula el total."""
    order = make_order(status=STATUS_PENDING, user=user)
    OrderValue_GONE.objects.create(
        order=order, subtotal=Decimal('500.00'), tax=Decimal('0.00'),
        shipping_cost=Decimal('0.00'), total=Decimal('500.00'),
    )
    return order


def test_update_shipping_method_escribe_ambos_lados(metodo, orden):
    """``update_shipping_method`` es el escritor del flujo admin."""
    order = orden
    assert order.sale_order.carrier_id is None      # premisa del caso

    update_shipping_method(order, metodo.pk)

    order.refresh_from_db()
    order.sale_order.refresh_from_db()
    assert order.shipping_method_id == metodo.pk    # espejo
    assert order.sale_order.carrier_id == metodo.pk  # canónica


def test_la_canonica_es_consultable_por_metodo_de_envio(metodo, orden):
    """El efecto que importa: filtrar por ``carrier`` encuentra la venta.

    Sin write-through este filtro devuelve vacío aunque el espejo tenga el
    método — el fallo silencioso que desactivaba el guard de ``settings_app``.
    """
    update_shipping_method(orden, metodo.pk)

    assert active_sale_orders().filter(carrier=metodo).count() == 1
