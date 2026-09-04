"""``StockWarehouseOrderpoint._get_replenishment_multiple_alternative``.

Fiel a ``odoo19c: purchase_stock/models/stock.py:304-320`` (``odoo-tools``,
LGPL-3). El múltiplo de reabastecimiento cuando nadie lo fijó a mano, y sólo
cuando el punto de pedido resuelve por una ruta de compra:

- si la ruta efectiva no tiene ninguna regla ``action='buy'`` — se relega en
  la implementación previa (``addons/stock/models/stock_orderpoint.py``, que
  siempre devuelve ``False``);
- si el punto de pedido ya tiene un proveedor fijado a mano
  (``supplier_id``) — se usa **ese**, sin pasar por ``_select_seller``;
- si no, se resuelve con ``_select_seller`` usando la cantidad pedida.

Cada caso discrimina contra la rama vecina: el que prueba la ruta de compra
usa un proveedor de UOM distinta a la del producto (para que devolver
``self.product_uom`` por error se note); el que prueba el proveedor fijado a
mano lo enfrenta a un proveedor más barato que ganaría por precio si el
código ignorara ``supplier_id`` y llamara a ``_select_seller`` de todas
formas.
"""
from decimal import Decimal

import pytest

from addons.base.models import ResCompany, ResPartner
from addons.product.models import ProductSupplierinfo
from addons.stock.models import (
    StockLocation,
    StockRoute,
    StockRule,
    StockWarehouse,
    StockWarehouseOrderpoint,
)
from addons.uom.models.uom_uom import Uom
from orm.environments import set_current_company
from tests.factories.product_factory import make_product

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def company(db):
    company_rec = ResCompany.objects.create(code='test_rma', name='Test RMA')
    set_current_company(company_rec.pk)
    yield company_rec
    set_current_company(None)


@pytest.fixture
def warehouse(company):
    view = StockLocation.objects.create(
        name='WH', usage=StockLocation.USAGE_VIEW, company=company,
        barcode='RMA-VIEW')
    stock = StockLocation.objects.create(
        name='WH/Stock', usage=StockLocation.USAGE_INTERNAL,
        location=view, company=company, barcode='RMA-STOCK')
    return StockWarehouse.objects.create(
        name='Main', code='WHR', company=company,
        view_location=view, lot_stock=stock)


def _orderpoint(company, wh, product, **kwargs):
    kwargs.setdefault('product', product)
    kwargs.setdefault('company', company)
    kwargs.setdefault('warehouse', wh)
    kwargs.setdefault('location', wh.lot_stock)
    return StockWarehouseOrderpoint.objects.create(**kwargs)


def _buy_route(dest):
    """Una ruta con una regla ``action='buy'`` — la que hace efectiva la rama
    de compra del método bajo prueba."""
    route = StockRoute.objects.create(name='Comprar')
    StockRule.objects.create(name='Comprar', action='buy', route=route,
                             location_dest=dest)
    return route


def _non_buy_route(dest):
    """Una ruta SIN ninguna regla de compra — la rama de relevo."""
    route = StockRoute.objects.create(name='Mover')
    StockRule.objects.create(name='Mover', action='pull_push', route=route,
                             location_dest=dest)
    return route


def _uom(name):
    return Uom.objects.create(name=name)


def _tariff(product, partner, uom, **kwargs):
    return ProductSupplierinfo.objects.create(
        partner=partner, product_tmpl=product.product_tmpl,
        product_uom=uom, **kwargs)


class TestReplenishmentMultipleAlternative:

    def test_relays_to_the_base_class_when_the_route_is_not_a_buy_route(
            self, company, warehouse):
        """Sin regla ``action='buy'`` en la ruta efectiva: el método se
        relega en la implementación previa, que siempre devuelve ``False``
        (``addons/stock/models/stock_orderpoint.py``).

        Con un proveedor que **sí** resolvería si la guarda de la ruta no
        existiera — si esta guarda desapareciera, el método seguiría hasta
        ``_select_seller`` y devolvería la UOM del proveedor en vez de
        ``False``. Sin esta tarifa, el caso pasaría igual aunque la guarda
        no existiera (nadie más resuelve nada) y no discriminaría nada —
        control neutralizado en
        ``scripts/evidence/neutering-replenishment-alternative-buy-route-guard-*.txt``.
        """
        product = make_product(name='Sin compra')
        would_resolve = ResPartner.objects.create(name='Resolvería si no hubiera guarda')
        _tariff(product, would_resolve, _uom('Caja de resguardo'), min_qty=1,
               price=Decimal('1.00'))
        op = _orderpoint(company, warehouse, product,
                         route=_non_buy_route(warehouse.lot_stock))
        assert op._get_replenishment_multiple_alternative(10) is False

    def test_returns_false_when_the_route_is_buy_but_nothing_resolves(
            self, company, warehouse):
        """Ruta de compra sin ningún proveedor —ni fijado a mano, ni por
        ``_select_seller``—: ``False`` explícito, no un ``None`` que dependa
        de que el relevo coincida por casualidad."""
        product = make_product(name='Sin proveedor')
        op = _orderpoint(company, warehouse, product,
                         route=_buy_route(warehouse.lot_stock))
        assert op._get_replenishment_multiple_alternative(10) is False

    def test_returns_the_selected_seller_uom_on_a_buy_route(
            self, company, warehouse):
        """Con ruta de compra y un proveedor que cubre la cantidad pedida:
        la UOM del proveedor elegido — deliberadamente distinta de la UOM
        base del producto, para que devolver ``self.product_uom`` por error
        se note de inmediato."""
        product = make_product(name='Con compra')
        base_uom = product.uom
        seller_uom = _uom('Caja de 12')
        assert seller_uom.pk != getattr(base_uom, 'pk', None)
        supplier = ResPartner.objects.create(name='Proveedor')
        tariff = _tariff(product, supplier, seller_uom, min_qty=1,
                         price=Decimal('5.00'))
        op = _orderpoint(company, warehouse, product,
                         route=_buy_route(warehouse.lot_stock))
        result = op._get_replenishment_multiple_alternative(10)
        assert result == seller_uom
        assert result != base_uom

    def test_uses_the_manually_fixed_supplier_without_calling_select_seller(
            self, company, warehouse):
        """Con ``supplier_id`` fijado a mano: se usa ese proveedor tal cual,
        sin pasar por ``_select_seller`` — enfrentado a un proveedor más
        barato que ganaría si el código lo ignorara."""
        product = make_product(name='Proveedor fijo')
        fixed_uom = _uom('Tarima')
        cheaper_uom = _uom('Pieza')
        assert fixed_uom.pk != cheaper_uom.pk
        fixed_partner = ResPartner.objects.create(name='Fijo')
        cheap_partner = ResPartner.objects.create(name='Barato')
        fixed_tariff = _tariff(product, fixed_partner, fixed_uom, min_qty=1,
                               price=Decimal('50.00'))
        _tariff(product, cheap_partner, cheaper_uom, min_qty=1,
               price=Decimal('1.00'))
        op = _orderpoint(company, warehouse, product,
                         route=_buy_route(warehouse.lot_stock),
                         supplier=fixed_tariff)
        result = op._get_replenishment_multiple_alternative(10)
        assert result == fixed_uom
        assert result != cheaper_uom
