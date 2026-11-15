"""El nombre de ``purchase.order`` sale de su secuencia al crear.

≙ ``odoo19c: addons/purchase/models/purchase_order.py:394-406`` y la
secuencia ``seq_purchase_order`` (``purchase/data/purchase_data.xml:21-27``).
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
purchase-order-sequence.md``.
"""
import pytest

from addons.base.models import IrSequence, ResCompany, ResPartner
from orm.environments import sudo
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


def _create(**values):
    vendor = ResPartner.objects.create(name='Proveedor SEQ')
    [order] = MODELS_BY_NAME['purchase.order'].create(
        [{'partner_id': vendor.pk, **values}])
    return order


def test_the_name_defaults_to_new():
    field = MODELS_BY_NAME['purchase.order']._meta.get_field('name')
    assert field.default == 'New'


def test_new_orders_take_the_next_number_of_the_sequence():
    IrSequence.objects.filter(code='purchase.order').delete()
    first = _create()
    second = _create()
    assert first.name == 'P00001'
    assert second.name == 'P00002'
    sequence = IrSequence.objects.get(code='purchase.order')
    assert (sequence.prefix, sequence.padding) == ('P', 5)
    assert sequence.company_id is None


def test_an_explicit_name_is_kept():
    assert _create(name='PO-MANUAL').name == 'PO-MANUAL'


def test_confirming_keeps_the_name():
    order = _create()
    name = order.name
    order.button_confirm()
    assert order.name == name


def test_the_company_sequence_wins_over_the_global_one():
    IrSequence.objects.filter(code='purchase.order').delete()
    company = ResCompany.objects.create(name='Compras SEQ')
    IrSequence.objects.create(name='Global', code='purchase.order',
                              prefix='G', padding=3)
    IrSequence.objects.create(name='Propia', code='purchase.order',
                              prefix='C', padding=3, company=company)
    assert _create(company_id=company.pk).name == 'C001'
