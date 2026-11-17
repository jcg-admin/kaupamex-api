"""Lo que ``purchase`` cuelga en ``res.partner``.

≙ ``_inherit = 'res.partner'``.

Adaptación de ``odoo19c: addons/purchase/models/res_partner.py`` (LGPL-3
según su ``__manifest__.py``: copia y adaptación con atribución).

*Métrica:* símbolos del cuerpo de ``class ResPartner``, contados por AST: 9.
Se porta 1 de 9 en este pase: ``buyer_id`` (``:45``), que
``purchase.order.onchange_partner_id`` (``odoo19c:
addons/purchase/models/purchase_order.py:455-456``) lee para fijar el
comprador de la orden.

Los ocho restantes tienen unidad registrada en el plan de continuación, no
se omiten:

- ``property_purchase_currency_id`` (``:31-33``) — unidad
  ``purchase-product-actions-0397``;
- ``_compute_purchase_order_count``, ``purchase_order_count``,
  ``purchase_warn_msg``, ``receipt_reminder_email``,
  ``reminder_date_before_receipt`` y ``_compute_application_statistics_hook``
  (``:9-29,34-49``) — unidad ``purchase-partner-extension-0535``.

``_inherit`` se expresa colgando el campo de ``addons.base.models.ResPartner``
con :func:`~orm.model_classes.extend_model`, el mismo mecanismo que
``res_company.py`` de este addon. La columna la crea la migración de ``base``
``0117_respartner_buyer_id``, como ``0115`` hace con los campos de la empresa.
"""
from django.db import models

import fields
from orm.model_classes import extend_model


def apply_purchase_partner_extensions():
    """≙ ``_inherit = 'res.partner'`` de ``purchase``.

    La invoca ``PurchaseConfig.ready()``, no el import: en tiempo de import el
    registro de modelos aún no está poblado.
    """
    extend_model(
        'base', 'ResPartner',
        campos={
            #: ≙ ``buyer_id = fields.Many2one('res.users', string='Buyer')``
            #: (``:45``). ``ondelete`` por omisión de la fuente: ``set null``.
            'buyer_id': fields.Many2one(
                'base.ResUsers', verbose_name='Buyer', null=True, blank=True,
                on_delete=models.SET_NULL, related_name='+',
                db_column='buyer_id'),
        },
    )
