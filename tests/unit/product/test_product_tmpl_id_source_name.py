"""``product_tmpl_id``: el nombre de la fuente en variante, BoM y línea.

≙ ``odoo19c: addons/product/models/product_product.py:42``,
``addons/mrp/models/mrp_bom.py:31`` y
``addons/product/models/product_template_attribute_line.py:19``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-tmpl-id.md``.

*Métrica:* el nombre y la columna de los tres campos, la delegación de
``_inherits`` y la coherencia variante-plantilla de una tarifa, que compara
ids.
*Ciega a:* ``ProductTemplate.uom``, que el diseño declara con su sucesor.
"""
import pytest
from django.core.exceptions import ValidationError

from addons.base.models import ResPartner
from addons.mrp.models import MrpBom
from addons.product.models import (
    ProductProduct, ProductSupplierinfo, ProductTemplate,
    ProductTemplateAttributeLine)

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('model', [
    ProductProduct, MrpBom, ProductTemplateAttributeLine])
def test_product_tmpl_id_keeps_the_source_name_and_column(model):
    assert model._meta.get_field(
        'product_tmpl_id').column == 'product_tmpl_id'


def test_the_variant_reads_its_template_through_inherits():
    template = ProductTemplate.objects.create(name='Plantilla ptid')
    variant = ProductProduct.objects.create(product_tmpl_id=template)
    assert variant.product_tmpl_id == template
    assert variant.name == 'Plantilla ptid'


def test_a_tariff_accepts_a_variant_of_its_template():
    template = ProductTemplate.objects.create(name='Propia ptid')
    variant = ProductProduct.objects.create(product_tmpl_id=template)
    info = ProductSupplierinfo(
        partner_id=ResPartner.objects.create(name='Prov ptid'),
        product_tmpl_id=template, product_id=variant)
    info.clean()


def test_a_tariff_refuses_a_variant_of_another_template():
    template = ProductTemplate.objects.create(name='Una ptid')
    other = ProductProduct.objects.create(
        product_tmpl_id=ProductTemplate.objects.create(name='Otra ptid'))
    info = ProductSupplierinfo(
        partner_id=ResPartner.objects.create(name='Prov2 ptid'),
        product_tmpl_id=template, product_id=other)
    with pytest.raises(ValidationError):
        info.clean()
