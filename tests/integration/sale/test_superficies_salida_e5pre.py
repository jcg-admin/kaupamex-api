"""Tests — E5-pre: las superficies de salida leen el canónico.

Cierra H-API-34 (recibo PDF y payload del pedido anclados al espejo). Con
E1-bis los importes son líneas y con E4 son agregables; aquí las **dos
superficies que ve el comprador** dejan de leer las columnas de cabecera de
``OrderValue``.

Lo que se fija:

1. **El contrato no cambia** — las cinco claves siguen siendo
   ``subtotal``/``tax``/``shipping_cost``/``discount``/``total``, así que el UI
   no se toca.
2. **La fuente sí** — los valores se componen de las líneas del canónico, y
   cada término lo aporta su addon (``delivery`` el envío, ``sale_loyalty`` el
   descuento).
3. **Divergencia deliberada del IVA (H-API-41)** — el espejo calculaba el
   impuesto excluyendo el envío de la base; el canónico lo incluye. El
   **total es idéntico**; sólo se reparte distinto. Se fija con un test que
   compara ambos, para que la divergencia sea una decisión visible y no un
   drift silencioso.
4. **Degradación** — un espejo sin ``sale_order`` (huérfano del histórico)
   devuelve ceros en vez de romper la superficie.
"""
from decimal import Decimal
from uuid import uuid4

import pytest

from addons.catalogue.models import Category, Product
from addons.delivery.models import ShippingMethod
from addons.delivery.models.sale_order import set_delivery_line
from addons.loyalty.models import Voucher
from addons.sale.amounts import order_amounts
from addons.orders.models import Order, OrderValue
from addons.orders.serializers import OrderSerializer
from addons.sale.models import SaleOrder
from addons.sale_loyalty.services import apply_voucher_to_draft
from addons.sale.services import (
    add_item_to_draft, confirm_draft_order,
)
from addons.sale_loyalty.models.sale_order import set_reward_line
from django.utils import timezone

pytestmark = pytest.mark.django_db

ADDR = {
    'recipient_name': 'E5pre', 'street': 'Calle 3', 'city': 'CDMX',
    'state': 'CDMX', 'zip_code': '01000',
}


@pytest.fixture
def producto():
    cat = Category.objects.create(name='Cat S', slug='cat-s', is_active=True)
    prod = Product.objects.create(
        name='Prod S', slug='prod-s', sku='SKU-S',
        price=Decimal('100.00'), stock=9, is_active=True, is_published=True)
    prod.categories.add(cat)
    return prod


@pytest.fixture
def metodo():
    return ShippingMethod.objects.create(
        name='Estándar S', cost=Decimal('99.00'), estimated_days=3)


def _venta(producto, metodo, shipping=Decimal('99.00'), voucher=None):
    draft = SaleOrder.objects.create(
        state=SaleOrder.STATE_DRAFT, cart_token=uuid4(), carrier=metodo)
    add_item_to_draft(draft, producto, quantity=1)
    if voucher is not None:
        apply_voucher_to_draft(draft, voucher.code)
    set_delivery_line(draft, shipping)
    set_reward_line(draft)
    legacy = confirm_draft_order(draft, address_data=dict(ADDR),
                                 guest_email='s@test.mx',
                                 shipping_cost=shipping)
    draft.refresh_from_db()
    return draft, legacy


class TestContratoEstable:

    def test_las_cinco_claves_siguen_siendo_las_mismas(self, producto, metodo):
        venta, _ = _venta(producto, metodo)
        assert set(order_amounts(venta)) == {
            'subtotal', 'tax', 'shipping_cost', 'discount', 'total'}

    def test_el_desglose_sale_de_las_lineas(self, producto, metodo):
        venta, _ = _venta(producto, metodo)
        a = order_amounts(venta)
        assert a['shipping_cost'] == Decimal('99.00')
        assert a['subtotal'] == Decimal('100.00')
        assert a['total'] == Decimal('199.00')
        assert a['total'] == venta.amount_total

    def test_el_descuento_se_presenta_en_positivo(self, producto, metodo):
        voucher = Voucher.objects.create(
            code='E5PRE20', voucher_type=Voucher.TYPE_FIXED,
            discount_value=Decimal('20.00'), is_active=True,
            valid_from=timezone.now())
        venta, _ = _venta(producto, metodo, voucher=voucher)
        a = order_amounts(venta)
        assert a['discount'] == Decimal('20.00')     # la línea es -20.00
        assert a['subtotal'] == Decimal('100.00')    # producto bruto
        assert a['total'] == Decimal('179.00')


class TestDivergenciaDeliberadaDelIva:
    """H-API-41 — el espejo excluía el envío de la base gravable.

    ``confirm_draft_order`` calculaba ``tax`` sobre ``subtotal - discount``
    (``sale/services.py:377``); el canónico extrae el IVA por línea, así que la
    línea de envío también tributa. El comprador paga lo mismo.
    """

    def test_el_total_es_identico_en_ambas_fuentes(self, producto, metodo):
        venta, legacy = _venta(producto, metodo)
        espejo = OrderValue.objects.get(order=legacy)
        assert order_amounts(venta)['total'] == espejo.total

    def test_el_iva_canonico_grava_tambien_el_envio(self, producto, metodo):
        venta, legacy = _venta(producto, metodo)
        espejo = OrderValue.objects.get(order=legacy)
        canonico = order_amounts(venta)['tax']
        # El envío entra a la base, así que el impuesto extraído es mayor.
        assert canonico > espejo.tax
        # Y equivale al IVA de la venta completa, no sólo del producto.
        assert canonico == venta.amount_tax


class TestDegradacion:

    def test_espejo_sin_canonico_devuelve_ceros(self):
        a = order_amounts(None)
        assert a['total'] == Decimal('0.00')
        assert set(a) == {'subtotal', 'tax', 'shipping_cost', 'discount',
                          'total'}


class TestElPayloadDelPedido:
    """El serializer expone el desglose del canónico con el contrato intacto."""

    def test_el_serializer_lee_del_canonico(self, producto, metodo):
        venta, legacy = _venta(producto, metodo)
        data = OrderSerializer(Order.objects.get(pk=legacy.pk)).data
        assert Decimal(str(data['value']['total'])) == venta.amount_total
        assert Decimal(str(data['value']['shipping_cost'])) == Decimal('99.00')
