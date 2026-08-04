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

Post-E5 (retiro del addon espejo ``orders``, ``api@77bd1f0``): los FK
``order`` de ``ShipmentGuide``/``Review``/``Payment`` que E4-pre había vuelto
nullable **ya no existen** — se retiraron del modelo, no sólo de la
obligatoriedad. Los ``order=None`` explícitos de este módulo se quitan (el
kwarg ya no existe).

**Retiro parcial (H-API, este pase):** la familia ``reviews`` (serializer
admin ``ReviewAdminSerializer``, ``reviews/serializers.py``) se disolvió en
``rating`` sin llevarse la capa de serialización — ``rating`` sólo tiene
``models/`` (verificado: ``find src/addons/rating -name '*.py'`` → sin
``serializers.py`` ni ``views.py``). Los casos que ejercían ese serializer
se retiran; el modelo ``rating.Review`` anclado a la canónica (sin FK
espejo) sigue cubierto en ``test_axis_anchor_e4pre.py`` y
``test_sale_order_v4a.py``.
"""
from decimal import Decimal
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model

from addons.delivery.models import Courier, ShipmentGuide
from addons.delivery.controllers.serializers import ShipmentGuideSerializer
from addons.mail.models import Notification
from addons.payment.models import Payment, Refund
from addons.sale.models import SaleOrder, SaleOrderLine
from addons.sale.services import add_item_to_draft, confirm_draft_order
from tests.factories.product_factory import make_category, make_product

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def producto():
    cat = make_category(name='Cat I2')
    return make_product(name='Prod I2', price=Decimal('60.00'), stock=9, categ=cat)


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
            sale_order=venta, courier=courier,
            tracking_number='TRK-I2-1')
        data = ShipmentGuideSerializer(guia).data
        assert data['order_number'] == venta.name


class TestReembolsoNotificaDesdeLaCanonica:

    def test_refund_de_pago_solo_canonico_no_pierde_la_notificacion(self, producto):
        """Antes de I2 el signal atravesaba ``payment.order`` (nullable tras
        E4-pre): un pago sólo-canónico caía al ``except`` y el email se
        perdía en silencio. Ahora notifica desde la canónica."""
        comprador = User.objects.create_user(
            login='refund.i2@practicayoruba.mx', password='x')
        draft = SaleOrder.objects.create(
            state=SaleOrder.STATE_DRAFT, partner=comprador)
        SaleOrderLine.objects.create(
            order=draft, product=producto, name=producto.name,
            product_uom_qty=1, price_unit=producto.lst_price)
        draft.action_confirm()

        pago = Payment.objects.create(
            sale_order=draft, gateway=Payment.GATEWAY_MANUAL,
            status=Payment.STATUS_APPROVED, amount=Decimal('60.00'))
        Refund.objects.create(
            payment=pago, amount=Decimal('60.00'),
            status=Refund.STATUS_APPROVED)

        notif = Notification.objects.filter(user=comprador).latest('id')
        assert draft.name in notif.subject


class TestLosLectoresYaNoAtraviesanElEspejo:

    def test_serializers_leen_la_identidad_de_la_canonica(self):
        """Los serializers declaran ``source='sale_order.name'``.

        No se puede afirmar "0 apariciones de ``order.order_number``" en el
        controlador: su dashboard grupo-A itera ``Order`` directamente y ahí
        el atributo es legítimo — no atraviesa la FK espejo desde un eje. El
        candado apunta a lo que I2 sí cambió: la fuente declarada de los dos
        serializers.

        Las capas planas ``serializers.py``/``views.py`` se movieron bajo
        ``controllers/`` (mapa de H-API-238); el archivo de vistas quedó como
        ``controllers/main.py``.
        """
        fuente = open('src/addons/delivery/controllers/serializers.py',
                      encoding='utf-8').read()
        assert "source='sale_order.name'" in fuente
        assert "source='order.order_number'" not in fuente

    def test_el_dashboard_de_guias_no_atraviesa_el_espejo(self):
        fuente = open('src/addons/delivery/controllers/main.py',
                      encoding='utf-8').read()
        assert 'guide.order.order_number' not in fuente
        assert 'guide.sale_order.name' in fuente
