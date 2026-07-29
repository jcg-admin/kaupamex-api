"""Tests — I2: los lectores de identidad se re-anclan al canónico (H-API-31).

Tras I1 (``api@b5945d6``) ``order_number`` y ``sale_order.name`` portan el
mismo valor, así que el re-anclaje de los 4 lectores que atravesaban la FK
espejo nullable es mecánico — y elimina su fragilidad post-E4-pre: una
guía/reseña/pago **sólo-canónicos** ya no rompen el serializer ni pierden
la notificación en silencio.

Sitios re-anclados (inventario H-API-31):

- ``delivery/serializers.py`` — ``source='sale_order.name'``
- ``reviews/serializers.py``  — ``source='sale_order.name'``
- ``delivery/views.py``       — dashboard in-transit lee ``sale_order.name``
- ``mail/notification_signals.py`` (UC-NOT-05) — el reembolso notifica
  desde ``payment.sale_order`` (``name`` + ``partner``)
"""
from decimal import Decimal
from uuid import uuid4

import pytest
from django.utils import timezone

from addons.catalogue.models import Category, Product
from addons.delivery.models import Courier, ShipmentGuide
from addons.delivery.serializers import ShipmentGuideSerializer
from addons.mail.models import Notification
from addons.payment.models import Payment, Refund
from addons.rating.models import Review
from addons.reviews.serializers import ReviewAdminSerializer
from addons.sale.models import SaleOrder, SaleOrderLine
from addons.sale.services import add_item_to_draft, confirm_draft_order
from addons.users.models import IdentityUser

pytestmark = pytest.mark.django_db


@pytest.fixture
def producto():
    cat = Category.objects.create(name='Cat I2', slug='cat-i2', is_active=True)
    prod = Product.objects.create(
        name='Prod I2', slug='prod-i2', sku='SKU-I2',
        price=Decimal('60.00'), stock=9, is_active=True, is_published=True)
    prod.categories.add(cat)
    return prod


@pytest.fixture
def venta(producto):
    """Venta confirmada por el flujo real (nombre de secuencia asignado)."""
    draft = SaleOrder.objects.create(
        state=SaleOrder.STATE_DRAFT, cart_token=uuid4())
    add_item_to_draft(draft, producto, quantity=1)
    confirm_draft_order(
        draft,
        address_data={'recipient_name': 'I2', 'street': 'Calle 2',
                      'city': 'CDMX', 'state': 'CDMX', 'zip_code': '01000'},
        guest_email='i2@test.mx')
    draft.refresh_from_db()
    return draft


class TestSerializersEmitenIdentidadCanonica:

    def test_guia_solo_canonica_publica_el_nombre_de_la_venta(self, venta):
        courier = Courier.objects.create(name='DHL I2', code='DHL-I2')
        guia = ShipmentGuide.objects.create(
            sale_order=venta, order=None, courier=courier,
            tracking_number='TRK-I2-1')
        data = ShipmentGuideSerializer(guia).data
        assert data['order_number'] == venta.name

    def test_resena_solo_canonica_publica_el_nombre_de_la_venta(self, venta):
        usuario = IdentityUser.objects.create_user(
            email='rev.i2@example.com', password='x')
        prod = venta.order_line.first().product
        resena = Review.objects.create(
            user=usuario, product=prod, sale_order=venta, order=None,
            rating=4, title='I2', body='Lector re-anclado')
        data = ReviewAdminSerializer(resena).data
        assert data['order_number'] == venta.name


class TestReembolsoNotificaDesdeLaCanonica:

    def test_refund_de_pago_solo_canonico_no_pierde_la_notificacion(self, producto):
        """Antes de I2 el signal atravesaba ``payment.order`` (nullable tras
        E4-pre): un pago sólo-canónico caía al ``except`` y el email se
        perdía en silencio. Ahora notifica desde la canónica."""
        comprador = IdentityUser.objects.create_user(
            email='refund.i2@example.com', password='x')
        draft = SaleOrder.objects.create(
            state=SaleOrder.STATE_DRAFT, partner=comprador)
        SaleOrderLine.objects.create(
            order=draft, product=producto, name=producto.name,
            product_uom_qty=1, price_unit=producto.price)
        draft.action_confirm()

        pago = Payment.objects.create(
            sale_order=draft, order=None, gateway=Payment.GATEWAY_MANUAL,
            status=Payment.STATUS_APPROVED, amount=Decimal('60.00'))
        Refund.objects.create(
            payment=pago, amount=Decimal('60.00'),
            status=Refund.STATUS_APPROVED)

        notif = Notification.objects.filter(user=comprador).latest('id')
        assert draft.name in notif.subject


class TestLosLectoresYaNoAtraviesanElEspejo:

    def test_serializers_leen_la_identidad_de_la_canonica(self):
        """Los serializers declaran ``source='sale_order.name'``.

        No se puede afirmar "0 apariciones de ``order.order_number``" en
        ``delivery/views.py``: su dashboard grupo-A itera ``Order``
        directamente (``views.py:79``) y ahí el atributo es legítimo — no
        atraviesa la FK espejo desde un eje. El candado apunta a lo que I2
        sí cambió: la fuente declarada de los dos serializers.
        """
        for ruta in ('src/addons/delivery/serializers.py',
                     'src/addons/reviews/serializers.py'):
            fuente = open(ruta, encoding='utf-8').read()
            assert "source='sale_order.name'" in fuente, ruta
            assert "source='order.order_number'" not in fuente, ruta

    def test_el_dashboard_de_guias_no_atraviesa_el_espejo(self):
        fuente = open('src/addons/delivery/views.py', encoding='utf-8').read()
        assert 'guide.order.order_number' not in fuente
        assert 'guide.sale_order.name' in fuente
