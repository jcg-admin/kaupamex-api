"""Servicios de subcontratación — addon ``mrp_subcontracting``.

Adaptación fiel del flujo de costo de Odoo ``mrp_subcontracting`` (verificado en
18 y 19): en subcontratación la fabricación la hace un tercero, así que el
**costo unitario real** del producto terminado absorbe los **componentes
enviados** al subcontratista **más el servicio de subcontratación** (el precio
pagado al subcontratista, que en Odoo llega por la ``purchase.order`` — aquí se
pasa como ``service_cost``).

Reutiliza la maquinaria de valoración de ``stock_account`` (SVL): igual que
``mrp.services.produce``, pero (1) los componentes se consumen desde la
**ubicación del subcontratista** y (2) la "mano de obra" interna se sustituye por
el **servicio de subcontratación** externo. Las BoM de subcontratación no tienen
operaciones/workorders (constraint ``_check_subcontracting_no_operation`` de
Odoo, o18:20-24), así que no hay ``labor_cost`` interno.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError

from addons.mrp.models.mrp_production_move import MrpProductionMove
from addons.stock.models.stock_move import StockMove
from addons.stock_account import services as valuation


def subcontract_generate_moves(production, subcontractor_location,
                               production_location, dest_location):
    """Genera los movimientos de la orden de subcontratación desde la BoM.

    - Componentes: ``subcontractor_location → production_location`` por cada línea
      de BoM (ya están en poder del subcontratista).
    - Terminado: ``production_location → dest_location`` (regresa a stock interno).
    """
    if production.bom is None:
        raise ValidationError('La orden requiere una BoM para generar movimientos.')

    # Sin ``name``: ``stock.move`` no declara ese campo en la fuente — ver la
    # nota de ``mrp/services.py::generate_moves``, mismo criterio.
    for line in production.bom.bom_line_ids.all():
        qty = line.product_qty * production.product_qty
        move = StockMove.objects.create(
            product=line.product, product_uom_qty=qty,
            location=subcontractor_location, location_dest=production_location,
        )
        MrpProductionMove.objects.create(
            production=production, move=move, role=MrpProductionMove.ROLE_RAW,
        )

    finished = StockMove.objects.create(
        product=production.product,
        product_uom_qty=production.product_qty,
        location=production_location, location_dest=dest_location,
    )
    MrpProductionMove.objects.create(
        production=production, move=finished, role=MrpProductionMove.ROLE_FINISHED,
    )
    return production


def subcontract_produce(production, service_cost):
    """Produce una orden de subcontratación valuando el flujo de costo.

    Consume los componentes (salida valuada → costo real de componentes), suma el
    ``service_cost`` (el servicio pagado al subcontratista), y recibe el terminado
    con ``unit_cost = (componentes + servicio) / product_qty``. Devuelve ese costo
    unitario — el **costo real de subcontratación** del producto.

    Réplica del efecto de ``_cal_price`` de Odoo cuando la producción es de
    subcontratación: el ``subcontracting cost`` sustituye a la mano de obra.
    """
    if production.state not in (production.STATE_CONFIRMED, production.STATE_PROGRESS):
        raise ValidationError('Solo una orden confirmada/en progreso se produce.')

    service_cost = Decimal(service_cost)
    components_cost = Decimal('0.00')
    for move in production.move_raw_ids():
        move._action_confirm()
        move._action_assign()
        move._action_done()
        layer = valuation.value_move(move)
        if layer is not None:
            components_cost += abs(layer.value)

    total_cost = components_cost + service_cost
    qty = production.product_qty or Decimal('1.00')
    unit_cost = (total_cost / qty).quantize(Decimal('0.0001'))

    for move in production.move_finished_ids():
        move._action_confirm()
        move.quantity = move.product_uom_qty
        move._action_done()
        valuation.value_move(move, unit_cost=unit_cost)

    production.state = production.STATE_DONE
    production.save(update_fields=['state', 'updated_at'])
    return unit_cost
