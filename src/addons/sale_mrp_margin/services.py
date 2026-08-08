"""Servicio del addon ``sale_mrp_margin`` — costo de BoM para el margen.

Adaptación de Odoo ``sale_mrp_margin`` (``odoo19c:``, LGPL-3,
``odoo-tools@622ddc2a``; presente también en ``odoo18c:`` — gobierna 19),
cuyo manifiesto declara *"Handle BoM prices to compute sale margin"* y **no
trae un solo modelo**: sólo ``__manifest__.py`` + tests
(``test_sale_mrp_flow.py``, 224 líneas). En la fuente el comportamiento
emerge gratis — los movimientos de stock valuados de los COMPONENTES del kit
alimentan el costo que ``sale_stock_margin`` pondera.

Este árbol no tiene movimientos valuados (declarado en
``sale_stock_margin/services.py``), así que la adaptación hace explícito lo
que allá es emergente: el costo de un producto con BoM tipo **kit**
(``phantom``) es la suma del costo estándar de sus componentes. Mismo
espíritu behavior-only que su hermano ``sale_stock_margin``.
"""
from decimal import ROUND_HALF_UP, Decimal

from addons.mrp.models.mrp_bom import MrpBom
from addons.sale_margin.models.sale_order_line_margin import SaleOrderLineMargin


def bom_unit_cost(product) -> Decimal | None:
    """Costo unitario derivado de la BoM kit del producto, o ``None``.

    Suma ``componente.standard_price × qty`` sobre las líneas de la primera
    BoM **kit** (``phantom``) activa del producto — variante primero, la
    plantilla como respaldo, igual que ``_bom_find`` de la referencia
    prioriza la variante. Normaliza por ``product_qty`` de la BoM (una BoM
    que produce N unidades reparte su costo entre N). Sin BoM kit, ``None``:
    el llamador cae al costo estándar, que es el comportamiento sin este
    addon instalado.
    """
    if product is None:
        return None
    bom = (MrpBom.objects.filter(
        active=True, type=MrpBom.TYPE_PHANTOM, product=product)
        .order_by('sequence', 'id').first())
    if bom is None:
        bom = (MrpBom.objects.filter(
            active=True, type=MrpBom.TYPE_PHANTOM,
            product__isnull=True, product_tmpl=product.product_tmpl)
            .order_by('sequence', 'id').first())
    if bom is None:
        return None
    total = Decimal('0.00')
    for line in bom.bom_line_ids.select_related('product'):
        component_cost = (line.product.standard_price
                          if line.product and line.product.standard_price
                          is not None else Decimal('0.00'))
        total += component_cost * line.product_qty
    produced = bom.product_qty or Decimal('1.00')
    return (total / produced).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def recompute_purchase_price_with_bom(line) -> Decimal:
    """Fija el snapshot de costo del margen usando el costo de BoM si lo hay.

    La composición con ``sale_margin``: si el producto de la línea tiene BoM
    kit, su costo real es el de los componentes — el ``standard_price`` del
    kit suele ser 0 (nadie lo compra como tal), y con él el margen saldría
    inflado. Sin BoM, delega al camino estándar de ``sale_margin``.
    """
    cost = bom_unit_cost(line.product)
    margin, _created = SaleOrderLineMargin.objects.get_or_create(line=line)
    if cost is None:
        return margin.capture_purchase_price()
    margin.purchase_price = cost
    margin.save(update_fields=['purchase_price', 'updated_at'])
    return cost
