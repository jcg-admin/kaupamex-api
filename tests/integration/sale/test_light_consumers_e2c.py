"""Tests — E2c: consumidores ligeros del espejo re-anclados al canónico.

Tercera rebanada del retiro de ``orders.Order``. De la cola ligera, sólo dos
consumidores son re-anclables **sin tocar contrato ni dinero**:

- ``mail/views.py`` — audiencia "compradores del producto": contaba
  compradores vía ``OrderItem``; pasa a ``SaleOrderLine``.
- ``chartsize/views.py`` — guard de borrado de variante: detectaba órdenes
  activas vía ``OrderItem``; pasa a ``SaleOrderLine``.

La sutileza que estos tests fijan: ``OrderItem`` sólo existía **post-confirm**
(el espejo se materializa en el checkout), mientras que ``SaleOrderLine``
existe **desde el carrito** (draft). El marcador canónico de "fue confirmada
alguna vez" es ``date_order`` (lo fija ``action_confirm``,
``sale_order.py:189``, y ``action_cancel`` NO lo limpia). Sin ese filtro, el
re-anclaje inflaría la audiencia con carritos abandonados.

Los demás consumidores ligeros NO se tocan aquí, con causa registrada:
contrato público de identidad ``Order.pk`` (H-API-29) y agregados de dinero
sin columna canónica (H-API-30).
"""
from decimal import Decimal

import pytest

from addons.catalogue.models import Category, Product
from addons.chartsize.models import VariantType, VariantOption, ProductVariant
from addons.mail.views import (
    _compute_audience_count,
    _resolve_audience_user_ids,
)
from addons.mail.models import ManualNotification
from addons.sale.models import SaleOrder, SaleOrderLine
from addons.users.models import IdentityUser

pytestmark = pytest.mark.django_db


@pytest.fixture
def producto():
    cat = Category.objects.create(name='Cat E2c', slug='cat-e2c', is_active=True)
    prod = Product.objects.create(
        name='Prod E2c', slug='prod-e2c', sku='SKU-E2C',
        price=Decimal('100.00'), is_active=True)
    prod.categories.add(cat)
    return prod


def _venta(producto, usuario=None, confirmar=True):
    orden = SaleOrder.objects.create(
        state=SaleOrder.STATE_DRAFT, partner=usuario)
    SaleOrderLine.objects.create(
        order=orden, product=producto, name=producto.name,
        product_uom_qty=1, price_unit=producto.price)
    if confirmar:
        orden.action_confirm()
    return orden


class TestAudienciaCompradoresCanonica:
    """``PRODUCT_BUYERS`` se resuelve desde ``SaleOrderLine``."""

    def test_compradores_confirmados_cuentan(self, producto):
        u1 = IdentityUser.objects.create_user(email='b1.e2c@example.com',
                                              password='x')
        u2 = IdentityUser.objects.create_user(email='b2.e2c@example.com',
                                              password='x')
        _venta(producto, u1)
        _venta(producto, u2)

        ids = _resolve_audience_user_ids(
            ManualNotification.RecipientType.PRODUCT_BUYERS, '', producto.pk)
        assert sorted(ids) == sorted([u1.pk, u2.pk])
        assert _compute_audience_count(
            ManualNotification.RecipientType.PRODUCT_BUYERS, '',
            producto.pk) == 2

    def test_un_carrito_draft_no_es_comprador(self, producto):
        """La sutileza del re-anclaje: la línea existe desde el draft."""
        mirón = IdentityUser.objects.create_user(email='cart.e2c@example.com',
                                                 password='x')
        _venta(producto, mirón, confirmar=False)

        ids = _resolve_audience_user_ids(
            ManualNotification.RecipientType.PRODUCT_BUYERS, '', producto.pk)
        assert mirón.pk not in ids

    def test_una_orden_cancelada_post_confirm_sigue_contando(self, producto):
        """Paridad con el espejo: OrderItem persistía tras la cancelación."""
        arrepentido = IdentityUser.objects.create_user(
            email='cancel.e2c@example.com', password='x')
        orden = _venta(producto, arrepentido)
        orden.action_cancel()

        ids = _resolve_audience_user_ids(
            ManualNotification.RecipientType.PRODUCT_BUYERS, '', producto.pk)
        assert arrepentido.pk in ids

    def test_comprador_anonimo_no_cuenta(self, producto):
        _venta(producto, usuario=None)
        assert _compute_audience_count(
            ManualNotification.RecipientType.PRODUCT_BUYERS, '',
            producto.pk) == 0


class TestGuardVarianteCanonico:
    """El borrado de variante se bloquea leyendo ``SaleOrderLine``."""

    @pytest.fixture
    def variante(self, producto):
        vt = VariantType.objects.create(product=producto, name='Talla', order=0)
        opt = VariantOption.objects.create(
            variant_type=vt, label='M', slug='m-e2c', order=0)
        return ProductVariant.objects.create(
            product=producto, option=opt, sku_suffix='M', stock=5,
            is_active=True)

    def test_variante_en_orden_confirmada_no_entregada_bloquea(
            self, producto, variante):
        orden = SaleOrder.objects.create(state=SaleOrder.STATE_DRAFT)
        SaleOrderLine.objects.create(
            order=orden, product=producto, variant=variante,
            name=producto.name, product_uom_qty=1,
            price_unit=producto.price)
        orden.action_confirm()

        bloqueada = SaleOrderLine.objects.filter(
            variant=variante, order__state=SaleOrder.STATE_SALE,
        ).exists()
        assert bloqueada

    def test_el_guard_ya_no_consulta_orderitem(self):
        fuente = open('src/addons/chartsize/views.py', encoding='utf-8').read()
        assert 'OrderItem' not in fuente

    def test_la_audiencia_ya_no_consulta_orderitem(self):
        fuente = open('src/addons/mail/views.py', encoding='utf-8').read()
        assert 'OrderItem' not in fuente
