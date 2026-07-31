"""El proyector de estado filtra igual sobre la canónica que sobre el espejo.

E5/R2 del retiro de ``orders`` (:ref:`analisis-retiro-addon-orders-e5`). El
módulo se muda a ``sale/`` y su trío de queryset —``annotate_status_axes``,
``_canonical_status_q``, ``filter_orders_by_status``— deja de asumir que las
filas son ``orders.Order``.

Por qué hace falta el test (H-API-98): las dos subconsultas ``Exists`` joinean
por ``Payment.order``/``ShipmentGuide.order``, que son las FK **al espejo**. Un
``git mv`` habría dejado el filtro devolviendo vacío en cuanto el espejo se
vaciara — sin ``ImportError``, sin excepción: silencio. Estos casos fijan la
equivalencia entre ambas formas para que el cambio de join sea observable.
"""
import pytest

from addons.sale.models import SaleOrder
from addons.sale.status_projection import (
    STATUS_CANCELLED,
    STATUS_DELIVERED,
    STATUS_PAID,
    STATUS_PENDING,
    STATUS_SHIPPED,
    filter_orders_by_status,
)
from tests.factories.order_factory import make_order

pytestmark = pytest.mark.django_db


ESTADOS = [
    STATUS_PENDING,
    STATUS_PAID,
    STATUS_SHIPPED,
    STATUS_DELIVERED,
    STATUS_CANCELLED,
]


@pytest.fixture
def universo():
    """Una orden por cada estado proyectado alcanzable."""
    return {estado: make_order(status=estado) for estado in ESTADOS}


@pytest.mark.parametrize('estado', ESTADOS)
def test_filtro_canonico_selecciona_la_misma_venta_que_el_espejo(universo, estado):
    """``filter_orders_by_status`` sobre ``SaleOrder`` devuelve la canónica de
    la misma fila que devuelve sobre ``SaleOrder``."""
    esperado = universo[estado].sale_order_id

    por_espejo = filter_orders_by_status(SaleOrder.objects.all(), estado)
    por_canonica = filter_orders_by_status(SaleOrder.objects.all(), estado)

    assert list(por_espejo.values_list('sale_order_id', flat=True)) == [esperado]
    assert list(por_canonica.values_list('pk', flat=True)) == [esperado]


@pytest.mark.parametrize('estado', ESTADOS)
def test_el_filtro_canonico_excluye_los_demas_estados(universo, estado):
    """Un estado no arrastra a los otros cuatro — descarta que el join roto
    devuelva todo o nada."""
    seleccionadas = set(
        filter_orders_by_status(SaleOrder.objects.all(), estado)
        .values_list('pk', flat=True)
    )
    otras = {
        orden.sale_order_id
        for otro, orden in universo.items() if otro != estado
    }

    assert seleccionadas == {universo[estado].sale_order_id}
    assert not (seleccionadas & otras)


def test_estado_fuera_del_contrato_publico_es_rechazado():
    """El vocabulario público no crece por mudar el módulo."""
    with pytest.raises(ValueError):
        filter_orders_by_status(SaleOrder.objects.all(), 'PROCESSING')
