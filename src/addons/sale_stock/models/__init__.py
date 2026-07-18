"""Modelos del addon ``sale_stock`` (estructura Odoo: un archivo por modelo)."""
from .sale_order import SaleOrderDelivery
from .sale_order_line import SaleOrderLineDelivery

__all__ = ['SaleOrderDelivery', 'SaleOrderLineDelivery']
