"""Lo que ``sale`` cuelga en ``account.move.line`` para copiarla.

Adaptación de ``odoo19c: addons/sale/models/account_move_line.py:36-39``
(LGPL-3 según su ``__manifest__.py``: copia y adaptación con atribución). El
resto de la clase de la fuente tiene su hogar en otros módulos de ``sale``;
este archivo porta el override de ``_copy_data_extend_business_fields``, que
encadena con :func:`~orm.method_chain.wrap_method` sobre la base de
``account``. Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/
designs/account-copy-data-business-fields.md``.
"""
from django.apps import apps

from orm.method_chain import wrap_method

#: La cabecera de la clase de la fuente (``odoo19c: :9``), como constante:
#: el archivo extiende con ``wrap_method`` y no tiene clase que la lleve.
_inherit = 'account.move.line'


def _copy_data_extend_business_fields(self, previous, values):
    """≙ ``_copy_data_extend_business_fields`` (``odoo19c: :36-39``).

    ``sale_line_ids`` es aquí el inverso del ``Many2many invoice_lines`` de
    la línea de pedido, sobre la misma tabla ``sale_order_line_invoice_rel``
    que la fuente declara.
    """
    # OVERRIDE to copy the 'sale_line_ids' field as well.
    previous(values)
    values['sale_line_ids'] = [(6, None, self.sale_line_ids.ids)]


def apply_sale_account_move_line_extensions():
    """La invoca ``SaleConfig.ready()``."""
    wrap_method(apps.get_model('account', 'AccountMoveLine'),
                '_copy_data_extend_business_fields',
                _copy_data_extend_business_fields)
