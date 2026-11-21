"""``product_tmpl_id``: el nombre de la fuente en variante, BoM y línea.

≙ ``odoo19c: addons/product/models/product_product.py:42``,
``addons/mrp/models/mrp_bom.py:31`` y
``addons/product/models/product_template_attribute_line.py:19``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-tmpl-id.md``.

*Métrica:* el nombre y la columna de los tres campos, la delegación de
``_inherits`` y la coherencia variante-plantilla de una tarifa, que compara
ids.
*Ciega a:* ``ProductTemplate.uom_id``, que el diseño declara con su sucesor.
"""
import pytest
from orm.environments import env

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


def test_a_variant_of_another_template_is_cleared_on_change():
    """≙ ``_onchange_product_tmpl_id``: la variante que no pertenece a la
    plantilla se limpia en el formulario."""
    template = ProductTemplate.objects.create(name='Una ptid')
    other = ProductProduct.objects.create(
        product_tmpl_id=ProductTemplate.objects.create(name='Otra ptid'))
    info = env()['product.supplierinfo'].new({
        'partner_id': ResPartner.objects.create(name='Prov2 ptid').pk,
        'product_tmpl_id': template.pk, 'product_id': other.pk})
    info._onchange_product_tmpl_id()
    assert not info.product_id
