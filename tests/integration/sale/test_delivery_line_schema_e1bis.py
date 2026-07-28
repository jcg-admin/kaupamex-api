"""Tests — E1-bis rebanada 1: esquema de la línea de envío/descuento.

Cierra el prerequisito de H-API-24 (``ShippingMethod`` sin FK a producto) y
prepara H-API-30 (montos que no son de producto sin camino al canónico).

Contrato de la rebanada:

1. ``ShippingMethod.product`` existe y es **opcional** — un método sin
   producto sigue cotizando; sólo no puede facturarse como concepto. Es la
   divergencia deliberada con Odoo (``delivery.carrier.product_id`` es
   ``required=True``): aquí el comprador ya no elige transportista
   (``update_shipping_method`` DEPRECADO 2026-07-07), así que exigir el
   producto rompería métodos vigentes sin ganar nada.
2. ``ensure_service_product()`` siembra el producto de forma idempotente, con
   ``is_published=False`` (≙ ``sale_ok=False`` de la semilla Odoo): fuera del
   storefront, pero dato maestro editable.
3. ``SaleOrderLine`` acepta los marcadores ``is_delivery``/``is_reward``, y una
   línea marcada **entra a los totales como cualquier otra** — son marcadores,
   no un tipo de línea aparte.
"""
from decimal import Decimal
from uuid import uuid4

import pytest

from addons.catalogue.models import Category, Product
from addons.delivery.models import ShippingMethod
from addons.sale.models import SaleOrder, SaleOrderLine

pytestmark = pytest.mark.django_db


@pytest.fixture
def metodo():
    return ShippingMethod.objects.create(
        name='Estándar', cost=Decimal('99.00'), estimated_days=3)


@pytest.fixture
def producto():
    cat = Category.objects.create(name='Cat E1bis', slug='cat-e1bis', is_active=True)
    prod = Product.objects.create(
        name='Prod E1bis', slug='prod-e1bis', sku='SKU-E1BIS',
        price=Decimal('100.00'), stock=5, is_active=True, is_published=True)
    prod.categories.add(cat)
    return prod


class TestFKOpcionalAProducto:

    def test_el_metodo_nace_sin_producto(self, metodo):
        assert metodo.product_id is None

    def test_un_metodo_sin_producto_sigue_siendo_valido(self, metodo):
        """La divergencia con Odoo: la FK es opcional, no required."""
        metodo.full_clean()
        assert ShippingMethod.objects.filter(pk=metodo.pk).exists()


class TestSembradoDelProductoDeServicio:

    def test_siembra_el_producto_y_lo_ancla(self, metodo):
        producto = metodo.ensure_service_product()
        metodo.refresh_from_db()
        assert metodo.product_id == producto.pk
        assert producto.sku == f'{ShippingMethod.SERVICE_SKU_PREFIX}{metodo.pk}'

    def test_es_idempotente(self, metodo):
        primero = metodo.ensure_service_product()
        segundo = metodo.ensure_service_product()
        assert primero.pk == segundo.pk
        assert Product.objects.filter(sku=primero.sku).count() == 1

    def test_queda_fuera_del_storefront(self, metodo):
        """``is_published=False`` ≙ ``sale_ok=False`` de la semilla Odoo."""
        producto = metodo.ensure_service_product()
        assert producto.is_published is False
        assert producto.is_active is True


class TestMarcadoresDeLinea:

    def test_una_linea_normal_no_esta_marcada(self, producto):
        venta = SaleOrder.objects.create(
            state=SaleOrder.STATE_DRAFT, cart_token=uuid4())
        linea = SaleOrderLine.objects.create(
            order=venta, product=producto, name=producto.name,
            product_uom_qty=1, price_unit=producto.price)
        assert linea.is_delivery is False
        assert linea.is_reward is False

    def test_la_linea_de_envio_suma_al_total(self, producto, metodo):
        """El punto de todo E1-bis: el envío deja de ser un escalar invisible
        para ``amount_total()`` y pasa a sumar como línea."""
        venta = SaleOrder.objects.create(
            state=SaleOrder.STATE_DRAFT, cart_token=uuid4())
        SaleOrderLine.objects.create(
            order=venta, product=producto, name=producto.name,
            product_uom_qty=1, price_unit=Decimal('100.00'))
        assert venta.amount_total() == Decimal('100.00')

        SaleOrderLine.objects.create(
            order=venta, product=metodo.ensure_service_product(),
            name=f'Envío — {metodo.name}', product_uom_qty=1,
            price_unit=metodo.cost, is_delivery=True)
        assert venta.amount_total() == Decimal('199.00')

    def test_la_linea_de_recompensa_resta_del_total(self, producto):
        """Simetría envío/descuento (decisión ejecutor 2026-07-28): la
        recompensa es una línea de precio negativo, mismo mecanismo."""
        venta = SaleOrder.objects.create(
            state=SaleOrder.STATE_DRAFT, cart_token=uuid4())
        SaleOrderLine.objects.create(
            order=venta, product=producto, name=producto.name,
            product_uom_qty=1, price_unit=Decimal('100.00'))
        SaleOrderLine.objects.create(
            order=venta, product=producto, name='Descuento cupón',
            product_uom_qty=1, price_unit=Decimal('-20.00'), is_reward=True)
        assert venta.amount_total() == Decimal('80.00')
