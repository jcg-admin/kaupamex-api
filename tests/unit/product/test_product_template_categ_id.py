"""``product.template.categ_id``: el nombre de la fuente de la categoría.

≙ ``odoo19c: addons/product/models/product_template.py:81``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-template-categ-id.md``.

*Métrica:* el nombre y la columna del campo, la delegación en la variante y
una regla de tarifa de categoría, que lo lee por nombre.
*Ciega a:* los otros nombres de la plantilla (``company``, ``uom``), que el
diseño declara con su sucesor.
"""
import pytest

from addons.product.models import (
    ProductCategory, ProductPricelist, ProductPricelistItem, ProductProduct,
    ProductTemplate)
from addons.product.models.product_pricelist_item import APPLIED_CATEGORY
from addons.base.models.res_currency import ResCurrency


def _pricelist_currency():
    """La moneda obligatoria de una tarifa
    (``odoo19c: addons/product/models/product_pricelist.py:36-41``)."""
    currency, _ = ResCurrency.objects.get_or_create(
        name='MXN', defaults={'symbol': '$'})
    return currency


pytestmark = pytest.mark.django_db


def test_categ_id_keeps_the_source_name_and_column():
    assert ProductTemplate._meta.get_field('categ_id').column == 'categ_id'


def test_the_variant_delegates_categ_id_to_its_template():
    category = ProductCategory.objects.create(name='Cat ptc')
    template = ProductTemplate.objects.create(name='Plantilla ptc',
                                              categ_id=category)
    variant = ProductProduct.objects.create(product_tmpl_id=template)
    assert variant.categ_id == category


def test_a_category_rule_reaches_the_products_of_its_branch():
    root = ProductCategory.objects.create(name='Raiz ptc')
    child = ProductCategory.objects.create(name='Hija ptc', parent_id=root)
    other = ProductCategory.objects.create(name='Otra ptc')
    template = ProductTemplate.objects.create(name='En rama ptc',
                                              categ_id=child)
    stranger = ProductTemplate.objects.create(name='Fuera ptc',
                                              categ_id=other)
    rule = ProductPricelistItem.objects.create(
        pricelist_id=ProductPricelist.objects.create(
            currency_id=_pricelist_currency(), name='Tarifa ptc'),
        applied_on=APPLIED_CATEGORY, categ_id=root)
    assert rule._is_applicable_for(template, 1.0)
    assert not rule._is_applicable_for(stranger, 1.0)
