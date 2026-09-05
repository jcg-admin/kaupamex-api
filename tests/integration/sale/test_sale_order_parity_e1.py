"""Tests — E1 paridad de campos ``SaleOrder`` (retiro de la entidad espejo).

Primera rebanada del retiro de ``orders.Order`` como entidad (SOL-097 etapa 3,
sucesora de V5d). El espejo aún se crea; lo que esta rebanada cierra es la
**brecha de campos**: lo que el flujo vivo guarda en ``Order`` y el canónico
``SaleOrder`` no podía representar.

Alcance verificado contra la referencia Odoo (no es el "porta 7 columnas" que
se estimó al abrir la rebanada):

- ``carrier`` — Odoo ``sale.order.carrier_id``
  (``delivery/models/sale_order.py:13``). Se porta.
- ``admin_cancelled_by`` / ``cancellation_reason`` / ``cancelled_at`` — sin
  equivalente en Odoo core (allí la cancelación es ``state`` + ``mail.thread``);
  son extensión propia del proyecto (UC-ORD-04, UC-ORD-08). Se portan.
- ``order_number`` — **ya existía** como ``SaleOrder.name``. No se porta.
- ``voucher_code`` / ``voucher_discount`` — **ya existían** como
  ``sale_loyalty.SaleOrderCoupon``. No se portan.
- ``shipping_cost`` — en Odoo es una **línea** ``is_delivery=True``, no una
  columna; su port tiene prerequisito (H-API-24) y es rebanada aparte.
"""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from addons.delivery.models import ShippingMethod
from addons.sale.models import SaleOrder

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def draft():
    return SaleOrder.objects.create(state=SaleOrder.STATE_DRAFT)


class TestCarrierParity:
    """``SaleOrder.carrier`` — paridad con ``sale.order.carrier_id`` de Odoo."""

    def test_carrier_es_opcional_y_arranca_vacio(self, draft):
        assert draft.carrier_id is None

    def test_carrier_guarda_el_metodo_de_envio_elegido(self, draft):
        metodo = ShippingMethod.objects.create(
            name='Estándar E1', cost=Decimal('99.00'), estimated_days=3)
        draft.carrier = metodo
        draft.save(update_fields=['carrier', 'updated_at'])

        draft.refresh_from_db()
        assert draft.carrier_id == metodo.pk
        assert draft.carrier.cost == Decimal('99.00')

    def test_borrar_el_metodo_no_borra_la_orden(self, draft):
        """``SET_NULL``: el catálogo de envío es configuración, no la venta."""
        metodo = ShippingMethod.objects.create(
            name='Temporal E1', cost=Decimal('50.00'), estimated_days=2)
        draft.carrier = metodo
        draft.save(update_fields=['carrier', 'updated_at'])

        metodo.delete()

        draft.refresh_from_db()
        assert draft.pk is not None
        assert draft.carrier_id is None

    def test_la_orden_es_alcanzable_desde_el_metodo(self, draft):
        metodo = ShippingMethod.objects.create(
            name='Inverso E1', cost=Decimal('120.00'), estimated_days=5)
        draft.carrier = metodo
        draft.save(update_fields=['carrier', 'updated_at'])

        assert list(metodo.sale_orders.all()) == [draft]


class TestCancellationParity:
    """Trazabilidad de cancelación (UC-ORD-04 / UC-ORD-08)."""

    def test_una_orden_viva_no_tiene_rastro_de_cancelacion(self, draft):
        assert draft.cancelled_at is None
        assert draft.cancellation_reason == ''
        assert draft.admin_cancelled_by_id is None

    def test_cancelacion_del_comprador_deja_motivo_sin_admin(self, draft):
        momento = timezone.now()
        draft.state = SaleOrder.STATE_CANCEL
        draft.cancellation_reason = 'Ya no lo necesito'
        draft.cancelled_at = momento
        draft.save(update_fields=['state', 'cancellation_reason',
                                  'cancelled_at', 'updated_at'])

        draft.refresh_from_db()
        assert draft.cancellation_reason == 'Ya no lo necesito'
        assert draft.cancelled_at is not None
        # Distinción del UC: sin admin ⇒ la canceló el comprador.
        assert draft.admin_cancelled_by_id is None

    def test_cancelacion_administrativa_registra_quien(self, draft):
        admin = User.objects.create_user(
            login='admin.e1@kaupamex.mx', password='x')
        draft.state = SaleOrder.STATE_CANCEL
        draft.admin_cancelled_by = admin
        draft.cancellation_reason = 'Sin inventario'
        draft.cancelled_at = timezone.now()
        draft.save(update_fields=['state', 'admin_cancelled_by',
                                  'cancellation_reason', 'cancelled_at',
                                  'updated_at'])

        draft.refresh_from_db()
        assert draft.admin_cancelled_by_id == admin.pk
        assert list(admin.admin_cancelled_sale_orders.all()) == [draft]

    def test_borrar_al_admin_conserva_la_orden_cancelada(self, draft):
        """El historial de la venta sobrevive a la baja de la cuenta."""
        admin = User.objects.create_user(
            login='baja.e1@kaupamex.mx', password='x')
        draft.state = SaleOrder.STATE_CANCEL
        draft.admin_cancelled_by = admin
        draft.cancellation_reason = 'Fraude'
        draft.cancelled_at = timezone.now()
        draft.save(update_fields=['state', 'admin_cancelled_by',
                                  'cancellation_reason', 'cancelled_at',
                                  'updated_at'])

        admin.delete()

        draft.refresh_from_db()
        assert draft.admin_cancelled_by_id is None
        assert draft.cancellation_reason == 'Fraude'
        assert draft.state == SaleOrder.STATE_CANCEL


class TestParidadYaCubierta:
    """Lo que NO se porta porque el canónico ya lo representa.

    Estos tests son el candado de la decisión de alcance: si alguien vuelve a
    añadir ``order_number`` o ``voucher_*`` a ``SaleOrder``, sobra — y estos
    tests documentan dónde vive ya cada dato.
    """

    def test_el_numero_de_orden_es_name(self, draft):
        assert hasattr(draft, 'name')
        assert not hasattr(draft, 'order_number')

    def test_el_voucher_vive_en_sale_loyalty_no_en_la_cabecera(self, draft):
        assert not hasattr(draft, 'voucher_code')
        assert not hasattr(draft, 'voucher_discount')
        # El accesor del bridge existe (OneToOne inverso de SaleOrderCoupon).
        assert hasattr(SaleOrder, 'coupon')
