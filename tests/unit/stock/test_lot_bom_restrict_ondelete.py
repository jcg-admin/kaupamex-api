"""Lotes y listas de materiales con ``ondelete='restrict'`` por defecto.

≙ ``odoo19c: addons/stock/models/stock_lot.py:44-48`` y
``addons/mrp/models/mrp_bom.py:31-34``: Many2one obligatorios sin
``ondelete``, cuyo defecto es ``restrict`` (``odoo/orm/
fields_relational.py:274-282``). Diseño: ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/
product-lot-bom-restrict-ondelete.md``.

Cada caso deja al padre protegido sólo por la fila del campo medido.
"""
from decimal import Decimal

import pytest
from django.db.models import ProtectedError

from addons.mrp.models import MrpBom
from addons.product.models import ProductProduct, ProductTemplate
from addons.stock.models import StockLot

pytestmark = pytest.mark.django_db


def _template(name):
    return ProductTemplate.objects.create(name=name,
                                          list_price=Decimal('1.00'))


def test_deleting_a_product_with_a_lot_is_refused():
    variant = ProductProduct.objects.create(product_tmpl=_template('Serie'))
    lot = StockLot.objects.create(name='LOT-P', product=variant)
    with pytest.raises(ProtectedError):
        ProductProduct.objects.filter(pk=variant.pk).delete()
    assert StockLot.objects.filter(pk=lot.pk).exists()


def test_deleting_a_template_with_a_bom_is_refused():
    template = _template('Ensamble')
    bom = MrpBom.objects.create(product_tmpl=template)
    with pytest.raises(ProtectedError):
        ProductTemplate.objects.filter(pk=template.pk).delete()
    assert MrpBom.objects.filter(pk=bom.pk).exists()


def test_a_template_without_dependents_can_be_deleted():
    template = _template('Suelto')
    ProductTemplate.objects.filter(pk=template.pk).delete()
    assert not ProductTemplate.objects.filter(pk=template.pk).exists()
