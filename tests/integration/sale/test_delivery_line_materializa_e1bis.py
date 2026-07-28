"""Tests — E1-bis rebanada 2: materialización de la línea en el checkout.

Cierra H-API-24 y H-API-30: los importes que no son de producto dejan de ser
escalares invisibles y entran a ``order_line``, así que ``amount_total()`` del
canónico los recoge.

**Dirección de dependencia** (corrección estructural, ejecutor 2026-07-28): la
materialización NO vive en ``sale``. ``delivery`` → ``sale`` y ``sale_loyalty``
→ ``sale``, nunca al revés; cada addon contribuye su línea desde su propio
módulo (``<addon>/models/sale_order.py``, fiel al ``_inherit='sale.order'`` de
Odoo). El llamador —el checkout, que es quien conoce el envío y el cupón—
materializa sobre el **draft** antes de confirmar; es el mismo orden de Odoo:
la línea se agrega a la cotización y luego la orden se confirma.

Invariantes que fijan el contrato:

1. Una venta con envío nace con su línea ``is_delivery``, y el total canónico
   la incluye.
2. El descuento del cupón nace como línea ``is_reward`` de precio negativo, con
   el importe calculado **del cupón**, no recibido del llamador.
3. **El espejo no se contamina**: sus ``OrderItem`` siguen siendo sólo de
   producto (el puente itera la lista capturada antes de materializar), y su
   ``OrderValue`` conserva los escalares. No hay doble conteo — son dos
   modelos distintos.
4. Mecanismo A (borrar+recrear) es idempotente: re-materializar deja una sola
   línea. El Mecanismo B de Odoo (reescritura in-place bajo flag de contexto)
   no se porta.
5. El transportista es **opcional**: sin ``carrier`` la línea se crea igual,
   con el producto de servicio genérico. Lo que decide si hay línea es el
   importe. (La versión original degradaba aquí; corregido en E5-pre,
   H-API-42, al descubrir que ésa es la ruta real de producción.)
6. La base del descuento es el subtotal de **producto**: el orden en que se
   materializan las dos líneas no altera el importe.
"""
from decimal import Decimal
from uuid import uuid4

import pytest
from django.utils import timezone

from addons.catalogue.models import Category, Product
from addons.delivery.models import ShippingMethod
from addons.delivery.models.sale_order import set_delivery_line
from addons.loyalty.models import Voucher
from addons.orders.models import OrderItem, OrderValue
from addons.sale.models import SaleOrder
from addons.sale.services import (
    add_item_to_draft,
    apply_voucher_to_draft,
    confirm_draft_order,
)
from addons.sale_loyalty.models.sale_order import set_reward_line
from addons.sale_loyalty.models.sale_order_coupon import REWARD_SKU

pytestmark = pytest.mark.django_db

ADDR = {
    'recipient_name': 'E1bis', 'street': 'Calle 2', 'city': 'CDMX',
    'state': 'CDMX', 'zip_code': '01000',
}


@pytest.fixture
def producto():
    cat = Category.objects.create(name='Cat M', slug='cat-m', is_active=True)
    prod = Product.objects.create(
        name='Prod M', slug='prod-m', sku='SKU-M',
        price=Decimal('100.00'), stock=9, is_active=True, is_published=True)
    prod.categories.add(cat)
    return prod


@pytest.fixture
def metodo():
    return ShippingMethod.objects.create(
        name='Estándar', cost=Decimal('99.00'), estimated_days=3)


@pytest.fixture
def voucher_20():
    return Voucher.objects.create(
        code='E1BIS20', voucher_type=Voucher.TYPE_FIXED,
        discount_value=Decimal('20.00'), is_active=True,
        valid_from=timezone.now())


def _draft(producto, carrier=None):
    draft = SaleOrder.objects.create(
        state=SaleOrder.STATE_DRAFT, cart_token=uuid4(), carrier=carrier)
    add_item_to_draft(draft, producto, quantity=1)
    return draft


