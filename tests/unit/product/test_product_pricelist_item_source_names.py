"""Los cuatro nombres de la fuente en ``product.pricelist.item``.

≙ ``odoo19c: addons/product/models/product_pricelist_item.py:19``
(``pricelist_id``), ``:77`` (``product_tmpl_id``), ``:82`` (``product_id``)
y ``:104`` (``base_pricelist_id``). Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-pricelist-item-source-names.md``.

*Métrica:* el nombre y la columna de cada campo, y la aplicabilidad de una
regla de variante y de producto, que compara ids.
*Ciega a:* la selección entre reglas de varias tarifas
(``_compute_price_rule``, etapa 4 del diseño
``product-pricelist-cluster``), que no cambia con el nombre.
"""
import pytest

from addons.base.models.res_currency import ResCurrency

from addons.product.models import (
    ProductPricelist, ProductPricelistItem, ProductProduct, ProductTemplate)
from addons.product.models.product_pricelist_item import (
    APPLIED_PRODUCT, APPLIED_VARIANT)
from orm.environments import env

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('name', [
    'pricelist_id', 'product_tmpl_id', 'product_id', 'base_pricelist_id'])
def test_the_field_keeps_the_source_name_and_column(name):
    assert ProductPricelistItem._meta.get_field(name).column == name


@pytest.fixture
def variant():
    template = ProductTemplate.objects.create(name='Regla pli-src')
    return ProductProduct.objects.create(product_tmpl_id=template)


@pytest.fixture
def pricelist():
    currency, _ = ResCurrency.objects.get_or_create(
        name='MXN', defaults={'symbol': '$'})
    return ProductPricelist.objects.create(name='Tarifa pli-src',
                                           currency_id=currency)


def test_a_variant_rule_matches_its_variant_only(variant, pricelist):
    other = ProductProduct.objects.create(
        product_tmpl_id=ProductTemplate.objects.create(name='Otra pli-src'))
    rule = ProductPricelistItem.objects.create(
        pricelist_id=pricelist, applied_on=APPLIED_VARIANT,
        product_id=variant)
    assert rule._is_applicable_for(variant, 1.0)
    assert not rule._is_applicable_for(other, 1.0)


def test_a_product_rule_matches_the_variants_of_its_template(
        variant, pricelist):
    rule = ProductPricelistItem.objects.create(
        pricelist_id=pricelist, applied_on=APPLIED_PRODUCT,
        product_tmpl_id=variant.product_tmpl_id)
    assert rule._is_applicable_for(variant, 1.0)


def test_the_pricelist_lists_its_rules(pricelist):
    rule = env()['product.pricelist.item'].create(
        [{'pricelist_id': pricelist.pk}])
    assert pricelist.item_ids == rule
