"""Modelos del addon ``mrp`` (estructura Odoo: un archivo por modelo)."""
from .mrp_bom import MrpBom, MrpBomLine
from .mrp_production import MrpProduction
from .mrp_production_move import MrpProductionMove
from .mrp_routing_workcenter import MrpRoutingWorkcenter
from .mrp_workcenter import MrpWorkcenter
from .mrp_workorder import MrpWorkorder

__all__ = [
    'MrpBom',
    'MrpBomLine',
    'MrpProduction',
    'MrpProductionMove',
    'MrpRoutingWorkcenter',
    'MrpWorkcenter',
    'MrpWorkorder',
]
