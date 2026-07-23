"""Tests — addons ``mrp`` + ``sale_mrp`` (venta de producto fabricado → MO)."""
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from addons.catalogue.models import Product
from addons.mrp.models import MrpBom, MrpBomLine, MrpProduction
from addons.sale.models import SaleOrder, SaleOrderLine
from addons.sale_mrp.models import SaleOrderLineProduction

pytestmark = pytest.mark.integration


def _product(name, sku):
    return Product.objects.create(
        name=name, slug=sku.lower(), sku=sku, price=Decimal('100.00'),
    )


def test_mrp_production_state_machine(db):
    prod = _product('Mesa', 'MSA-001')
    mo = MrpProduction.objects.create(product=prod, product_qty=Decimal('2'))
    assert mo.state == MrpProduction.STATE_DRAFT
    mo.action_confirm()
    assert mo.state == MrpProduction.STATE_CONFIRMED
    assert mo.name.startswith('MO-')
    mo.button_mark_done()
    assert mo.state == MrpProduction.STATE_DONE
    with pytest.raises(ValidationError):
        mo.action_cancel()  # una MO terminada no se cancela


def test_bom_and_lines(db):
    table = _product('Mesa', 'MSA-002')
    leg = _product('Pata', 'PAT-001')
    top = _product('Tablero', 'TAB-001')
    bom = MrpBom.objects.create(product=table, product_qty=Decimal('1'))
    MrpBomLine.objects.create(bom=bom, product=leg, product_qty=Decimal('4'), sequence=1)
    MrpBomLine.objects.create(bom=bom, product=top, product_qty=Decimal('1'), sequence=2)
    assert bom.bom_line_ids.count() == 2
    assert bom.type == MrpBom.TYPE_NORMAL
    assert list(bom.bom_line_ids.values_list('product__sku', flat=True)) == ['PAT-001', 'TAB-001']


def test_generate_production_from_sale_line(db):
    table = _product('Mesa', 'MSA-003')
    bom = MrpBom.objects.create(product=table, product_qty=Decimal('1'))
    order = SaleOrder.objects.create()
    line = SaleOrderLine.objects.create(
        order=order, product=table, price_unit=Decimal('100.00'), product_uom_qty=3,
    )
    link = SaleOrderLineProduction.generate_production(line)
    assert line.production_link.production == link.production
    assert link.production.product == table
    assert link.production.product_qty == Decimal('3')
    assert link.production.bom == bom  # tomó la BoM activa del producto


def test_explode_kit_phantom_bom(db):
    kit = _product('Kit oficina', 'KIT-001')
    penc = _product('Lápiz', 'LAP-001')
    note = _product('Cuaderno', 'CUA-001')
    bom = MrpBom.objects.create(product=kit, type=MrpBom.TYPE_PHANTOM, product_qty=Decimal('1'))
    MrpBomLine.objects.create(bom=bom, product=penc, product_qty=Decimal('3'))
    MrpBomLine.objects.create(bom=bom, product=note, product_qty=Decimal('2'))
    # 5 kits → 15 lápices, 10 cuadernos.
    exploded = SaleOrderLineProduction.explode_kit(kit, 5)
    as_dict = {p.sku: q for p, q in exploded}
    assert as_dict == {'LAP-001': Decimal('15.00'), 'CUA-001': Decimal('10.00')}
    # Producto sin BoM kit → sin explosión.
    assert SaleOrderLineProduction.explode_kit(penc, 3) == []
