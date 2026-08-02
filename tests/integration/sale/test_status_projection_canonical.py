"""El proyector de estado filtra la venta canónica por cada estado del ciclo.

E5/R2 del retiro de ``orders`` (:ref:`analisis-retiro-addon-orders-e5`). El
módulo se mudó a ``sale/`` y su trío de queryset —``annotate_status_axes``,
``_canonical_status_q``, ``filter_orders_by_status``— dejó de asumir que las
filas eran ``orders.Order``.

Retiro parcial (2026-08): el retiro del addon espejo ``orders`` (SOL-098,
``api@77bd1f0``) le quitó el segundo lado a la comparación "espejo vs
canónica" que este módulo protegía (H-API-98) — ``make_order`` ya no
devuelve un objeto ``.sale_order_id`` distinto de la venta misma. Lo que
sigue vigente es que el filtro selecciona **exactamente** la venta de su
estado y descarta las demás; eso es lo que se prueba aquí.
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
def test_filtro_canonico_selecciona_la_venta_de_su_estado(universo, estado):
    esperado = universo[estado].pk
    seleccionadas = filter_orders_by_status(SaleOrder.objects.all(), estado)
    assert list(seleccionadas.values_list('pk', flat=True)) == [esperado]


@pytest.mark.parametrize('estado', ESTADOS)
def test_el_filtro_canonico_excluye_los_demas_estados(universo, estado):
    """Un estado no arrastra a los otros cuatro — descarta que el join roto
    devuelva todo o nada."""
    seleccionadas = set(
        filter_orders_by_status(SaleOrder.objects.all(), estado)
        .values_list('pk', flat=True)
    )
    otras = {
        orden.pk
        for otro, orden in universo.items() if otro != estado
    }

    assert seleccionadas == {universo[estado].pk}
    assert not (seleccionadas & otras)


def test_estado_fuera_del_contrato_publico_es_rechazado():
    """El vocabulario público no crece por mudar el módulo."""
    with pytest.raises(ValueError):
        filter_orders_by_status(SaleOrder.objects.all(), 'PROCESSING')
