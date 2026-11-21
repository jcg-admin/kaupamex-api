"""``allowed_uom_ids`` de ``stock.move`` sobre los Many2many de la plantilla.

``product.template``, ``uom.uom`` y ``product.supplierinfo`` son
``BaseModel``: ``uom_ids`` y ``seller_ids`` de la plantilla son recordsets,
como en la fuente, y la propiedad los leía con ``values_list`` y
``exclude``. Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/
designs/basemodel-reverse-queryset.md``.

≙ ``_compute_allowed_uom_ids``
(``odoo19c: addons/stock/models/stock_move.py``):
la unidad del producto, la de sus empaquetados y la de sus proveedores.

*Métrica:* las unidades admitidas de un movimiento sin guardar.
*Ciega a:* el dominio de la vista que las consume.
"""
from decimal import Decimal

import pytest
from django.apps import apps

from addons.uom.models.uom_uom import Uom
from orm.environments import sudo

pytestmark = pytest.mark.django_db

ProductProduct = apps.get_model('product', 'ProductProduct')
ProductSupplierinfo = apps.get_model('product', 'ProductSupplierinfo')
ProductTemplate = apps.get_model('product', 'ProductTemplate')
ResPartner = apps.get_model('base', 'ResPartner')
StockMove = apps.get_model('stock', 'StockMove')


def test_the_allowed_units_join_product_packaging_and_sellers():
    unit = Uom.objects.create(name='SMU Unidad', relative_factor=1.0)
    box = Uom.objects.create(name='SMU Caja', relative_factor=6.0,
                             relative_uom_id=unit)
    dozen = Uom.objects.create(name='SMU Docena', relative_factor=12.0,
                               relative_uom_id=unit)
    with sudo():
        tmpl = ProductTemplate.objects.create(
            name='SMU Producto', list_price=Decimal('1.00'), uom_id=unit)
        ProductTemplate.objects.get(pk=tmpl.pk).write(
            {'uom_ids': [(6, 0, [box.pk])]})
        variant = ProductProduct.objects.create(product_tmpl_id=tmpl)
        ProductSupplierinfo.objects.create(
            partner_id=ResPartner.objects.create(name='SMU Proveedor'),
            product_tmpl_id=tmpl, price=1.0, product_uom_id=dozen)
        allowed = StockMove(product=variant).allowed_uom_ids
        assert set(allowed.values_list('pk', flat=True)) == {
            unit.pk, box.pk, dozen.pk}
