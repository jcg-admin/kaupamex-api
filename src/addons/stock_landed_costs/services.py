"""Servicio de costes en destino — addon ``stock_landed_costs``.

Adaptación fiel de Odoo ``compute_landed_cost``
(``stock_landed_costs/models/stock_landed_cost.py:270-315``) y
``button_validate`` (aplicación del ajuste sobre la valoración). Reparte cada
componente de coste sobre los movimientos de recepción según su ``split_method``
y suma el resultado al costo de inventario del producto — cerrando el rastreo
del **costo unitario real de entrega** (precio de compra + flete/aranceles).
"""
from decimal import Decimal

from addons.stock_account import services as valuation
from addons.stock_account.models.product_costing import ProductCosting
from addons.stock_account.models.stock_valuation_layer import StockValuationLayer
from addons.stock_landed_costs.models.stock_valuation_adjustment import (
    StockValuationAdjustment,
)


def _q2(value) -> Decimal:
    return Decimal(value).quantize(Decimal('0.01'))


def _former_cost(move) -> Decimal:
    """Costo de la recepción de ese movimiento (SVL de entrada)."""
    total = Decimal('0.00')
    for svl in StockValuationLayer.objects.filter(stock_move=move, quantity__gt=0):
        total += svl.value
    return total


def compute(cost, moves):
    """Construye las líneas de ajuste y reparte cada componente (Odoo compute_landed_cost).

    Para cada componente de coste, crea una línea de ajuste por movimiento
    objetivo con ``quantity``/``weight``/``volume``/``former_cost``, y reparte
    ``price_unit`` según ``split_method``. Reemplaza cualquier ajuste previo.
    """
    cost.adjustment_lines.all().delete()
    moves = list(moves)

    # Totales base del reparto (sobre los movimientos objetivo).
    total_qty = Decimal('0.00')
    total_weight = Decimal('0.000')
    total_volume = Decimal('0.000')
    former_by_move = {}
    for move in moves:
        qty = move.quantity or move.product_uom_qty
        # H-API — el campo de peso de la variante es ``weight`` (Float,
        # odoo19c: ``product_product.py:154-156``, sobreescribe al de la
        # ficha). ``weight_kg`` no existe en ``product.ProductProduct``;
        # con ``getattr(..., 0)`` el ``SPLIT_BY_WEIGHT`` degradaba en
        # silencio a "todo pesa 0" en vez de fallar.
        weight = qty * Decimal(getattr(move.product, 'weight', 0) or 0)
        volume = qty * Decimal(getattr(move.product, 'volume', 0) or 0)
        former = _former_cost(move)
        former_by_move[move.id] = (qty, weight, volume, former)
        total_qty += qty
        total_weight += weight
        total_volume += volume
    total_cost = sum(v[3] for v in former_by_move.values()) or Decimal('0.00')
    total_line = len(moves)

    for line in cost.cost_lines.all():
        for move in moves:
            qty, weight, volume, former = former_by_move[move.id]
            additional = _split_value(
                line, qty, weight, volume, former,
                total_qty, total_weight, total_volume, total_cost, total_line,
            )
            StockValuationAdjustment.objects.create(
                cost=cost, cost_line=line, move=move, product=move.product,
                quantity=qty, weight=weight, volume=volume, former_cost=former,
                additional_landed_cost=additional, final_cost=_q2(former + additional),
            )
    return cost.adjustment_lines.all()


def _split_value(line, qty, weight, volume, former,
                 total_qty, total_weight, total_volume, total_cost, total_line):
    """Reparte ``line.price_unit`` a esta línea según el método (Odoo split_method).

    Si el denominador del método es cero, cae a reparto igual (mismo fallback
    que Odoo con el ``else`` final).
    """
    price = Decimal(line.price_unit)
    method = line.split_method
    LineCls = line.__class__
    if method == LineCls.SPLIT_BY_QUANTITY and total_qty:
        return _q2(qty * (price / total_qty))
    if method == LineCls.SPLIT_BY_WEIGHT and total_weight:
        return _q2(weight * (price / total_weight))
    if method == LineCls.SPLIT_BY_VOLUME and total_volume:
        return _q2(volume * (price / total_volume))
    if method == LineCls.SPLIT_BY_COST and total_cost:
        return _q2(former * (price / total_cost))
    # equal (o denominador cero → fallback igual).
    return _q2(price / total_line) if total_line else Decimal('0.00')


def validate(cost):
    """Aplica el ajuste sobre la valoración (Odoo button_validate).

    Por cada ajuste con coste adicional, crea una SVL de revaluación
    (``quantity=0``, ``value=additional``) ligada al movimiento y — en AVCO —
    sube el ``standard_price`` del producto. Deja el documento en ``done``.
    """
    for adj in cost.adjustment_lines.all():
        if adj.additional_landed_cost == 0:
            continue
        StockValuationLayer.objects.create(
            product=adj.product, quantity=Decimal('0.00'),
            unit_cost=Decimal('0.0000'), value=_q2(adj.additional_landed_cost),
            remaining_qty=Decimal('0.00'),
            remaining_value=_q2(adj.additional_landed_cost),
            stock_move=adj.move,
            description=f'Coste en destino: {cost.name or cost.pk}',
        )
        _bump_avco(adj.product)
    cost.state = cost.STATE_DONE
    cost.save(update_fields=['state', 'updated_at'])
    return cost


def _bump_avco(product):
    """Recalcula el AVCO del producto tras la revaluación (Odoo _update_standard_price)."""
    costing = ProductCosting.for_product(product)
    if costing.cost_method != ProductCosting.COST_AVERAGE:
        return
    qty = valuation._product_qty_svl(product)
    value = valuation._product_value_svl(product)
    if qty > 0:
        costing.standard_price = (value / qty).quantize(Decimal('0.0001'))
        costing.save(update_fields=['standard_price', 'updated_at'])
