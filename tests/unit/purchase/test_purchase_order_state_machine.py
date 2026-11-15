"""Máquina de estados de ``purchase.order``.

≙ ``odoo19c: addons/purchase/models/purchase_order.py:90,105-117,157-159,
615-668,1251-1260`` y ``purchase_order_line.py:91-95``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
purchase-order-state-machine.md``.
"""
from decimal import Decimal

import pytest

from addons.base.models import ResCompany, ResPartner
from exceptions import UserError
from orm.environments import sudo
from orm.registry import MODELS_BY_NAME
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _as_superuser():
    """Los datos de prueba de la referencia se escriben como superusuario."""
    with sudo():
        yield


def _company(**values):
    return ResCompany.objects.create(name='Compras SM 0397', **values)


def _order(company, price='100.00', product=True, **line_values):
    vendor = ResPartner.objects.create(name='Proveedor SM 0397')
    [order] = MODELS_BY_NAME['purchase.order'].create(
        [{'partner_id': vendor.pk, 'company_id': company.pk,
          'currency_id': company.currency_id}])
    values = {'order_id': order.id, 'name': 'Eleke',
              'price_unit': Decimal(price), **line_values}
    if product:
        values['product_id'] = make_product(
            name='Insumo SM', price=Decimal(price)).pk
    MODELS_BY_NAME['purchase.order.line'].create([values])
    return order


def test_the_state_selection_has_the_five_source_values():
    field = MODELS_BY_NAME['purchase.order']._meta.get_field('state')
    assert [key for key, _ in field.choices] == [
        'draft', 'sent', 'to approve', 'purchase', 'cancel']


def test_the_lock_and_approval_fields_exist():
    model = MODELS_BY_NAME['purchase.order']
    assert model._meta.get_field('locked').default is False
    assert model._meta.get_field('date_approve').db_index
    assert model._meta.get_field('user_id').db_index
    line = MODELS_BY_NAME['purchase.order.line']
    assert [k for k, _ in line._meta.get_field('display_type').choices] == [
        'line_section', 'line_subsection', 'line_note']
    assert line._meta.get_field('is_downpayment').default is False


def test_lock_confirmed_po_follows_the_company():
    order = _order(_company(po_lock='lock'))
    assert order.lock_confirmed_po == 'lock'


def test_one_step_confirms_and_dates_the_approval():
    order = _order(_company())
    assert order.button_confirm() is True
    assert order.state == 'purchase'
    assert order.date_approve is not None


def test_two_step_over_the_threshold_waits_for_approval():
    order = _order(_company(po_double_validation='two_step',
                            po_double_validation_amount=50))
    order.button_confirm()
    assert order.state == 'to approve'
    assert not order.date_approve


def test_two_step_under_the_threshold_approves():
    order = _order(_company(po_double_validation='two_step',
                            po_double_validation_amount=5000))
    order.button_confirm()
    assert order.state == 'purchase'


def test_the_lock_policy_locks_the_approved_order():
    order = _order(_company(po_lock='lock'))
    order.button_confirm()
    assert order.locked is True


def test_confirming_a_confirmed_order_skips_it():
    order = _order(_company())
    order.button_confirm()
    approved = order.date_approve
    assert order.button_confirm() is True
    assert order.date_approve == approved


def test_a_line_without_product_blocks_the_confirmation():
    order = _order(_company(), product=False)
    with pytest.raises(UserError):
        order.button_confirm()
    assert order.state == 'draft'


def test_a_section_line_without_product_does_not_block():
    order = _order(_company(), product=False, display_type='line_section')
    order.button_confirm()
    assert order.state == 'purchase'


def test_a_locked_order_cannot_be_cancelled_until_unlocked():
    order = _order(_company())
    order.button_lock()
    with pytest.raises(UserError):
        order.button_cancel()
    order.invalidate_recordset()
    assert order.state == 'draft'
    order.button_unlock()
    order.button_cancel()
    assert order.state == 'cancel'


def test_button_draft_returns_to_draft():
    order = _order(_company())
    order.button_cancel()
    order.button_draft()
    assert order.state == 'draft'
