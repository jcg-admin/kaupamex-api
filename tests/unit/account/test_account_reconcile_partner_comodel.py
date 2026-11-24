"""Los contactos de la regla de conciliación son ``res.partner``.

≙ ``odoo19c: addons/account/models/account_reconcile_model.py:20-23,
118-122, 144-145``: ``partner_id``, ``mapped_partner_id`` y
``match_partner_ids`` se declaran sobre ``res.partner``, así que un
contacto sin acceso al sistema es elegible.
"""
import pytest

from addons.account.models import (
    AccountReconcileModel,
    AccountReconcileModelLine,
)
from addons.base.models import ResCompany, ResPartner
from orm.commands import Command

pytestmark = pytest.mark.django_db


@pytest.fixture
def rule():
    company = ResCompany.objects.create(
        name='Kaupamex', code='kaupamex_test_reco_partner')
    return AccountReconcileModel.objects.create(
        name='Comisiones', company=company, match_label='contains',
        match_label_param='FEE')


@pytest.fixture
def bank():
    return ResPartner.objects.create(name='Banco sin acceso')


def test_the_line_partner_is_a_res_partner():
    field = AccountReconcileModelLine._meta.get_field('partner')
    assert field.related_model is ResPartner


def test_a_contact_without_login_can_map_the_partner(rule, bank):
    AccountReconcileModelLine.objects.create(
        model=rule, partner=bank, amount_type='percentage',
        amount_string='100')
    rule = AccountReconcileModel.objects.get(pk=rule.pk)
    assert rule.compute_mapped_partner().pk == bank.pk


def test_the_rule_restricts_to_res_partners(bank):
    rule = AccountReconcileModel.objects.create(
        name='Sólo el banco', company=ResCompany.objects.create(
            name='Otra', code='kaupamex_test_reco_partner_b'))
    rule.sudo().write({'match_partner_ids': [Command.link(bank.pk)]})
    assert rule.compute_can_be_proposed() is True