def _checkout(draft, shipping_cost=Decimal('0.00')):
    """Reproduce el orden del checkout real: materializar, luego confirmar."""
    set_delivery_line(draft, shipping_cost)
    set_reward_line(draft)
    return confirm_draft_order(draft, address_data=dict(ADDR),
                               guest_email='m@test.mx',
                               shipping_cost=shipping_cost)


class TestLineaDeEnvio:

    def test_la_venta_nace_con_su_linea_de_envio(self, producto, metodo):
        draft = _draft(producto, carrier=metodo)
        _checkout(draft, Decimal('99.00'))
        draft.refresh_from_db()
        envio = draft.order_line.filter(is_delivery=True)
        assert envio.count() == 1
        assert envio.first().price_unit == Decimal('99.00')

    def test_el_total_canonico_incluye_el_envio(self, producto, metodo):
        """El punto de H-API-30: antes ``amount_total()`` lo excluía."""
        draft = _draft(producto, carrier=metodo)
        _checkout(draft, Decimal('99.00'))
        draft.refresh_from_db()
        assert draft.amount_total() == Decimal('199.00')

    def test_la_linea_apunta_al_producto_de_servicio_del_metodo(
            self, producto, metodo):
        draft = _draft(producto, carrier=metodo)
        set_delivery_line(draft, Decimal('99.00'))
        linea = draft.order_line.get(is_delivery=True)
        assert linea.product.sku == f'{ShippingMethod.SERVICE_SKU_PREFIX}{metodo.pk}'

    def test_sin_carrier_tambien_hay_linea_con_producto_generico(
            self, producto):
        """Corregido en E5-pre (H-API-42) — antes esto era una degradación.

        La versión original de E1-bis omitía la línea cuando la orden no traía
        ``carrier``, y dejaba el importe sólo en el escalar del espejo. Parecía
        aceptable mientras las superficies leían el espejo; al re-anclarlas al
        canónico resultó ser **la ruta real** —el envío se deriva por zona y la
        orden no lleva transportista— así que el comprador habría visto envío
        en cero. Lo que decide si hay línea es el importe, no el transportista.
        """
        draft = _draft(producto, carrier=None)
        legacy = _checkout(draft, Decimal('50.00'))
        draft.refresh_from_db()
        linea = draft.order_line.get(is_delivery=True)
        assert linea.price_unit == Decimal('50.00')
        assert linea.product.sku == 'SRV-ENVIO'     # producto genérico
        assert linea.name == 'Envío'
        # El espejo conserva su escalar; los dos totales siguen coincidiendo.
        assert OrderValue.objects.get(order=legacy).shipping_cost == Decimal('50.00')
        assert draft.amount_total() == Decimal('150.00')


class TestLineaDeRecompensa:

    def test_el_descuento_nace_como_linea_negativa(
            self, producto, metodo, voucher_20):
        draft = _draft(producto, carrier=metodo)
        apply_voucher_to_draft(draft, voucher_20.code)
        set_reward_line(draft)
        linea = draft.order_line.get(is_reward=True)
        assert linea.price_unit == Decimal('-20.00')
        assert linea.product.sku == REWARD_SKU

    def test_resta_del_total_canonico(self, producto, metodo, voucher_20):
        draft = _draft(producto, carrier=metodo)
        assert draft.amount_total() == Decimal('100.00')
        apply_voucher_to_draft(draft, voucher_20.code)
        set_reward_line(draft)
        assert draft.amount_total() == Decimal('80.00')

    def test_sin_cupon_no_hay_linea(self, producto, metodo):
        draft = _draft(producto, carrier=metodo)
        assert set_reward_line(draft) is None
        assert draft.order_line.filter(is_reward=True).count() == 0

    def test_el_importe_no_lo_dicta_el_llamador(
            self, producto, metodo, voucher_20):
        """``set_reward_line`` no recibe monto: lo calcula del cupón, así que
        el llamador no puede desincronizarse de la regla de descuento."""
        draft = _draft(producto, carrier=metodo)
        apply_voucher_to_draft(draft, voucher_20.code)
        set_reward_line(draft)
        assert draft.order_line.get(is_reward=True).price_unit == Decimal('-20.00')


