"""Modelos del addon ``stock`` — inventario (adaptación de Odoo ``stock``).

Expone la máquina de movimientos de inventario adaptada fielmente de Odoo
(verificada en 18 y 19): ubicaciones, existencias (quants), movimientos con
reservación, transferencias (pickings) y reglas de aprovisionamiento.
"""
from addons.stock.models.stock_location import StockLocation
from addons.stock.models.stock_lot import StockLot
from addons.stock.models.stock_move import StockMove
from addons.stock.models.stock_picking import StockPicking
from addons.stock.models.stock_quant import StockQuant
from addons.stock.models.stock_rule import StockRule

__all__ = [
    'StockLocation',
    'StockLot',
    'StockMove',
    'StockPicking',
    'StockQuant',
    'StockRule',
]
