"""``product.template.uom_id`` y ``product.uom.uom_id``: nombre de la fuente.

≙ ``odoo19c: addons/product/models/product_template.py:118`` y
``odoo19c: addons/product/models/product_uom.py:13``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-template-uom-id.md``.

*Métrica:* el nombre y la columna de los dos campos, la delegación en la
variante y la conversión de unidad de una regla de precio fijo, que lee la
unidad del producto por nombre.
*Ciega a:* los otros nombres de ``product.uom`` (``product``, ``company``),
que el diseño declara con su sucesor.
"""
import pytest

from addons.product.models import (
    ProductPricelist, ProductPricelistItem, ProductProduct, ProductTemplate,
    ProductUom)
from addons.product.models.product_pricelist_item import COMPUTE_FIXED
from addons.uom.models import Uom

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('model', [ProductTemplate, ProductUom])
def test_uom_id_keeps_the_source_name_and_column(model):
    assert model._meta.get_field('uom_id').column == 'uom_id'


def test_the_variant_delegates_uom_id_to_its_template():
    unit = Uom.objects.create(name='Unidad ptu', relative_factor=1.0)
    template = ProductTemplate.objects.create(name='Plantilla ptu',
                                              uom_id=unit)
    variant = ProductProduct.objects.create(product_tmpl_id=template)
    assert variant.uom_id == unit


def test_a_fixed_rule_converts_its_price_to_the_requested_unit():
    unit = Uom.objects.create(name='Unidad ptu2', relative_factor=1.0)
    dozen = Uom.objects.create(name='Docena ptu2', relative_factor=12.0,
                               relative_uom_id=unit)
    template = ProductTemplate.objects.create(name='Por unidad ptu',
                                              uom_id=unit)
    variant = ProductProduct.objects.create(product_tmpl_id=template)
    rule = ProductPricelistItem.objects.create(
        pricelist_id=ProductPricelist.objects.create(name='Tarifa ptu'),
        compute_price=COMPUTE_FIXED, fixed_price=1)
    assert rule.compute(variant, to_uom=dozen) == pytest.approx(12.0)
