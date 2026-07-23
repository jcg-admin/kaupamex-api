"""Modelos del addon ``product_expiry`` — caducidad de productos y lotes.

Extiende la base ``stock`` (DEC-SALE-01): la config de caducidad del producto
(``ProductExpiryConfig``) y las fechas del lote (``StockLotExpiry``), con la
estrategia de remoción FEFO en ``services``.
"""
from addons.product_expiry.models.product_expiry_config import ProductExpiryConfig
from addons.product_expiry.models.stock_lot_expiry import StockLotExpiry

__all__ = [
    'ProductExpiryConfig',
    'StockLotExpiry',
]
