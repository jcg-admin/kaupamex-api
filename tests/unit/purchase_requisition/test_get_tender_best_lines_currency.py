"""``PurchaseOrderLine.price_total_cc``/``company_currency_id`` y el cierre de
D-3a en ``get_tender_best_lines`` (tarea #266).

Contrato adaptado de ``odoo19c: addons/purchase_requisition/models/purchase.py``,
``PurchaseOrderLine.price_total_cc``/``company_currency_id`` (``:257-258``),
``_compute_price_total_cc`` (``:260-263``) y ``get_tender_best_lines``
(``:192-235``). Antes de la tarea #266, ``purchase.order`` no declaraba
``company_id``/``currency_id``/``currency_rate`` (Causa D del docstring del
módulo), así que ``get_tender_best_lines`` comparaba con
``line.price_subtotal()`` — degradación D-3, correcta sólo si todas las
alternativas comparten moneda.

**Qué haría fallar a cada control se declara en su caso.** El caso central
—``test_prefers_the_cheaper_line_in_company_currency_not_the_smaller_raw_number``—
es el que discrimina D-3a: con ``PurchaseOrder._compute_currency_rate``
neutralizado a 1.0 fijo, el "mejor precio" se invierte.
"""
from datetime import date
from decimal import Decimal

import pytest

from addons.base.models import ResCompany, ResCurrency
from addons.base.models.res_currency import ResCurrencyRate
from addons.base_setup.settings_access import get_setting
from addons.product.models import ProductProduct, ProductTemplate
from addons.purchase.models import PurchaseOrder, PurchaseOrderLine
from addons.purchase_requisition.models import PurchaseOrderGroup

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def mxn(db):
    return ResCurrency.objects.create(name='Y28', symbol='$', rounding='0.01')


@pytest.fixture
def usd(db):
    return ResCurrency.objects.create(name='Y29', symbol='US$', rounding='0.01')


@pytest.fixture
def company(db, mxn):
    return ResCompany.objects.create(code='po-266-c', name='PO 266 Co C',
                                     currency=mxn)


@pytest.fixture
def variant(db):
    tmpl = ProductTemplate.objects.create(name='Producto tender 266',
                                          list_price=Decimal('10.00'))
    return ProductProduct.objects.create(product_tmpl=tmpl)


def _rate(currency, day, value, company=None):
    return ResCurrencyRate.objects.create(
        currency=currency, company=company, name=day, rate=Decimal(str(value)))


def _alternative(company, currency, variant, price_unit, group=None):
    """Una orden en borrador con una sola línea del producto dado."""
    order = PurchaseOrder.objects.create(company_id=company, currency_id=currency)
    if group is not None:
        order.purchase_group = group
        order.save()
    PurchaseOrderLine.objects.create(
        order_id=order, product_id=variant, price_unit=price_unit)
    return order


class TestPriceTotalCcAndCompanyCurrencyId:
    """≙ ``price_total_cc``/``company_currency_id`` (``odoo19c: :257-258``)."""

    def test_price_total_cc_equals_subtotal_when_rate_is_one(self, company, mxn, variant):
        """Sin conversión (misma moneda), ``price_total_cc`` == ``price_subtotal()``."""
        order = PurchaseOrder.objects.create(company_id=company, currency_id=mxn)
        line = PurchaseOrderLine.objects.create(
            order_id=order, product_id=variant, price_unit=Decimal('100.00'))
        line.refresh_from_db()
        assert line.price_total_cc == line.price_subtotal().quantize(Decimal('0.01'))

    def test_price_total_cc_divides_by_the_order_currency_rate(
            self, company, mxn, usd, variant):
        """Qué haría fallar al control: no dividir — dejar
        ``price_total_cc == price_subtotal()`` aunque la orden esté en otra
        moneda.
        """
        day_rate = Decimal('0.05')
        today = date.today()
        _rate(mxn, today, 1, company)
        _rate(usd, today, day_rate, company)
        # Las tasas se siembran ANTES de crear la orden: currency_rate es
        # precompute=True, no un valor que se actualice solo cuando cambia
        # una tasa sembrada después — es la misma congelación que
        # SaleOrder.currency_rate documenta ("tasa aplicada al confirmar").
        order = PurchaseOrder.objects.create(company_id=company, currency_id=usd)
        line = PurchaseOrderLine.objects.create(
            order_id=order, product_id=variant, price_unit=Decimal('10.00'))
        line.refresh_from_db()
        expected = (line.price_subtotal() / order.currency_rate).quantize(
            Decimal('0.01'))
        assert line.price_total_cc == expected
        assert line.price_total_cc != line.price_subtotal().quantize(Decimal('0.01'))

    def test_company_currency_id_is_the_line_company_currency(
            self, company, mxn, variant):
        """``@property`` ``related='company_id.currency_id'``, sin ``store``."""
        order = PurchaseOrder.objects.create(company_id=company, currency_id=mxn)
        line = PurchaseOrderLine.objects.create(
            order_id=order, product_id=variant, price_unit=Decimal('10.00'))
        line.refresh_from_db()
        assert line.company_currency_id == mxn


