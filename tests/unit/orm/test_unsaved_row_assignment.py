"""Asignar sobre una fila de Django sin guardar llega a ESA instancia.

≙ ``BaseModel.__setitem__`` (``odoo19c: odoo/orm/models.py:6694``) y
``Field.__set__`` (``odoo19c: odoo/orm/fields.py:1807-1841``): un registro
nuevo recibe el valor en su caché. Aquí una fila sin ``pk`` no se puede
reconstruir por id; reconstruirla crea otra instancia y el valor se pierde.
Reproductor: ``scripts/workbench/orm-continuation-plan-20261103T095630/
designs/purchase-line-price-and-dates.md`` (unidad
``orm-related-scalar-unsaved-0485``).
"""
import pytest

from addons.base.models import ResCompany, ResPartner
from orm.environments import env, sudo
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


@pytest.fixture
def unsaved_line():
    company = ResCompany.objects.create(name='Fila sin guardar 0485')
    vendor = ResPartner.objects.create(name='Proveedor sin guardar 0485')
    [order] = MODELS_BY_NAME['purchase.order'].create(
        [{'partner_id': vendor.pk, 'company_id': company.pk}])
    line = MODELS_BY_NAME['purchase.order.line'](
        order_id=order, name='x', product_qty=1, price_unit=1)
    return order, line


def test_a_scalar_related_resolves_on_an_unsaved_row(unsaved_line):
    order, line = unsaved_line
    assert line.date_order == order.date_order


def test_a_many2one_related_resolves_on_an_unsaved_row(unsaved_line):
    """Control: el ``related`` ``Many2one`` ya resolvía."""
    order, line = unsaved_line
    assert line.currency_id == order.currency_id


def test_update_on_an_unsaved_row_reaches_the_instance(unsaved_line):
    _order, line = unsaved_line
    line.update({'name': 'nuevo', 'sequence': 7})
    assert (line.name, line.sequence) == ('nuevo', 7)


def test_item_assignment_on_an_unsaved_row_reaches_the_instance(
        unsaved_line):
    _order, line = unsaved_line
    line['sequence'] = 9
    assert line.sequence == 9


def test_assignment_inside_a_compute_reaches_the_instance(unsaved_line):
    """Dentro de un cómputo la fila está protegida, y es el caso que
    perdía el valor: ``_reset_price_unit`` lo asigna con ``update``."""
    _order, line = unsaved_line
    field = line._fields['sequence']
    with env().protecting([field], (None,)):
        line.update({'sequence': 11})
    assert line.sequence == 11
