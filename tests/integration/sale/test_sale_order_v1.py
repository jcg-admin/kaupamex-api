"""Tests — V1 de la unificación orders→sale (analisis-unificar-orders-sale).

V1 es additiva: ``SaleOrder`` gana ``guest_email``/``notes`` (lo que el
flujo vivo del strangler necesita, DEC-FW-02) y los satélites
``OrderAddress``/``OrderStatusLog`` ganan la FK dual transitoria a
``sale.SaleOrder`` (V2 conmuta el flujo; V5 retira la FK a Order).
"""
import pytest

from addons.orders.models import OrderAddress, OrderStatusLog
from addons.sale.models import SaleOrder

pytestmark = pytest.mark.django_db


class TestSaleOrderV1Fields:
    def test_guest_email_and_notes_persist(self):
        so = SaleOrder.objects.create(
            guest_email='guest-v1@test.mx', notes='entregar en portería')
        so.refresh_from_db()
        assert so.guest_email == 'guest-v1@test.mx'
        assert so.notes == 'entregar en portería'
        assert so.state == SaleOrder.STATE_DRAFT

    def test_defaults_are_empty(self):
        so = SaleOrder.objects.create()
        so.refresh_from_db()
        assert so.guest_email == ''
        assert so.notes == ''


class TestSatelliteDualFkV1:
    def test_order_address_anchors_to_sale_order(self):
        so = SaleOrder.objects.create()
        addr = OrderAddress.objects.create(
            sale_order=so, recipient_name='Test V1', street='Calle 1',
            city='CDMX', state='CMX', zip_code='06600',
        )
        assert so.delivery_address.pk == addr.pk
        assert addr.order_id is None  # la FK legacy es opcional en V1

    def test_status_log_anchors_to_sale_order(self):
        so = SaleOrder.objects.create()
        log = OrderStatusLog.objects.create(
            sale_order=so, previous_status='draft', new_status='sale')
        assert list(so.status_logs.all()) == [log]
