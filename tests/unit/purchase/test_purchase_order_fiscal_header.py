"""La cabecera fiscal de ``purchase.order`` y su asignación desde el proveedor.

≙ ``odoo19c: addons/purchase/models/purchase_order.py:80-82,143,153,444-457``
y ``addons/purchase/models/res_partner.py:45`` (``buyer_id``).
"""
import pytest

from addons.account.models import AccountFiscalPosition, AccountPaymentTerm
from addons.base.models import ResCompany, ResCountry, ResPartner
from orm.environments import company_scope, sudo
from orm.registry import MODELS_BY_NAME
from tests.factories.user_factory import UserFactory

pytestmark = pytest.mark.django_db
ORDER = 'purchase.order'


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


@pytest.fixture
def company():
    return ResCompany.objects.create(name='Compras fiscal 0535')


@pytest.fixture
def mexico():
    return ResCountry.objects.get(code__iexact='MX')


def _order(company, partner=None):
    values = {'company_id': company.pk}
    if partner is not None:
        values['partner_id'] = partner.pk
    [order] = MODELS_BY_NAME[ORDER].create([values])
    return order


def _position(company, name='México', **values):
    return AccountFiscalPosition.objects.create(
        name=name, company=company, auto_apply=True, **values)


def test_the_three_header_fields_exist_with_the_source_names():
    model = MODELS_BY_NAME[ORDER]
    assert {'origin', 'fiscal_position_id', 'payment_term_id'} <= {
        field.name for field in model._meta.get_fields()}


def test_origin_is_not_copied(company):
    order = _order(company)
    order.origin = 'S00042'
    order.save()
    assert order.copy().origin == ''


def test_the_partner_change_is_an_onchange_trigger():
    methods = MODELS_BY_NAME[ORDER]()._onchange_methods
    assert 'onchange_partner_id' in {
        method.__name__ for method in methods['partner_id']}
    assert 'onchange_partner_id' in {
        method.__name__ for method in methods['company_id']}


def test_without_partner_the_position_is_cleared(company, mexico):
    order = _order(company)
    order.fiscal_position_id = _position(company)
    assert order.onchange_partner_id() == {}
    assert order.fiscal_position_id is None


def test_the_partner_brings_position_payment_term_and_buyer(
        company, mexico):
    position = _position(company, country=mexico)
    term = AccountPaymentTerm.objects.create(name='30 días')
    buyer = UserFactory()
    partner = ResPartner.objects.create(
        name='Proveedor fiscal', country=mexico,
        property_supplier_payment_term_id=term, buyer_id=buyer)
    order = _order(company, partner)
    order.onchange_partner_id()
    assert order.fiscal_position_id == position
    assert order.payment_term_id == term
    assert order.user_id == buyer


def test_no_matching_position_assigns_none_not_an_empty_record(
        company, mexico):
    partner = ResPartner.objects.create(name='Sin posición', country=mexico)
    order = _order(company, partner)
    order.onchange_partner_id()
    assert order.fiscal_position_id is None


def test_without_buyer_the_order_buyer_is_kept(company, mexico):
    keeper = UserFactory()
    partner = ResPartner.objects.create(name='Sin comprador', country=mexico)
    order = _order(company, partner)
    order.user_id = keeper
    order.onchange_partner_id()
    assert order.user_id == keeper


def test_the_position_is_resolved_with_the_company_of_the_order(mexico):
    """≙ ``self.with_company(self.company_id)``: la posición sale de la
    empresa de la orden aunque la activa en contexto sea otra."""
    own = ResCompany.objects.create(name='Empresa de la orden 0535')
    other = ResCompany.objects.create(name='Empresa activa 0535')
    _position(other, name='De la activa', country=mexico)
    expected = _position(own, name='De la orden', country=mexico)
    partner = ResPartner.objects.create(name='Proveedor MX', country=mexico)
    order = _order(own, partner)
    with company_scope(other.pk):
        order.onchange_partner_id()
    assert order.fiscal_position_id == expected
