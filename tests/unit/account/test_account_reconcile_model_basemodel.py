"""``account.reconcile.model`` y su línea sobre ``BaseModel``.

≙ ``odoo19c: addons/account/models/account_reconcile_model.py:8-13, 91-96``:
la identidad de las dos clases, ``_check_company_auto`` y ``line_ids``
como recordset que lee ``_compute_partner_mapping``.
"""
import pytest

from addons.account.models import (
    AccountReconcileModel,
    AccountReconcileModelLine,
)
from addons.base.models import ResCompany
from orm.models import BaseModel

pytestmark = pytest.mark.django_db


@pytest.fixture
def rule():
    company = ResCompany.objects.create(
        name='Kaupamex', code='kaupamex_test_account_u5')
    return AccountReconcileModel.objects.create(
        name='Comisiones', company=company, match_label='contains',
        match_label_param='FEE')


def test_both_models_are_basemodels():
    assert issubclass(AccountReconcileModel, BaseModel)
    assert issubclass(AccountReconcileModelLine, BaseModel)


def test_both_models_check_the_company():
    assert AccountReconcileModel._check_company_auto is True
    assert AccountReconcileModelLine._check_company_auto is True


def test_the_lines_of_a_rule_are_a_recordset(rule):
    line = AccountReconcileModelLine.objects.create(
        model=rule, amount_type='percentage', amount_string='100')
    lines = AccountReconcileModel.objects.get(pk=rule.pk).line_ids
    assert isinstance(lines, BaseModel)
    assert lines.ids == [line.id]


def test_a_single_line_without_partner_maps_nothing(rule):
    AccountReconcileModelLine.objects.create(
        model=rule, amount_type='percentage', amount_string='100')
    rule = AccountReconcileModel.objects.get(pk=rule.pk)
    assert rule.compute_mapped_partner() is None
