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

**Retiro parcial (H-API, este pase):** ``TestGuardVarianteCanonico`` probaba
el guard de borrado de ``chartsize.ProductVariant`` — la familia
``chartsize`` se disolvió por completo (el eje ``variant`` desapareció:
``product.ProductProduct`` **es** la variante, H-API-213) y
``src/addons/chartsize/views.py`` no existe (verificado:
``find src/addons/chartsize`` → vacío). Ni el modelo, ni el archivo que el
candado leía, sobreviven. Se retira la clase; ``TestAudienciaCompradoresCanonica``
(el otro consumidor, sin dependencia de chartsize) se conserva.
"""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from addons.mail.controllers.main import (
    _compute_audience_count,
    _resolve_audience_user_ids,
)
from addons.mail.models import ManualNotification
from addons.sale.models import SaleOrder, SaleOrderLine
from tests.factories.product_factory import make_category, make_product

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def producto():
    cat = make_category(name='Cat E2c')
    return make_product(name='Prod E2c', price=Decimal('100.00'), categ=cat)


def _venta(producto, usuario=None, confirmar=True):
    orden = SaleOrder.objects.create(
        state=SaleOrder.STATE_DRAFT, partner=usuario)
    SaleOrderLine.objects.create(
        order=orden, product=producto, name=producto.name,
        product_uom_qty=1, price_unit=producto.lst_price)
    if confirmar:
        orden.action_confirm()
    return orden


class TestAudienciaCompradoresCanonica:
    """``PRODUCT_BUYERS`` se resuelve desde ``SaleOrderLine``."""

    def test_compradores_confirmados_cuentan(self, producto):
        u1 = User.objects.create_user(login='b1.e2c@practicayoruba.mx',
                                      password='x')
        u2 = User.objects.create_user(login='b2.e2c@practicayoruba.mx',
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
        mirón = User.objects.create_user(login='cart.e2c@practicayoruba.mx',
                                         password='x')
        _venta(producto, mirón, confirmar=False)

        ids = _resolve_audience_user_ids(
            ManualNotification.RecipientType.PRODUCT_BUYERS, '', producto.pk)
        assert mirón.pk not in ids

    def test_una_orden_cancelada_post_confirm_sigue_contando(self, producto):
        """Paridad con el espejo: OrderItem persistía tras la cancelación."""
        arrepentido = User.objects.create_user(
            login='cancel.e2c@practicayoruba.mx', password='x')
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
