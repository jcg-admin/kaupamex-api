"""Modelos del addon ``stock_landed_costs`` — costes en destino.

Adaptación de Odoo ``stock_landed_costs`` (verificado en 18 y 19): reparte
fletes/aranceles/seguros sobre los productos de una recepción y los suma a su
costo unitario de inventario, haciendo rastreable el costo unitario real de
entrega.
"""
from addons.stock_landed_costs.models.stock_landed_cost import StockLandedCost
from addons.stock_landed_costs.models.stock_landed_cost_line import StockLandedCostLine
from addons.stock_landed_costs.models.stock_valuation_adjustment import StockValuationAdjustment

__all__ = [
    'StockLandedCost',
    'StockLandedCostLine',
    'StockValuationAdjustment',
]
