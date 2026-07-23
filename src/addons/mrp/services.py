"""Servicio de fabricación con valoración — addon ``mrp``.

Integra las órdenes de fabricación con las bases ``stock`` + ``stock_account``:
genera los movimientos de materia prima (``move_raw_ids``) y de producto
terminado (``move_finished_ids``) de la BoM, y al producir valúa el flujo —
el consumo de materia prima como **salida** (costo real de los componentes) y
el terminado como **entrada** con costo = materia prima valuada + mano de obra
(``workorders`` × ``costs_hour``). Réplica del efecto de ``_generate_moves`` +
``_cal_price``/``_run_manufacture`` de Odoo ``mrp`` sobre la valoración.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError

from addons.mrp.models.mrp_production_move import MrpProductionMove
from addons.stock.models.stock_location import StockLocation
from addons.stock.models.stock_move import StockMove
from addons.stock_account import services as valuation


def generate_moves(production, stock_location, production_location):
    """Crea los movimientos de materia prima y de terminado desde la BoM.

    Réplica de ``_generate_raw_moves`` + ``_generate_finished_moves`` de Odoo.
    - Materia prima: ``stock_location → production_location`` por cada línea de
      BoM (qty = componente × ``product_qty``).
    - Terminado: ``production_location → stock_location`` por el producto a
      fabricar (qty = ``product_qty``).
    """
    if production.bom is None:
        raise ValidationError('La orden requiere una BoM para generar movimientos.')

    for line in production.bom.bom_line_ids.all():
        qty = line.product_qty * production.product_qty
        move = StockMove.objects.create(
            name=line.product.name, product=line.product, product_uom_qty=qty,
            location=stock_location, location_dest=production_location,
        )
        MrpProductionMove.objects.create(
            production=production, move=move, role=MrpProductionMove.ROLE_RAW,
        )

    finished = StockMove.objects.create(
        name=production.product.name, product=production.product,
        product_uom_qty=production.product_qty,
        location=production_location, location_dest=stock_location,
    )
    MrpProductionMove.objects.create(
        production=production, move=finished, role=MrpProductionMove.ROLE_FINISHED,
    )
    return production


def produce(production):
    """Produce la orden valuando el flujo (Odoo _cal_price + button_mark_done).

    Consume la materia prima (salida valuada → costo real de componentes), suma
    la mano de obra de las ``workorders``, y recibe el terminado con
    ``unit_cost = (materia prima + mano de obra) / product_qty``. Devuelve ese
    costo unitario — el **costo real de fabricación** del producto.
    """
    if production.state not in (production.STATE_CONFIRMED, production.STATE_PROGRESS):
        raise ValidationError('Solo una orden confirmada/en progreso se produce.')

    raw_cost = Decimal('0.00')
    for move in production.move_raw_ids():
        move._action_confirm()
        move._action_assign()
        move._action_done()
        layer = valuation.value_move(move)
        if layer is not None:
            raw_cost += abs(layer.value)

    labor_cost = production.labor_cost()
    total_cost = raw_cost + labor_cost
    qty = production.product_qty or Decimal('1.00')
    unit_cost = (total_cost / qty).quantize(Decimal('0.0001'))

    for move in production.move_finished_ids():
        move._action_confirm()
        move.quantity = move.product_uom_qty
        move._action_done()
        valuation.value_move(move, unit_cost=unit_cost)

    for wo in production.workorders.all():
        if wo.state != wo.STATE_DONE:
            wo.state = wo.STATE_DONE
            wo.save(update_fields=['state', 'updated_at'])

    production.state = production.STATE_DONE
    production.save(update_fields=['state', 'updated_at'])
    return unit_cost
