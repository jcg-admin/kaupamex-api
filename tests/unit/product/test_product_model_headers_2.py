"""Cabeceras de cinco modelos de ``product``.

≙ ``odoo19c: addons/product/models/product_attribute.py:8-12``,
``product_combo.py:8-10``, ``product_combo_item.py:8-10``,
``product_tag.py:8-10`` y ``product_uom.py:9-11``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-model-headers-batch-2.md``.

*Métrica:* los atributos de clase de cada modelo.
*Ciega a:* las cinco cabeceras que exigen renombrar campos, que el diseño
declara con su sucesor.
"""
import pytest

from addons.product.models import (
    ProductAttribute, ProductCombo, ProductComboItem, ProductTag, ProductUom)

HEADERS = [
    (ProductAttribute, {'_name': 'product.attribute',
                        '_description': 'Product Attribute',
                        '_order': 'sequence, id'}),
    (ProductCombo, {'_name': 'product.combo',
                    '_description': 'Product Combo',
                    '_order': 'sequence, id'}),
    (ProductComboItem, {'_name': 'product.combo.item',
                        '_description': 'Product Combo Item',
                        '_check_company_auto': True}),
    (ProductTag, {'_name': 'product.tag',
                  '_description': 'Product Tag',
                  '_order': 'sequence, id'}),
    (ProductUom, {'_name': 'product.uom',
                  '_description': 'Link between products and their UoMs',
                  '_rec_name': 'barcode'}),
]


@pytest.mark.parametrize('model, header', HEADERS,
                         ids=[h['_name'] for _, h in HEADERS])
def test_the_header_is_the_reference(model, header):
    for name, value in header.items():
        assert model.__dict__[name] == value
