"""Tests — V1 de la unificación orders→sale (analisis-unificar-orders-sale).

V1 fue additiva: ``SaleOrder`` ganó ``guest_email``/``notes`` (lo que el flujo
vivo del strangler necesitaba, DEC-FW-02) y los satélites ganaron una FK dual
transitoria hacia ``sale.SaleOrder``.

**Estado tras SOL-098:** la dualidad terminó — V5 retiró la FK al espejo y el
addon ``orders`` desapareció (``api@77bd1f0``). Lo que V1 introdujo como
"segunda ancla" es hoy la **única**, así que aquí se verifica esa forma final.
``SaleOrderStatusLog`` se fue con el espejo: su test no se reescribe porque no
queda modelo que probar, y conservarlo vacío afirmaría una cobertura
inexistente.
"""
import pytest

from addons.delivery.models import DeliveryAddress
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


class TestSatelliteAnchor:
    """El satélite cuelga de la venta, y de nada más."""

    def test_delivery_address_anchors_to_sale_order(self):
        so = SaleOrder.objects.create()
        addr = DeliveryAddress.objects.create(
            sale_order=so, recipient_name='Test V1', street='Calle 1',
            city='CDMX', state='CMX', zip_code='06600',
        )
        assert so.delivery_address.pk == addr.pk
