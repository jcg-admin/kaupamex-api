"""Lo que ``purchase`` cuelga a la empresa — ≙ ``_inherit = 'res.company'``.

Adaptación de ``odoo19c: addons/purchase/models/res_company.py`` (LGPL-3
según su ``__manifest__.py``: copia y adaptación con atribución).

*Métrica:* campos del cuerpo de ``class ResCompany``, contados por AST: 3.
Se portan 3 de 3. ``_inherit`` se expresa colgando los campos de
``addons.base.models.ResCompany`` con :func:`~orm.model_classes.extend_model`,
el mismo mecanismo que ``sale/models/res_company.py``.

Sus consumidores en la fuente son ``purchase.order._approval_allowed`` y
``button_approve`` (``purchase_order.py:615-619,1251-1260``).
"""
from decimal import Decimal

import fields
from orm.model_classes import extend_model

#: ≙ el ``selection`` de ``po_lock`` (``odoo19c: :10-14``).
PO_LOCK = [
    ('edit', 'Allow to edit purchase orders'),
    ('lock', 'Confirmed purchase orders are not editable'),
]
#: ≙ el ``selection`` de ``po_double_validation`` (``odoo19c: :16-20``).
PO_DOUBLE_VALIDATION = [
    ('one_step', 'Confirm purchase orders in one step'),
    ('two_step', 'Get 2 levels of approvals to confirm a purchase order'),
]


def apply_purchase_extensions():
    """≙ ``_inherit = 'res.company'`` de ``purchase``.

    La invoca ``PurchaseConfig.ready()``, no el import: en tiempo de import
    el registro de modelos aún no está poblado.
    """
    extend_model(
        'base', 'ResCompany',
        campos={
            'po_lock': fields.Selection(
                PO_LOCK, 'Purchase Order Modification', default='edit',
                max_length=4,
                help_text=(
                    'Purchase Order Modification used when you want to '
                    'purchase order editable after confirm'),
            ),
            'po_double_validation': fields.Selection(
                PO_DOUBLE_VALIDATION, 'Levels of Approvals',
                default='one_step', max_length=8,
                help_text='Provide a double validation mechanism for '
                          'purchases',
            ),
            'po_double_validation_amount': fields.Monetary(
                'Double validation amount', max_digits=16, decimal_places=2,
                default=Decimal('5000'),
                help_text='Minimum amount for which a double validation is '
                          'required',
            ),
        },
    )
