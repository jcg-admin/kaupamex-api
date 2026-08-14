"""Modelos del addon ``purchase`` (estructura Odoo: un archivo por modelo)."""
from .purchase_order import PurchaseOrder
from .purchase_order_line import PurchaseOrderLine

__all__ = ['PurchaseOrder', 'PurchaseOrderLine']
