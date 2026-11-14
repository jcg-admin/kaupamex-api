"""Lo que ``purchase`` cuelga en ``res.company``.

≙ ``odoo19c: addons/purchase/models/res_company.py``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
purchase-res-company.md``.
"""
from decimal import Decimal

import pytest

from addons.base.models import ResCompany

pytestmark = pytest.mark.django_db


def _field(name):
    return ResCompany._meta.get_field(name)


def test_the_three_fields_carry_the_source_defaults():
    assert _field('po_lock').default == 'edit'
    assert _field('po_double_validation').default == 'one_step'
    assert Decimal(str(_field('po_double_validation_amount').default)) == 5000


def test_the_selections_are_the_source_ones():
    assert [k for k, _ in _field('po_lock').choices] == ['edit', 'lock']
    assert [k for k, _ in _field('po_double_validation').choices] == [
        'one_step', 'two_step']


def test_a_new_company_gets_the_defaults():
    company = ResCompany.objects.create(name='Compras 0397')
    company.refresh_from_db()
    assert company.po_lock == 'edit'
    assert company.po_double_validation == 'one_step'
    assert company.po_double_validation_amount == 5000
