"""Modelos del addon ``mrp`` (estructura Odoo: un archivo por modelo)."""
from .mrp_bom import MrpBom, MrpBomLine
from .mrp_production import MrpProduction

__all__ = ['MrpBom', 'MrpBomLine', 'MrpProduction']
