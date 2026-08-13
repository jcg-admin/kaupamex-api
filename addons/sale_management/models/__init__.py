"""Modelos del addon ``sale_management`` (estructura Odoo: un archivo por modelo)."""
from .sale_order_template import SaleOrderTemplate
from .sale_order_template_line import SaleOrderTemplateLine

__all__ = ['SaleOrderTemplate', 'SaleOrderTemplateLine']