class TestMecanismoABorrarYRecrear:
    """Odoo nunca actualiza la línea in-place; la borra y la recrea."""

    def test_re_materializar_deja_una_sola_linea(self, producto, metodo):
        draft = _draft(producto, carrier=metodo)
        set_delivery_line(draft, Decimal('99.00'))
        set_delivery_line(draft, Decimal('149.00'))
        lineas = draft.order_line.filter(is_delivery=True)
        assert lineas.count() == 1
        assert lineas.first().price_unit == Decimal('149.00')

    def test_importe_cero_borra_la_linea(self, producto, metodo):
        draft = _draft(producto, carrier=metodo)
        set_delivery_line(draft, Decimal('99.00'))
        assert draft.order_line.filter(is_delivery=True).count() == 1
        set_delivery_line(draft, Decimal('0.00'))
        assert draft.order_line.filter(is_delivery=True).count() == 0

    def test_re_materializar_la_recompensa_deja_una_sola_linea(
            self, producto, metodo, voucher_20):
        draft = _draft(producto, carrier=metodo)
        apply_voucher_to_draft(draft, voucher_20.code)
        set_reward_line(draft)
        set_reward_line(draft)
        assert draft.order_line.filter(is_reward=True).count() == 1


class TestBaseDelDescuento:
    """El descuento es sobre producto: el orden de materialización no lo mueve."""

    def test_el_envio_no_entra_en_la_base_del_descuento(
            self, producto, metodo, voucher_20):
        draft = _draft(producto, carrier=metodo)
        apply_voucher_to_draft(draft, voucher_20.code)
        set_delivery_line(draft, Decimal('99.00'))
        set_reward_line(draft)
        assert draft.order_line.get(is_reward=True).price_unit == Decimal('-20.00')
        assert draft.amount_total() == Decimal('179.00')

    def test_el_orden_inverso_da_el_mismo_total(
            self, producto, metodo, voucher_20):
        draft = _draft(producto, carrier=metodo)
        apply_voucher_to_draft(draft, voucher_20.code)
        set_reward_line(draft)
        set_delivery_line(draft, Decimal('99.00'))
        assert draft.amount_total() == Decimal('179.00')


class TestElEspejoNoSeContamina:
    """El contrato del espejo queda intacto: sus OrderItem son de producto."""

    def test_los_orderitem_siguen_siendo_solo_de_producto(
            self, producto, metodo):
        draft = _draft(producto, carrier=metodo)
        legacy = _checkout(draft, Decimal('99.00'))
        items = OrderItem.objects.filter(order=legacy)
        assert items.count() == 1
        assert items.first().product_id == producto.pk

    def test_los_dos_totales_coinciden_sin_doble_conteo(
            self, producto, metodo):
        draft = _draft(producto, carrier=metodo)
        legacy = _checkout(draft, Decimal('99.00'))
        draft.refresh_from_db()
        valor = OrderValue.objects.get(order=legacy)
        assert valor.total == draft.amount_total() == Decimal('199.00')


class TestVoucherEndToEnd:

    def test_checkout_con_voucher_materializa_ambas_lineas(
            self, producto, metodo, voucher_20):
        draft = _draft(producto, carrier=metodo)
        apply_voucher_to_draft(draft, voucher_20.code)
        legacy = _checkout(draft, Decimal('99.00'))
        draft.refresh_from_db()
        assert draft.order_line.filter(is_delivery=True).count() == 1
        assert draft.order_line.filter(is_reward=True).count() == 1
        valor = OrderValue.objects.get(order=legacy)
        assert valor.total == draft.amount_total()
