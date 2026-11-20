"""``product.template.uom_id`` toma la unidad por defecto.

≙ ``uom_id`` (``odoo19c: addons/product/models/product_template.py:118-121``)
con ``default=_get_default_uom_id`` (``:34-36``), que devuelve
``uom.product_uom_unit``.

*Métrica:* la unidad de una plantilla creada sin ``uom_id``.
*Ciega a:* la obligatoriedad en la columna (``NOT NULL``), que espera a que
las filas antiguas sin unidad se rellenen.
"""
import pytest

from addons.base.models import IrModelData
from addons.product.models import ProductTemplate

pytestmark = pytest.mark.django_db


def test_a_template_without_unit_takes_the_default_unit():
    template = ProductTemplate.objects.create(name='Sin unidad')
    assert template.uom_id.id == IrModelData._xmlid_to_res_id(
        'uom.product_uom_unit')


def test_an_explicit_unit_is_kept():
    unit = IrModelData.ref('uom.product_uom_dozen')
    template = ProductTemplate.objects.create(name='Docena', uom_id=unit)
    assert template.uom_id == unit
