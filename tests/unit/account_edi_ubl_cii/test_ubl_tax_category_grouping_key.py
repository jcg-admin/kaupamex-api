"""La categoría de impuesto UBL de una base-line y la dirección del tercero.

≙ ``_ubl_default_tax_category_grouping_key`` (``odoo19c:
addons/account_edi_ubl_cii/models/account_edi_ubl.py:92-157``, LGPL-3) y
``_ubl_get_partner_address_node`` (``:1129-1141``). La primera es la clave de
agrupación que leen todos los ``_ubl_add_*`` que agregan importes: hasta que
``account.tax`` portó su agregación estaba bloqueada.

La segunda lee el país del tercero. En la fuente ``country_id`` es el
registro; aquí el campo es ``country`` y ``country_id`` es la columna, un
entero: leer ``.code`` sobre él falla. Los casos usan un tercero con país
para que esa diferencia sea visible.
"""

from decimal import Decimal

import pytest

from addons.account.models import AccountTax
from addons.account_edi_ubl_cii.models.account_edi_ubl import AccountEdiUBL
from addons.account_edi_ubl_cii.models.account_edi_ubl_pint_eu import (
    AccountEdiUBLPintEU,
)
from addons.base.models import ResCompany, ResCountry, ResPartner
from addons.base.models.res_currency import ResCurrency
from orm.environments import get_context

pytestmark = pytest.mark.django_db


@pytest.fixture
def mexico(db):
    country, _ = ResCountry.objects.get_or_create(
        code='MX', defaults={'name': 'México'})
    return country


@pytest.fixture
def currency(db):
    currency, _ = ResCurrency.objects.get_or_create(
        name='MXN', defaults={'symbol': '$'})
    return currency


@pytest.fixture
def company(db, currency):
    return ResCompany.objects.create(code='ubl', name='UBL',
                                     currency=currency)


@pytest.fixture
def vals(mexico):
    supplier = ResPartner.objects.create(name='Proveedor', country=mexico)
    customer = ResPartner.objects.create(name='Cliente', country=mexico)
    return {'supplier': supplier, 'customer': customer}


def _tax(company, **kwargs):
    values = {'name': 'IVA 16', 'amount': Decimal('16'), 'company': company,
              **kwargs}
    return AccountTax.objects.create(**values)


def _tax_data(tax):
    return {'tax': tax, 'is_reverse_charge': False}


def test_a_percent_tax_between_same_country_parties_is_standard(
        company, currency, vals):
    tax = _tax(company)
    key = AccountEdiUBL._ubl_default_tax_category_grouping_key(
        {}, _tax_data(tax), vals, currency)
    assert key['tax_category_code'] == 'S'
    assert key['percent'] == tax.amount
    assert key['scheme_id'] == 'VAT'
    assert key['is_withholding'] is False
    assert key['currency'] == currency


def test_a_negative_tax_is_a_withholding(company, currency, vals):
    tax = _tax(company, name='Retención', amount=Decimal('-10'))
    key = AccountEdiUBL._ubl_default_tax_category_grouping_key(
        {}, _tax_data(tax), vals, currency)
    assert key['is_withholding'] is True


def test_a_line_without_tax_is_exempt(currency, vals):
    key = AccountEdiUBL._ubl_default_tax_category_grouping_key(
        {}, None, vals, currency)
    assert key['tax_category_code'] == 'E'
    assert key['percent'] == 0.0
    assert key['tax_exemption_reason']


def test_a_fixed_tax_has_no_tax_category(company, currency, vals):
    tax = _tax(company, name='Fijo', amount_type='fixed')
    assert AccountEdiUBL._ubl_default_tax_category_grouping_key(
        {}, _tax_data(tax), vals, currency) is None


def test_the_invoice_reaches_the_exemption_reason_through_the_context(
        company, currency, vals, monkeypatch):
    """≙ ``self.with_context(tax_exemption_reason_invoice=...)``: la nota
    belga lee la factura del contexto (``account_edi_common.py:353``)."""
    seen = []

    def spy(cls, customer, supplier, tax):
        seen.append(get_context().get('tax_exemption_reason_invoice'))
        return {}

    monkeypatch.setattr(AccountEdiUBL, '_get_tax_exemption_reason',
                        classmethod(spy))
    invoice = object()
    AccountEdiUBL._ubl_default_tax_category_grouping_key(
        {}, _tax_data(_tax(company)), {**vals, 'invoice': invoice}, currency)
    assert seen == [invoice]
    assert 'tax_exemption_reason_invoice' not in get_context()


def test_the_partner_address_reports_its_country(mexico, vals):
    node = AccountEdiUBL._ubl_get_partner_address_node({}, vals['customer'])
    assert node['cac:Country']['cbc:IdentificationCode']['_text'] == 'MX'
    assert node['cac:Country']['cbc:Name']['_text'] == mexico.name


def test_a_partner_without_country_reports_no_country(db):
    partner = ResPartner.objects.create(name='Sin país')
    node = AccountEdiUBL._ubl_get_partner_address_node({}, partner)
    assert not node['cac:Country']['cbc:IdentificationCode']['_text']
    assert not node['cbc:CountrySubentity']['_text']


@pytest.mark.parametrize('customer_code, expected', [
    ('DE', 'fecha'), ('BE', None)])
def test_an_intra_community_delivery_reports_the_invoice_date(
        monkeypatch, customer_code, expected):
    """≙ ``AccountEdiUBLPintEU._ubl_get_delivery_node_from_delivery_address``
    (``odoo19c: account_edi_ubl_pint_eu.py:41-56``): entre dos países
    distintos del área económica europea se informa la fecha. El padre está
    bloqueado (``module_installed``), así que se sustituye para aislar la
    extensión."""
    belgium, _ = ResCountry.objects.get_or_create(
        code='BE', defaults={'name': 'Belgium'})
    other, _ = ResCountry.objects.get_or_create(
        code=customer_code, defaults={'name': customer_code})
    monkeypatch.setattr(
        AccountEdiUBL, '_ubl_get_delivery_node_from_delivery_address',
        classmethod(lambda cls, vals: {
            'cbc:ActualDeliveryDate': {'_text': None}}))
    monkeypatch.setattr(AccountEdiUBLPintEU, '_get_document_type',
                        classmethod(lambda cls, vals: 'invoice'))

    class Invoice:
        invoice_date = 'fecha'

    delivery_node = (
        AccountEdiUBLPintEU._ubl_get_delivery_node_from_delivery_address)
    node = delivery_node({
        'invoice': Invoice(),
        'supplier': ResPartner.objects.create(name='Proveedor',
                                              country=belgium),
        'customer': ResPartner.objects.create(name='Cliente', country=other),
    })
    assert node['cbc:ActualDeliveryDate']['_text'] == expected
