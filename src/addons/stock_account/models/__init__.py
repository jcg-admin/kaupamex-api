"""Modelos del addon ``stock_account`` — valoración de inventario.

Adaptación de Odoo ``stock_account`` (verificado en 18 y 19): la capa de
valoración (``StockValuationLayer``) y el costeo por producto
(``ProductCosting``) que permiten rastrear el costo unitario real de cada
entrada/salida de inventario (estándar / FIFO / AVCO).
"""
from addons.stock_account.models.product_costing import ProductCosting
from addons.stock_account.models.stock_valuation_layer import StockValuationLayer

__all__ = [
    'ProductCosting',
    'StockValuationLayer',
]
