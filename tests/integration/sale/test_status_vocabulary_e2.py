"""Tests — E2a: el vocabulario de estado deja de vivir en el espejo.

Tras V5d la columna ``SaleOrder.status`` no existe, pero el **vocabulario** de
estados seguía declarado en ``orders.Order`` (``STATUS_*`` + ``STATUSES``). Eso
dejaba al espejo como propietario del idioma que consume la proyección
canónica: 39 referencias de producción importaban ``SaleOrder`` sólo para leer dos
constantes, y ``status_projection`` —el módulo que *produce* el estado— tenía
que importar el modelo espejo para nombrar su propia salida.

Es un acoplamiento invertido y bloquea E5: no se puede dar de baja ``SaleOrder``
mientras sea el hogar del idioma. E2a lo mueve a ``status_projection``, que es
quien deriva el estado de los ejes.

El valor de cada constante **no cambia** — es contrato de API pública
(``?status=``, DEC del contrato canónico de la Rebanada 6).
"""
import pytest

from addons.sale import status_projection as sp
from addons.payment.models import Payment
from addons.sale.models import SaleOrder
from tests.factories.order_factory import make_order

pytestmark = pytest.mark.django_db


class TestVocabularioEnLaProyeccion:
    """Las constantes viven donde se produce el estado."""

    def test_la_proyeccion_declara_el_vocabulario(self):
        assert sp.STATUS_DRAFT == 'DRAFT'
        assert sp.STATUS_PENDING == 'PENDING'
        assert sp.STATUS_PAID == 'PAID'
        assert sp.STATUS_SHIPPED == 'SHIPPED'
        assert sp.STATUS_DELIVERED == 'DELIVERED'
        assert sp.STATUS_CANCELLED == 'CANCELLED'

    def test_conserva_los_estados_no_canonicos_del_enum_historico(self):
        """No se borran aquí: son valores que el enum monolítico admitía.

        ``PROCESSING``/``IN_PREPARATION``/``REFUNDED``/``CANCELLED_TIMEOUT``
        no los emite la proyección (ver ``CANONICAL_ORDER_STATUSES``), pero
        siguen siendo vocabulario declarado — su retiro es decisión aparte.
        """
        assert sp.STATUS_PROCESSING == 'PROCESSING'
        assert sp.STATUS_IN_PREPARATION == 'IN_PREPARATION'
        assert sp.STATUS_REFUNDED == 'REFUNDED'
        assert sp.STATUS_CANCELLED_BY_TIMEOUT == 'CANCELLED_TIMEOUT'

    def test_las_etiquetas_siguen_disponibles(self):
        etiquetas = dict(sp.STATUSES)
        assert etiquetas[sp.STATUS_PENDING] == 'Pendiente de pago'
        assert etiquetas[sp.STATUS_DELIVERED] == 'Entregado'

    def test_el_espejo_ya_no_es_dueno_del_vocabulario(self):
        """El candado de E2a: si alguien lo devuelve a ``SaleOrder``, falla."""
        assert 'STATUS_PENDING' not in vars(SaleOrder)
        assert 'STATUSES' not in vars(SaleOrder)


class TestLaProyeccionNoDependeDelEspejo:
    """``status_projection`` deja de importar el modelo espejo."""

    def test_el_modulo_no_importa_order(self):
        fuente = open(sp.__file__, encoding='utf-8').read()
        assert 'from .models import SaleOrder' not in fuente

    def test_derive_sigue_proyectando_los_mismos_valores(self):
        """El cambio es de hogar, no de comportamiento.

        Post-E5 (retiro del addon espejo ``orders``, ``api@77bd1f0``): la
        venta **es** la orden — ``make_order`` ya no devuelve un segundo
        objeto que enlazar. ``Payment.sale_order`` es el único ancla
        (NOT NULL, PROTECT — ver ``payment/models/payment.py``).
        """
        venta = make_order(status=sp.STATUS_PENDING)
        assert sp.derive_order_status(venta) == sp.STATUS_PENDING

        Payment.objects.create(
            sale_order=venta, amount=100,
            gateway=Payment.GATEWAY_MANUAL, status=Payment.STATUS_APPROVED)
        assert sp.derive_order_status(venta) == sp.STATUS_PAID

    def test_un_draft_proyecta_draft_y_un_cancel_cancelado(self):
        borrador = SaleOrder.objects.create(state=SaleOrder.STATE_DRAFT)
        assert sp.derive_order_status(borrador) == sp.STATUS_DRAFT

        cancelada = SaleOrder.objects.create(state=SaleOrder.STATE_CANCEL)
        assert sp.derive_order_status(cancelada) == sp.STATUS_CANCELLED
