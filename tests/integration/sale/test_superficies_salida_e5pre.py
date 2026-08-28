"""Tests — E5-pre: las superficies de salida leen el canónico.

Cierra H-API-34 (desglose de montos anclado al canónico). Con E1-bis los
importes son líneas y con E4 son agregables; aquí la superficie de
desglose (``order_amounts``) deja de leer columnas de cabecera de un
espejo — hoy no hay ningún espejo del que leer.

Lo que se fija:

1. **El contrato no cambia** — las cinco claves siguen siendo
   ``subtotal``/``tax``/``shipping_cost``/``discount``/``total``, así que el UI
   no se toca.
2. **La fuente es el canónico** — los valores se componen de las líneas de
   ``SaleOrder``, y cada término lo aporta su addon (``delivery`` el envío,
   ``sale_loyalty`` el descuento).
3. **El envío entra a la base gravable (H-API-41)** — el IVA se extrae por
   línea (``SaleOrderLine.price_tax``), así que la línea de envío también
   tributa: agregar el envío incrementa ``amount_tax``. (Origen histórico:
   el espejo, ya retirado junto con el addon ``orders`` — SOL-098,
   ``api@77bd1f0`` —, excluía el envío de su base; esa comparación entre
   dos fuentes ya no es posible ni necesaria, sólo queda un origen.)
4. **Degradación** — sin una venta que renderizar (``sale_order=None``,
   p. ej. una referencia aún sin resolver) la superficie devuelve ceros en
   vez de romper.

**Sección retirada (post-V5d/SOL-098):** la versión original de este
módulo incluía ``TestElPayloadDelPedido``, que verificaba que un
``OrderSerializer`` (del addon espejo ``orders``, ya retirado) expusiera el
desglose del canónico. Esa clase se eliminó: el serializer no existe en
ningún addon vigente (``grep -rn "class OrderSerializer" src/`` → vacío),
así que su sujeto desapareció junto con el espejo.
"""
from decimal import Decimal
from uuid import uuid4

import pytest

from addons.delivery.models import ShippingMethod
from addons.delivery.models.sale_order import set_delivery_line
from addons.loyalty.models import Voucher
from addons.sale.amounts import order_amounts
from addons.sale.models import SaleOrder
from addons.sale_loyalty.services import apply_voucher_to_draft
from addons.sale.services import (
    add_item_to_draft, confirm_draft_order,
)
from addons.sale_loyalty.models.sale_order import set_reward_line
from django.utils import timezone
from tests.factories.product_factory import make_category, make_product

pytestmark = pytest.mark.django_db

ADDR = {
    'recipient_name': 'E5pre', 'street': 'Calle 3', 'city': 'CDMX',
    'state': 'CDMX', 'zip_code': '01000',
}


@pytest.fixture
def producto():
    cat = make_category(name='Cat S')
    return make_product(name='Prod S', price=Decimal('100.00'), stock=9, categ=cat)


@pytest.fixture
def metodo():
    return ShippingMethod.objects.create(
        name='Estándar S', cost=Decimal('99.00'), estimated_days=3)


def _venta(producto, metodo, shipping=Decimal('99.00'), voucher=None):
    """Confirma una venta con envío (y cupón opcional) y la retorna.

    No hay una segunda entidad que devolver: ``confirm_draft_order``
    confirma el mismo ``SaleOrder`` que recibe.
    """
    draft = SaleOrder.objects.create(
        state=SaleOrder.STATE_DRAFT, cart_token=uuid4(), carrier=metodo)
    add_item_to_draft(draft, producto, quantity=1)
    if voucher is not None:
        apply_voucher_to_draft(draft, voucher.code)
    set_delivery_line(draft, shipping)
    set_reward_line(draft)
    confirm_draft_order(draft, address_data=dict(ADDR),
                        guest_email='s@test.mx', shipping_cost=shipping)
    draft.refresh_from_db()
    return draft


class TestContratoEstable:

    def test_las_cinco_claves_siguen_siendo_las_mismas(self, producto, metodo):
        venta = _venta(producto, metodo)
        assert set(order_amounts(venta)) == {
            'subtotal', 'tax', 'shipping_cost', 'discount', 'total'}

    def test_el_desglose_sale_de_las_lineas(self, producto, metodo):
        venta = _venta(producto, metodo)
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
        venta = _venta(producto, metodo, voucher=voucher)
        a = order_amounts(venta)
        assert a['discount'] == Decimal('20.00')     # la línea es -20.00
        assert a['subtotal'] == Decimal('100.00')    # producto bruto
        assert a['total'] == Decimal('179.00')


class TestElIvaIncluyeElEnvioEnSuBase:
    """H-API-41 — el IVA se extrae por línea, así que la de envío también
    tributa.

    Origen histórico: el espejo (ya retirado, SOL-098) calculaba el
    impuesto sobre ``subtotal - discount`` sin el envío. Al no existir ya
    una segunda fuente que comparar, el invariante se fija de forma
    autocontenida: agregar la línea de envío a una venta sólo-producto
    debe aumentar el IVA calculado.
    """

    def test_agregar_el_envio_aumenta_el_iva_de_la_venta(
            self, producto, metodo):
        draft = SaleOrder.objects.create(
            state=SaleOrder.STATE_DRAFT, cart_token=uuid4(), carrier=metodo)
        add_item_to_draft(draft, producto, quantity=1)
        iva_solo_producto = draft.amount_tax

        set_delivery_line(draft, metodo.cost)
        draft.refresh_from_db()

        assert draft.amount_tax > iva_solo_producto
        # Y equivale al IVA de la venta completa, no sólo del producto.
        assert order_amounts(draft)['tax'] == draft.amount_tax


class TestDegradation:

    def test_sin_venta_que_renderizar_devuelve_ceros(self):
        a = order_amounts(None)
        assert a['total'] == Decimal('0.00')
        assert set(a) == {'subtotal', 'tax', 'shipping_cost', 'discount',
                          'total'}
