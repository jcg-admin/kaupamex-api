"""Una línea de compra en memoria recalcula precio y fecha al cambiar la
cantidad.

≙ ``odoo19c: odoo/orm/fields.py:1807-1847`` (``Field.__set__``: sobre un
``NewId`` protege los calculados del campo, escribe y llama a
``modified``), ``odoo/orm/models.py:6756-6838`` (``modified`` marca el
calculado almacenado en ``transaction.tocompute``) y
``odoo/orm/fields.py:1642-1666`` (``__get__`` de un calculado almacenado
procesa lo pendiente antes de leer la caché). La dependencia la declara
``addons/purchase/models/purchase_order_line.py:404`` —
``@api.depends('product_qty', 'product_uom_id', 'company_id',
'order_id.partner_id')``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
new-line-recompute-flow.md``.
"""
import datetime
from decimal import Decimal

import pytest

from addons.base.models import ResCompany, ResPartner
from addons.product.models import ProductSupplierinfo
from addons.uom.models import Uom
from orm.environments import company_scope, env, sudo
from orm.registry import MODELS_BY_NAME
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.django_db
LINE = 'purchase.order.line'


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


@pytest.fixture
def company():
    company = ResCompany.objects.create(name='Compras en memoria 0122')
    with company_scope(company.pk):
        yield company


@pytest.fixture
def setup(company):
    unit = Uom.objects.create(name='Units new 0122', relative_factor=1.0)
    vendor = ResPartner.objects.create(name='Proveedor en memoria 0122')
    product = make_product(uom=unit, name='Insumo en memoria 0122')
    for min_qty, price, delay in ((1, '7', 1), (10, '5', 10)):
        ProductSupplierinfo.objects.create(
            partner_id=vendor, product_tmpl_id=product.product_tmpl,
            min_qty=min_qty, price=Decimal(price), delay=delay)
    [order] = MODELS_BY_NAME['purchase.order'].create(
        [{'partner_id': vendor.pk, 'company_id': company.pk,
          'currency_id': company.currency_id}])
    return order, product


def _new_line(order, product, qty):
    return env()[LINE].new({'order_id': order.id, 'product_id': product.pk,
                            'product_qty': Decimal(qty)})


def _days_after_order(line):
    return (line.date_planned.date() - line.order_id.date_order.date()).days


def test_the_initial_values_come_from_the_matching_seller(setup):
    line = _new_line(*setup, '1')
    assert line.price_unit == Decimal('7')
    assert _days_after_order(line) == 1


def test_raising_the_quantity_switches_to_the_bigger_seller(setup):
    line = _new_line(*setup, '1')
    assert line.price_unit == Decimal('7')
    line.product_qty = Decimal('10')
    assert line.price_unit == Decimal('5')
    assert _days_after_order(line) == 10


def test_lowering_it_back_restores_the_first_seller(setup):
    line = _new_line(*setup, '10')
    assert line.price_unit == Decimal('5')
    line.product_qty = Decimal('1')
    assert line.price_unit == Decimal('7')
    assert _days_after_order(line) == 1


def test_a_field_outside_the_dependencies_does_not_recompute(setup):
    """Control negativo: ``name`` no está en ``@api.depends`` del cálculo."""
    line = _new_line(*setup, '1')
    assert line.price_unit == Decimal('7')
    line.price_unit = Decimal('42')
    line.name = 'Otra descripción'
    assert line.price_unit == Decimal('42')


def test_the_persisted_line_follows_the_same_contract(setup):
    """Control de compatibilidad: la fila guardada ya recalculaba."""
    order, product = setup
    [line] = MODELS_BY_NAME[LINE].create([{
        'order_id': order.id, 'product_id': product.pk,
        'product_qty': Decimal('1')}])
    assert line.price_unit == Decimal('7')
    line.write({'product_qty': Decimal('10')})
    assert line.price_unit == Decimal('5')
    assert isinstance(line.date_planned, datetime.datetime)
