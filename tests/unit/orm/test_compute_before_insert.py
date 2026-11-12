"""Un cálculo almacenado corre una vez por estado de dependencias al crear.

≙ ``create``/``_create`` (``odoo19c: odoo/orm/models.py:4611-4949``): los
precompute los calcula ``_add_precomputed_values`` (``:4814-4846``) antes del
INSERT; los demás, el volcado tras ``modified(..., create=True)``
(``:4929-4933``). Ninguno corre dos veces para el mismo estado.

Aquí seis modelos calculan en su propio ``save()`` antes del INSERT, y el
núcleo los volvía a calcular: el pase de precompute de ``pre_save`` (los
precompute) y el marcado de creación de ``post_save`` (los readonly).
designs/eager-computes-in-save.md. Las pruebas cuentan invocaciones, miden
el valor persistido y comprueban que una dependencia posterior sigue
recalculando.
"""
from decimal import Decimal

import pytest
from django.apps import apps
from django.utils import timezone

from addons.crm.models import CrmLead
from addons.sale.models import SaleOrder, SaleOrderLine
from orm.environments import env as current_env
from orm.environments import transaction_scope
from tests.factories.order_factory import make_order
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.django_db

AccountAccount = apps.get_model('account', 'AccountAccount')
AccountJournal = apps.get_model('account', 'AccountJournal')
AccountMove = apps.get_model('account', 'AccountMove')
AccountMoveLine = apps.get_model('account', 'AccountMoveLine')
ResCompany = apps.get_model('base', 'ResCompany')
ResCurrency = apps.get_model('base', 'ResCurrency')


def _flush():
    with transaction_scope():
        current_env().flush_all()


@pytest.fixture
def spy(monkeypatch):
    """``spy(Model, 'metodo')`` cuenta las invocaciones del método."""
    counts = {}

    def install(model, name):
        original = getattr(model, name)
        counts[name] = 0

        def counting(self, *args, **kwargs):
            counts[name] += 1
            return original(self, *args, **kwargs)

        monkeypatch.setattr(model, name, counting)
        return counts

    return install


def test_a_line_computes_its_precompute_amounts_once(user, spy):
    counts = spy(SaleOrderLine, '_compute_amount')
    product = make_product(name='Hora')
    line = SaleOrderLine.objects.create(
        order=make_order(user=user), product=product, name=product.name,
        price_unit=Decimal('90.00'), product_uom_qty=2)
    _flush()
    assert counts['_compute_amount'] == 1
    # Los mismos importes que daba el doble cálculo, medidos antes del cambio:
    # el precio de 90 lleva un 16 % incluido.
    row = SaleOrderLine.objects.values(
        'price_subtotal', 'price_tax', 'price_total').get(pk=line.pk)
    assert row == {'price_subtotal': Decimal('155.17'),
                   'price_tax': Decimal('24.83'),
                   'price_total': Decimal('180.00')}


def test_a_lead_computes_readonly_and_precompute_fields_once(spy):
    spy(CrmLead, '_compute_won_status')
    counts = spy(CrmLead, '_compute_team_id')
    lead = CrmLead.objects.create(name='Iniciativa', probability=40,
                                  expected_revenue=Decimal('1000'))
    _flush()
    assert counts == {'_compute_won_status': 1, '_compute_team_id': 1}
    row = CrmLead.objects.values('won_status', 'prorated_revenue').get(
        pk=lead.pk)
    assert row['won_status'] == 'pending'
    assert row['prorated_revenue'] == pytest.approx(400.0)


def test_a_later_dependency_change_still_recomputes(spy):
    lead = CrmLead.objects.create(name='Iniciativa', probability=40,
                                  expected_revenue=Decimal('1000'))
    _flush()
    counts = spy(CrmLead, '_compute_prorated_revenue')
    lead.probability = 50
    lead.save()
    _flush()
    assert counts['_compute_prorated_revenue'] >= 1
    assert CrmLead.objects.values_list(
        'prorated_revenue', flat=True).get(pk=lead.pk) == pytest.approx(500.0)


@pytest.fixture
def company():
    currency, _ = ResCurrency.objects.get_or_create(
        name='MXN', defaults={'symbol': '$'})
    return ResCompany.create_company('Cuentas', currency=currency,
                                     code='cuentas')


def test_an_account_computes_its_group_once_and_keeps_a_given_type(
        company, spy):
    """``account_type`` es precompute editable: dado en el alta no se
    calcula (``_add_precomputed_values`` sólo calcula lo que ``vals`` no
    trae). ``internal_group`` es readonly sin precompute: lo calcula una vez
    el marcado de creación."""
    spy(AccountAccount, '_compute_account_type')
    counts = spy(AccountAccount, '_compute_internal_group')
    account = AccountAccount.objects.create(
        code='105', name='Clientes', account_type='asset_receivable',
        company=company)
    _flush()
    assert counts == {'_compute_account_type': 0,
                      '_compute_internal_group': 1}
    row = AccountAccount.objects.values('account_type', 'internal_group').get(
        pk=account.pk)
    assert row == {'account_type': 'asset_receivable',
                   'internal_group': 'asset'}


def test_an_order_computes_its_validity_date_once(user, spy):
    """``validity_date`` es precompute: lo calcula el pase de ``pre_save``;
    ``SaleOrder.save`` sólo lo recalcula cuando cambia la empresa."""
    counts = spy(SaleOrder, '_compute_validity_date')
    make_order(user=user)
    _flush()
    assert counts['_compute_validity_date'] == 1


@pytest.fixture
def journal(company):
    return AccountJournal.objects.create(name='Ventas', code='VEN',
                                         type='sale', company=company)


def test_a_move_line_computes_its_balance_once(company, journal, spy):
    counts = spy(AccountMoveLine, '_compute_balance')
    account = AccountAccount.objects.create(
        code='105', name='Clientes', account_type='asset_receivable',
        company=company)
    move = AccountMove.objects.create(move_type='entry',
                                      date=timezone.now().date(),
                                      journal=journal, company=company)
    line = AccountMoveLine.objects.create(move=move, account=account,
                                          debit=Decimal('100.00'))
    _flush()
    assert counts['_compute_balance'] == 1
    assert AccountMoveLine.objects.values_list(
        'balance', flat=True).get(pk=line.pk) == Decimal('100.00')
