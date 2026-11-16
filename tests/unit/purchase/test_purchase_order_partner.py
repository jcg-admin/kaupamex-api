"""El proveedor de ``purchase.order`` es un ``res.partner``.

≙ ``odoo19c: addons/purchase/models/purchase_order.py:91-94`` y
``purchase_order_line.py:84``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
purchase-order-partner.md``.
"""
import pytest

from addons.base.models import ResCompany, ResPartner
from orm.environments import sudo
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _as_superuser():
    """Los datos de prueba de la referencia se escriben como superusuario."""
    with sudo():
        yield


def _order(partner):
    # ``company_id`` es requerido en la fuente (``purchase_order.py:155``).
    company = ResCompany.objects.create(name='Compras proveedor 0397')
    [order] = MODELS_BY_NAME['purchase.order'].create(
        [{'partner_id': partner.pk, 'company_id': company.pk}])
    return order


def _line(order):
    [line] = MODELS_BY_NAME['purchase.order.line'].create(
        [{'order_id': order.id, 'name': 'Eleke', 'price_unit': 10,
          'product_qty': 1}])
    return line


def test_the_order_partner_is_a_contact():
    field = MODELS_BY_NAME['purchase.order']._meta.get_field('partner_id')
    assert field.related_model is ResPartner


def test_the_line_partner_is_stored():
    field = MODELS_BY_NAME['purchase.order.line']._meta.get_field(
        'partner_id')
    assert field.related_model is ResPartner
    assert field.concrete


def test_a_new_line_copies_the_order_partner():
    vendor = ResPartner.objects.create(name='Proveedor 0397')
    line = _line(_order(vendor))
    assert line.partner_id.id == vendor.pk


def test_changing_the_order_partner_reaches_its_lines():
    first = ResPartner.objects.create(name='Proveedor A 0397')
    second = ResPartner.objects.create(name='Proveedor B 0397')
    order = _order(first)
    line = _line(order)
    order.write({'partner_id': second.pk})
    assert line.partner_id.id == second.pk


def test_the_line_partner_reaches_the_column():
    """El ``store=True`` de la fuente: tras vaciar, la columna lo lleva."""
    vendor = ResPartner.objects.create(name='Proveedor C 0397')
    line = _line(_order(vendor))
    line.flush_recordset()
    model = MODELS_BY_NAME['purchase.order.line']
    assert model.objects.filter(pk=line.id).values_list(
        'partner_id', flat=True)[0] == vendor.pk
