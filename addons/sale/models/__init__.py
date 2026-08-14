"""Modelos del addon ``sale`` (estructura Odoo: un archivo por modelo)."""
from .sale_order import SaleOrder
from .sale_order_line import SaleOrderLine

__all__ = ['SaleOrder', 'SaleOrderLine']
