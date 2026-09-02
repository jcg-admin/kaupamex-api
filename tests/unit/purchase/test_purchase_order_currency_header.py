"""``PurchaseOrder`` gana cabecera ``company_id``/``currency_id``/
``currency_rate`` (tarea #266).

Contrato adaptado de ``odoo19c: addons/purchase/models/purchase_order.py``,
``_compute_currency_id`` (``:459-466``) y ``_compute_currency_rate``
(``:211-218``). ``ResCurrency._get_conversion_rate`` ya estaba portado
(``src/addons/base/models/res_currency.py:462``) sin consumidor en ``purchase``;
estos casos verifican que la cabecera lo usa de verdad, no sólo que el campo
exista.

También cubre ``PurchaseOrderLine.company_id`` (stored, sincronizado en
``save()``) y ``PurchaseOrderLine.currency_id`` (``@property`` sobre
``order_id``).

**Qué haría fallar a cada control se declara en su caso.**
"""
from datetime import date, datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from addons.base.models import ResCompany, ResCurrency, ResUsers
from addons.base.models.res_currency import ResCurrencyRate
from addons.product.models import ProductProduct, ProductTemplate
from addons.purchase.models import PurchaseOrder, PurchaseOrderLine

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def mxn(db):
    return ResCurrency.objects.create(name='Y26', symbol='$', rounding='0.01')


@pytest.fixture
def usd(db):
    return ResCurrency.objects.create(name='Y27', symbol='US$', rounding='0.01')


@pytest.fixture
def company(db, mxn):
    return ResCompany.objects.create(code='po-266-a', name='PO 266 Co A',
                                     currency=mxn)


@pytest.fixture
def other_company(db, mxn):
    return ResCompany.objects.create(code='po-266-b', name='PO 266 Co B',
                                     currency=mxn)


@pytest.fixture
def supplier(db):
    return ResUsers.objects.create_user(login='vendedor-266@kaupamex.mx',
                                        password='x')


@pytest.fixture
def variant(db):
    tmpl = ProductTemplate.objects.create(name='Producto 266',
                                          list_price=Decimal('10.00'))
    return ProductProduct.objects.create(product_tmpl=tmpl)


def _rate(currency, day, value, company=None):
    return ResCurrencyRate.objects.create(
        currency=currency, company=company, name=day, rate=Decimal(str(value)))


class TestCurrencyIdCompute:
    """≙ ``_compute_currency_id`` (``odoo19c: purchase_order.py:459-466``)."""

    def test_defaults_to_the_company_currency_when_unset(self, company):
        """Qué haría fallar al control: no computar nada y dejar NULL."""
        order = PurchaseOrder.objects.create(company_id=company)
        order.refresh_from_db()
        assert order.currency_id == company.currency

    def test_an_explicit_value_survives_creation(self, company, usd):
        """``precompute=True``: un valor explícito en la creación no se pisa.

        Qué haría fallar al control: recomputar siempre. La empresa tiene
        MXN; si el cómputo ganara, ``currency_id`` terminaría en MXN, no en
        el USD que se pasó explícito.
        """
        order = PurchaseOrder.objects.create(company_id=company, currency_id=usd)
        order.refresh_from_db()
        assert order.currency_id == usd

    def test_recomputes_when_company_changes(self, company, other_company):
        """``@api.depends('company_id')``: cambiar la empresa recalcula.

        Qué haría fallar al control: computar sólo al crear. Las dos
        empresas comparten moneda (MXN) en este caso — lo que se mide es que
        el compute SE DISPARA, no sólo que el resultado cambie; el caso
        siguiente (moneda distinta) cubre el resultado.
        """
        order = PurchaseOrder.objects.create(company_id=company)
        order.currency_id = None  # simula «se limpió, toca recomputar»
        order.company_id = other_company
        order.save()
        order.refresh_from_db()
        assert order.currency_id == other_company.currency