class TestGetTenderBestLinesD3a:
    """D-3a CERRADA: compara en moneda de la empresa, no por número crudo."""

    def test_prefers_the_cheaper_line_in_company_currency_not_the_smaller_raw_number(
            self, company, mxn, usd, variant):
        """Dos alternativas del mismo producto: una en MXN (barata de
        verdad) y otra en USD (número menor, pero *cara* al convertir).

        1 USD = 20 MXN (``currency_rate`` = 0.05). La línea en pesos cuesta
        100 (IVA incl.); la línea en dólares cuesta 10 (IVA incl.) — un
        número menor, pero equivalen a ~200 pesos. Comparar por
        ``price_subtotal()`` crudo elegiría la de dólares por ser el número
        más chico; comparar por ``price_total_cc`` —moneda de la empresa—
        elige la de pesos, que es la que de verdad cuesta menos.
        """
        # Las tasas se siembran ANTES de crear las órdenes: currency_rate es
        # precompute=True (se congela al crear), no recalcula solo porque
        # aparezca una tasa nueva sin que company_id/currency_id/date_order
        # cambien — misma congelación que documenta
        # SaleOrder.currency_rate ("tasa aplicada al confirmar").
        today = date.today()
        _rate(mxn, today, 1, company)
        _rate(usd, today, Decimal('0.05'), company)

        group = PurchaseOrderGroup.objects.create()
        mxn_order = _alternative(company, mxn, variant, Decimal('100.00'), group)
        usd_order = _alternative(company, usd, variant, Decimal('10.00'), group)

        mxn_line = mxn_order.order_line.all()[0]
        usd_line = usd_order.order_line.all()[0]

        # Qué haría fallar al control: comparar sin convertir.
        assert usd_line.price_subtotal() < mxn_line.price_subtotal(), (
            'la premisa del caso es que el número CRUDO en USD es menor'
        )
        assert usd_line.price_total_cc > mxn_line.price_total_cc, (
            'convertida a pesos, la línea en USD es la más cara'
        )

        best_price_ids, _best_date_ids, best_unit_price_ids = (
            mxn_order.get_tender_best_lines())

        assert best_price_ids == [mxn_line.pk]
        assert best_unit_price_ids == [mxn_line.pk]

    def test_best_date_ids_stays_empty_d3b_open(self, company, mxn, variant):
        """D-3b sigue abierta: sin ``date_planned`` en la línea, la lista de
        mejores fechas es siempre vacía — el contrato de la tripleta no
        cambia."""
        order = PurchaseOrder.objects.create(company_id=company, currency_id=mxn)
        PurchaseOrderLine.objects.create(
            order_id=order, product_id=variant, price_unit=Decimal('10.00'))
        _best_price_ids, best_date_ids, _best_unit_price_ids = (
            order.get_tender_best_lines())
        assert best_date_ids == []
