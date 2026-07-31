"""Los dos proxies del espejo tienen reemplazo canónico equivalente.

E5/R5 del retiro de ``orders`` (:ref:`analisis-retiro-addon-orders-e5`). Los
proxies ``ActiveOrder`` y ``DeliveredOrder`` son modelos ``proxy=True`` sobre
``orders_order``: no pueden sobrevivir a la baja del espejo. Sus dos
consumidores reales son de una línea cada uno:

- ``settings_app/views.py`` — protege un ``ShippingMethod`` de desactivarse
  mientras haya órdenes activas usándolo.
- ``payments/views.py`` — comprador recurrente (al menos una orden entregada).

El reemplazo cambia además el campo del filtro, porque la canónica los nombra
distinto: ``Order.user`` → ``SaleOrder.partner`` y ``Order.shipping_method`` →
``SaleOrder.carrier`` (ambos apuntan al mismo destino: ``AUTH_USER_MODEL`` y
``delivery.ShippingMethod``). Estos casos fijan la equivalencia **antes** de
tocar a los consumidores, para que el cambio de campo sea observable y no un
supuesto.
"""
from decimal import Decimal

import pytest

from addons.delivery.models import ShippingMethod
from addons.orders.proxy_models import ActiveOrder, DeliveredOrder
from addons.sale.models import SaleOrder
from addons.sale.status_projection import (
    STATUS_CANCELLED,
    STATUS_DELIVERED,
    STATUS_DRAFT,
    STATUS_PAID,
    STATUS_PENDING,
    STATUS_SHIPPED,
    active_sale_orders,
    filter_orders_by_status,
)
from tests.factories.order_factory import make_courier, make_order
from tests.factories.user_factory import UserFactory

pytestmark = pytest.mark.django_db


ACTIVOS = [STATUS_PENDING, STATUS_PAID, STATUS_SHIPPED]
NO_ACTIVOS = [STATUS_DELIVERED, STATUS_CANCELLED]


@pytest.fixture
def metodo_envio():
    """Método de envío compartido por el universo."""
    return ShippingMethod.objects.create(
        name='E5R5 Express', cost=Decimal('99.00'),
        estimated_days=3, is_active=True)


@pytest.fixture
def universo(metodo_envio):
    """Una orden por estado alcanzable, mismo courier y método de envío."""
    courier = make_courier()
    return {
        estado: make_order(status=estado, courier=courier,
                           shipping_method=metodo_envio)
        for estado in ACTIVOS + NO_ACTIVOS
    }


def test_activas_son_las_mismas_por_ambos_caminos(universo):
    """``active_sale_orders()`` selecciona las canónicas de las mismas filas
    que el proxy ``ActiveOrder``."""
    por_proxy = set(
        ActiveOrder.objects.values_list('sale_order_id', flat=True))
    por_canonica = set(active_sale_orders().values_list('pk', flat=True))

    assert por_canonica == por_proxy
    assert por_canonica == {universo[e].sale_order_id for e in ACTIVOS}


@pytest.mark.parametrize('estado', NO_ACTIVOS)
def test_entregada_y_cancelada_quedan_fuera_de_activas(universo, estado):
    """Una entregada o cancelada no es activa — es lo que protege al
    ``ShippingMethod`` de un falso positivo que impida desactivarlo."""
    assert universo[estado].sale_order_id not in set(
        active_sale_orders().values_list('pk', flat=True))


def test_draft_no_es_activa():
    """``DRAFT`` es carrito, no venta confirmada: fuera del conjunto activo.

    Va aparte del universo porque el factory no le asigna courier ni fecha —
    un ``state='sale'`` sin ``date_order`` es un estado que el flujo real
    nunca produce.
    """
    borrador = make_order(status=STATUS_DRAFT)
    assert borrador.sale_order_id not in set(
        active_sale_orders().values_list('pk', flat=True))


def test_el_filtro_por_metodo_de_envio_migra_de_shipping_method_a_carrier(
        universo, metodo_envio):
    """El consumidor filtra por método de envío; la canónica lo llama
    ``carrier``. Mismo destino (``delivery.ShippingMethod``), otro nombre.

    Es el caso que protege al ``ShippingMethod`` de desactivarse con órdenes
    vivas: si la query canónica contara 0 donde el proxy cuenta 3, el guard
    dejaría borrar un método en uso.
    """
    por_proxy = ActiveOrder.objects.filter(shipping_method=metodo_envio).count()
    por_canonica = active_sale_orders().filter(carrier=metodo_envio).count()

    assert por_canonica == por_proxy == len(ACTIVOS)


def test_comprador_recurrente_migra_de_user_a_partner():
    """El consumidor pregunta si el usuario tiene alguna orden entregada; la
    canónica llama ``partner`` a ese campo."""
    usuario = UserFactory(email='recurrente-e5r5@practicayoruba.mx')
    make_order(status=STATUS_DELIVERED, user=usuario)

    por_proxy = DeliveredOrder.objects.filter(user=usuario).exists()
    por_canonica = filter_orders_by_status(
        SaleOrder.objects.all(), STATUS_DELIVERED,
    ).filter(partner=usuario).exists()

    assert por_canonica is por_proxy is True


def test_usuario_sin_entregadas_no_es_recurrente():
    """El contrafactual: sin órdenes entregadas, ambos caminos dan False.

    Sin este caso, un filtro roto que devolviera *todo* pasaría el test
    anterior.
    """
    usuario = UserFactory(email='novato-e5r5@practicayoruba.mx')

    assert DeliveredOrder.objects.filter(user=usuario).exists() is False
    assert filter_orders_by_status(
        SaleOrder.objects.all(), STATUS_DELIVERED,
    ).filter(partner=usuario).exists() is False
