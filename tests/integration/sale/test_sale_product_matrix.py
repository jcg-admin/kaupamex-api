"""Tests — addons ``product_matrix`` + ``sale_product_matrix`` (grilla de variantes)."""
from decimal import Decimal

import pytest

from addons.chartsize.models import ProductVariant, VariantOption, VariantType
from addons.product_matrix.models import ProductMatrixConfig
from addons.sale.models import SaleOrder, SaleOrderLine
from addons.sale_product_matrix.models import SaleOrderMatrix
from addons.catalogue.models import Product

pytestmark = pytest.mark.integration


def _product_with_variants(db):
    product = Product.objects.create(
        name='Playera', slug='playera', sku='PLA-001', price=Decimal('199.00'),
    )
    vtype = VariantType.objects.create(product=product, name='Talla')
    opt_s = VariantOption.objects.create(variant_type=vtype, label='S', slug='s', order=1)
    opt_m = VariantOption.objects.create(variant_type=vtype, label='M', slug='m', order=2)
    var_s = ProductVariant.objects.create(
        product=product, option=opt_s, sku_suffix='S', stock=5,
    )
    var_m = ProductVariant.objects.create(
        product=product, option=opt_m, sku_suffix='M', stock=3,
        price_override=Decimal('219.00'),
    )
    return product, var_s, var_m


def test_matrix_config_default_mode(db):
    product = Product.objects.create(
        name='Gorra', slug='gorra', sku='GOR-001', price=Decimal('99.00'),
    )
    cfg = ProductMatrixConfig.objects.create(product=product)
    assert cfg.add_mode == ProductMatrixConfig.MODE_CONFIGURATOR


def test_build_grid_from_chartsize_variants(db):
    product, var_s, var_m = _product_with_variants(db)
    grid = ProductMatrixConfig.build(product)
    assert grid['header'] == 'Playera'
    assert len(grid['rows']) == 1
    row = grid['rows'][0]
    assert row['type'] == 'Talla'
    labels = [c['label'] for c in row['cells']]
    assert labels == ['S', 'M']
    # Celda M usa el price_override; S cae al precio base del producto.
    prices = {c['label']: c['price'] for c in row['cells']}
    assert prices['S'] == Decimal('199.00')
    assert prices['M'] == Decimal('219.00')
    assert row['cells'][0]['sku'] == 'PLA-001-S'


def test_apply_bulk_lines(db):
    product, var_s, var_m = _product_with_variants(db)
    order = SaleOrder.objects.create()
    lines = SaleOrderMatrix.apply(order, [(var_s, 2), (var_m, 1)])
    assert len(lines) == 2
    assert order.order_line.count() == 2
    assert hasattr(order, 'matrix') and order.matrix.report_grids is True
    line_m = SaleOrderLine.objects.get(order=order, variant=var_m)
    assert line_m.price_unit == Decimal('219.00')
    assert line_m.product_uom_qty == 1


def test_apply_zero_qty_removes_line(db):
    product, var_s, var_m = _product_with_variants(db)
    order = SaleOrder.objects.create()
    SaleOrderMatrix.apply(order, [(var_s, 2), (var_m, 1)])
    # Re-aplicar con S=0 elimina esa línea; M pasa a 4.
    SaleOrderMatrix.apply(order, [(var_s, 0), (var_m, 4)])
    assert order.order_line.count() == 1
    assert not SaleOrderLine.objects.filter(order=order, variant=var_s).exists()
    assert SaleOrderLine.objects.get(order=order, variant=var_m).product_uom_qty == 4
