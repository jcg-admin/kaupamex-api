"""``product.uom`` como ``BaseModel``, completo.

≙ ``odoo19c: addons/product/models/product_uom.py``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-uom-basemodel.md``.

*Métrica:* el rechazo de un código que ya usa una variante al crear y al
escribir por el ORM, y el nombre para mostrar según ``show_variant_name``.
*Ciega a:* el índice parcial de ``barcode``, que es esquema y no conducta.
"""
import pytest

from addons.product.models import ProductUom
from addons.uom.models.uom_uom import Uom
from exceptions import ValidationError
from orm.environments import env
from orm.models import BaseModel

pytestmark = pytest.mark.django_db

PACKAGING = 'product.uom'


def _variant(name='PU Producto', barcode=False):
    [template] = env()['product.template'].create([{'name': name}])
    variant = template.product_variant_ids
    if barcode:
        variant.write({'barcode': barcode})
    return variant


def _packaging(variant, barcode):
    unit = Uom.objects.create(name=f'PU Caja {barcode}', relative_factor=1.0)
    [packaging] = env()[PACKAGING].create([{
        'uom_id': unit.pk, 'product_id': variant.id, 'barcode': barcode}])
    return packaging


def test_the_packaging_is_a_basemodel():
    assert issubclass(ProductUom, BaseModel)


def test_a_variant_barcode_cannot_be_reused_on_create():
    variant = _variant(barcode='7500000000017')
    with pytest.raises(ValidationError):
        _packaging(variant, '7500000000017')


def test_a_variant_barcode_cannot_be_reused_on_write():
    variant = _variant(barcode='7500000000024')
    packaging = _packaging(variant, '7500000000031')
    with pytest.raises(ValidationError):
        packaging.write({'barcode': '7500000000024'})


def test_the_display_name_shows_the_variant_on_request():
    variant = _variant(name='PU Mostrar')
    packaging = _packaging(variant, '7500000000048')
    shown = packaging.with_context(show_variant_name=True)
    assert shown.display_name == (
        f'7500000000048 for: {variant.display_name}')


def test_the_display_name_is_the_barcode_by_default():
    variant = _variant(name='PU Defecto')
    packaging = _packaging(variant, '7500000000055')
    assert packaging.display_name == '7500000000055'
