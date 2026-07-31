"""Tests — E4-pre: inversión del anclaje de los ejes (H-API-26).

Los tres modelos de eje estaban doblemente anclados con las obligatoriedades
al revés: la FK al espejo (``orders.Order``) era ``NOT NULL`` y la FK a la
canónica (``sale.SaleOrder``) era ``null=True``. Mientras eso fuera así, la
base de datos exigía una fila espejo por cada pago, guía y reseña — E5 (dar
de baja el espejo) era inejecutable por esquema, no por código.

E4-pre invierte el anclaje en los tres, con backfill previo desde
``order.sale_order`` (que es NOT NULL desde V5d, así que el backfill es
total):

- ``payment.Payment``      — ``sale_order`` NOT NULL/PROTECT · ``order`` nullable/SET_NULL
- ``delivery.ShipmentGuide`` — ídem (OneToOne)
- ``rating.Review``        — ídem

Los escritores de producción ya pasaban ambas FK (verificado:
``admin_services.py:104``, ``payments/services.py:92,515``,
``delivery/views.py:199``, ``reviews/views.py:206``), así que el flujo vivo
no cambia — cambia quién manda en el esquema.
"""
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from addons.catalogue.models import Category, Product
from addons.sale import status_projection as sp
from addons.delivery.models import Courier, ShipmentGuide
from addons.payment.models import Payment
from addons.rating.models import Review
from addons.sale.models import SaleOrder
from addons.users.models import IdentityUser

pytestmark = pytest.mark.django_db


@pytest.fixture
def venta():
    return SaleOrder.objects.create(
        state=SaleOrder.STATE_SALE, date_order=timezone.now())


class TestPagoAncladoAlCanonico:

    def test_un_pago_existe_sin_fila_espejo(self, venta):
        pago = Payment.objects.create(
            sale_order=venta, gateway=Payment.GATEWAY_MANUAL,
            status=Payment.STATUS_APPROVED, amount=Decimal('150.00'))
        pago.refresh_from_db()
        assert pago.order_id is None
        assert pago.sale_order_id == venta.pk

    def test_la_canonica_es_obligatoria(self, venta):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Payment.objects.create(
                    sale_order=None, gateway=Payment.GATEWAY_MANUAL,
                    status=Payment.STATUS_APPROVED, amount=Decimal('1.00'))

    def test_la_proyeccion_lee_el_pago_solo_canonico(self, venta):
        assert sp.derive_order_status(venta) == sp.STATUS_PENDING
        Payment.objects.create(
            sale_order=venta, gateway=Payment.GATEWAY_MANUAL,
            status=Payment.STATUS_APPROVED, amount=Decimal('99.00'))
        assert sp.derive_order_status(venta) == sp.STATUS_PAID


class TestGuiaAncladaAlCanonico:

    def test_una_guia_existe_sin_fila_espejo(self, venta):
        courier = Courier.objects.create(name='DHL E4', code='DHL-E4')
        guia = ShipmentGuide.objects.create(
            sale_order=venta, courier=courier, tracking_number='TRK-E4PRE-1')
        guia.refresh_from_db()
        assert guia.order_id is None
        assert guia.sale_order_id == venta.pk

    def test_la_proyeccion_deriva_shipped_de_la_guia_canonica(self, venta):
        courier = Courier.objects.create(name='FDX E4', code='FDX-E4')
        ShipmentGuide.objects.create(
            sale_order=venta, courier=courier, tracking_number='TRK-E4PRE-2')
        venta.refresh_from_db()
        assert sp.derive_order_status(venta) == sp.STATUS_SHIPPED


class TestResenaAncladaAlCanonico:

    def test_una_resena_prueba_la_compra_con_la_canonica(self, venta):
        usuario = IdentityUser.objects.create_user(
            email='rev.e4pre@example.com', password='x')
        cat = Category.objects.create(
            name='Cat E4pre', slug='cat-e4pre', is_active=True)
        prod = Product.objects.create(
            name='Prod E4pre', slug='prod-e4pre', sku='SKU-E4PRE',
            price=Decimal('50.00'), is_active=True)
        prod.categories.add(cat)

        resena = Review.objects.create(
            user=usuario, product=prod, sale_order=venta,
            rating=5, title='Excelente', body='Prueba E4-pre')
        resena.refresh_from_db()
        assert resena.order_id is None
        assert resena.sale_order_id == venta.pk
