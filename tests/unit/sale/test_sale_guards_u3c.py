"""Guardas de borrado, tarifa y restricciones de ``sale`` (U3c).

≙ ``odoo19c: addons/sale/models/sale_order.py:848-869,1032-1043`` y
``odoo19c: addons/sale/models/sale_order_line.py:56-59,1452-1473``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
sale-basemodel-u3c-guards.md``.

*Métrica:* el ``UserError``/``ValidationError`` de cada guarda en su caso
prohibido, y su ausencia en el permitido; el ``state`` de la línea tras
cambiar el de su orden.
*Ciega a:* un borrado por ``QuerySet.delete()`` de Django, que no pasa por
``unlink``.
"""
from decimal import Decimal

import pytest

from addons.base.models import ResCurrency
from addons.product.models.product_pricelist import ProductPricelist
from addons.sale.models import SaleOrder, SaleOrderLine
from exceptions import UserError, ValidationError
from orm.environments import sudo
from tests.factories.order_factory import STATUS_DRAFT, make_order
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _elevated():
    with sudo():
        yield


def _draft_with_line(user, **line_kwargs):
    order = make_order(status=STATUS_DRAFT, user=user)
    product = make_product(name='U3c producto')
    line = SaleOrderLine.objects.create(
        order=order, product=product, name=product.name,
        price_unit=Decimal('10.00'), product_uom_qty=1, **line_kwargs)
    return order, line


def _pricelist(name):
    """Una tarifa con su divisa obligatoria
    (``odoo19c: addons/product/models/product_pricelist.py:36-41``)."""
    currency, _created = ResCurrency.objects.get_or_create(
        name='MXN', defaults={'symbol': '$'})
    return ProductPricelist.objects.create(name=name, currency_id=currency)


def _reload(record):
    return type(record).objects.get(pk=record.pk)


def test_the_line_state_follows_its_order(user):
    order, line = _draft_with_line(user)
    assert _reload(line).state == SaleOrder.STATE_DRAFT
    order.action_confirm()
    assert _reload(line).state == SaleOrder.STATE_SALE


def test_a_draft_order_can_be_unlinked(user):
    order, _line = _draft_with_line(user)
    order.unlink()
    assert not SaleOrder.objects.filter(pk=order.pk).exists()


def test_a_confirmed_order_cannot_be_unlinked(user):
    order, _line = _draft_with_line(user)
    order.action_confirm()
    with pytest.raises(UserError):
        _reload(order).unlink()
    assert SaleOrder.objects.filter(pk=order.pk).exists()


def test_a_confirmed_line_cannot_be_unlinked(user):
    order, line = _draft_with_line(user)
    order.action_confirm()
    with pytest.raises(UserError):
        _reload(line).unlink()
    assert SaleOrderLine.objects.filter(pk=line.pk).exists()


def test_confirmed_lines_are_not_unlinkable_except_sections(user):
    order, line = _draft_with_line(user)
    note = SaleOrderLine.objects.create(
        order=order, name='U3c nota', display_type='line_note',
        product_uom_qty=0, price_unit=Decimal('0.00'))
    order.action_confirm()
    lines = _reload(order).order_line
    assert lines._check_line_unlink().ids == [line.pk]
    _reload(note).unlink()
    assert not SaleOrderLine.objects.filter(pk=note.pk).exists()


def test_the_pricelist_of_a_confirmed_order_cannot_change(user):
    order, _line = _draft_with_line(user)
    other = _pricelist('U3c otra tarifa')
    _reload(order).write({'pricelist_id': other.pk})
    order.action_confirm()
    second = _pricelist('U3c segunda tarifa')
    with pytest.raises(UserError):
        _reload(order).write({'pricelist_id': second.pk})


def test_prepayment_must_be_a_valid_percentage(user):
    order, _line = _draft_with_line(user)
    order = _reload(order)
    with pytest.raises(ValidationError):
        order.write({'require_payment': True, 'prepayment_percent': 0.0})
    order.write({'require_payment': True, 'prepayment_percent': 0.5})