class TestCurrencyRateCompute:
    """≙ ``_compute_currency_rate`` (``odoo19c: purchase_order.py:211-218``)."""

    def test_is_one_when_order_currency_matches_company(self, company, mxn):
        """Corto-circuito de ``_get_conversion_rate`` — misma moneda, tasa 1."""
        order = PurchaseOrder.objects.create(company_id=company, currency_id=mxn)
        order.refresh_from_db()
        assert order.currency_rate == Decimal('1')

    def test_uses_the_real_conversion_rate_for_a_different_currency(
            self, company, mxn, usd):
        """La empresa vale 1 y el dólar 0.05 el día de la orden.

        Qué haría fallar al control: quedarse en el default sin convertir.
        Con la tasa sembrada, ``currency_rate`` da **0.05**, no 1 ni 0 — un
        valor que sólo sale de leer la tabla de tasas.
        """
        day = date(2026, 1, 1)
        _rate(mxn, day, 1, company)
        _rate(usd, day, Decimal('0.05'), company)
        order = PurchaseOrder.objects.create(
            company_id=company, currency_id=usd, date_order=timezone.make_aware(datetime(2026, 1, 1)))
        order.refresh_from_db()
        assert order.currency_rate == Decimal('0.05')

    def test_recomputes_when_date_order_changes(self, company, mxn, usd):
        """Dos tasas en fechas distintas — cambiar ``date_order`` recalcula.

        Qué haría fallar al control: computar sólo al crear. Sin el
        recompute-por-dependencia, el segundo ``save()`` conservaría la tasa
        de la primera fecha (0.05) en vez de la nueva (0.10).
        """
        early, later = date(2026, 1, 1), date(2026, 2, 1)
        _rate(mxn, early, 1, company)
        _rate(usd, early, Decimal('0.05'), company)
        _rate(mxn, later, 1, company)
        _rate(usd, later, Decimal('0.10'), company)

        order = PurchaseOrder.objects.create(
            company_id=company, currency_id=usd,
            date_order=timezone.make_aware(datetime(2026, 1, 1)))
        order.refresh_from_db()
        assert order.currency_rate == Decimal('0.05')

        order.date_order = timezone.make_aware(datetime(2026, 2, 1))
        order.save()
        order.refresh_from_db()
        assert order.currency_rate == Decimal('0.10')


class TestOrderLineCompanyAndCurrency:
    """≙ ``purchase.order.line.company_id`` (``odoo19c: purchase_order_line.py:
    53``) y ``currency_id`` (``:85``)."""

    def test_line_company_id_mirrors_the_order(self, company, variant):
        """``related='order_id.company_id', store=True`` — sincronizado en
        ``save()``.

        Qué haría fallar al control: no sincronizar. Sin ``_sync_company``,
        ``company_id`` de la línea se queda ``None`` aunque la orden tenga
        empresa.
        """
        order = PurchaseOrder.objects.create(company_id=company)
        line = PurchaseOrderLine.objects.create(
            order_id=order, product_id=variant, price_unit=Decimal('10.00'))
        line.refresh_from_db()
        assert line.company_id == company

    def test_line_company_id_resyncs_when_order_company_changes(
            self, company, other_company, variant):
        """El campo es ``readonly`` desde la orden, no un valor congelado al
        crear — cada ``save()`` de la línea lo vuelve a leer."""
        order = PurchaseOrder.objects.create(company_id=company)
        line = PurchaseOrderLine.objects.create(
            order_id=order, product_id=variant, price_unit=Decimal('10.00'))
        order.company_id = other_company
        order.save()
        line.save()
        line.refresh_from_db()
        assert line.company_id == other_company

    def test_line_currency_id_property_reads_the_order(self, company, usd, variant):
        """``@property`` sin columna — navega ``order_id.currency_id``.

        Qué haría fallar al control: leer una columna propia en vez del FK.
        Aquí no hay columna ``currency_id`` en la línea; si la property
        estuviera mal cableada, devolvería la moneda de la EMPRESA (MXN) en
        vez de la de la ORDEN (USD, fijada explícita).
        """
        order = PurchaseOrder.objects.create(company_id=company, currency_id=usd)
        line = PurchaseOrderLine.objects.create(
            order_id=order, product_id=variant, price_unit=Decimal('10.00'))
        assert line.currency_id == usd

    def test_line_currency_id_is_none_without_an_order(self, variant):
        """Degradación defensiva: sin ``order_id`` no hay de dónde leer."""
        line = PurchaseOrderLine(product_id=variant, price_unit=Decimal('10.00'))
        assert line.currency_id is None
