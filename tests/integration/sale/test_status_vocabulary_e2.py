"""Tests — E2a: el vocabulario de estado deja de vivir en el espejo.

Tras V5d la columna ``Order.status`` no existe, pero el **vocabulario** de
estados seguía declarado en ``orders.Order`` (``STATUS_*`` + ``STATUSES``). Eso
dejaba al espejo como propietario del idioma que consume la proyección
canónica: 39 referencias de producción importaban ``Order`` sólo para leer dos
constantes, y ``status_projection`` —el módulo que *produce* el estado— tenía
que importar el modelo espejo para nombrar su propia salida.

Es un acoplamiento invertido y bloquea E5: no se puede dar de baja ``Order``
mientras sea el hogar del idioma. E2a lo mueve a ``status_projection``, que es
quien deriva el estado de los ejes.

El valor de cada constante **no cambia** — es contrato de API pública
(``?status=``, DEC del contrato canónico de la Rebanada 6).
"""
import pytest

from addons.orders import status_projection as sp
from addons.orders.models import Order
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
        """El candado de E2a: si alguien lo devuelve a ``Order``, falla."""
        assert 'STATUS_PENDING' not in vars(Order)
        assert 'STATUSES' not in vars(Order)


class TestLaProyeccionNoDependeDelEspejo:
    """``status_projection`` deja de importar el modelo espejo."""

    def test_el_modulo_no_importa_order(self):
        fuente = open(sp.__file__, encoding='utf-8').read()
        assert 'from .models import Order' not in fuente

    def test_derive_sigue_proyectando_los_mismos_valores(self):
        """El cambio es de hogar, no de comportamiento.

        El ``Payment`` se crea con **ambas** FK porque ``Payment.order`` sigue
        siendo ``NOT NULL`` hacia el espejo (H-API-26: el anclaje de los ejes
        está invertido — la FK legacy es obligatoria y la canónica opcional).
        Ese es el bloqueo de esquema que E5 tendrá que levantar; aquí sólo se
        reproduce el estado real.
        """
        espejo = make_order(status=sp.STATUS_PENDING)
        venta = espejo.sale_order
        assert sp.derive_order_status(venta) == sp.STATUS_PENDING

        Payment.objects.create(
            order=espejo, sale_order=venta, amount=100,
            gateway=Payment.GATEWAY_MANUAL, status=Payment.STATUS_APPROVED)
        assert sp.derive_order_status(venta) == sp.STATUS_PAID

    def test_un_draft_proyecta_draft_y_un_cancel_cancelado(self):
        borrador = SaleOrder.objects.create(state=SaleOrder.STATE_DRAFT)
        assert sp.derive_order_status(borrador) == sp.STATUS_DRAFT

        cancelada = SaleOrder.objects.create(state=SaleOrder.STATE_CANCEL)
        assert sp.derive_order_status(cancelada) == sp.STATUS_CANCELLED
