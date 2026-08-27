"""Asistentes del addon ``purchase_requisition``.

Los dos son ``TransientModel`` **abstractos y no gestionados**
(``src/orm/models_transient.py:29-36``): no producen tabla ni se registran como
modelo concreto, así que importarlos aquí es inocuo y hace que el símbolo sea
accesible como ``addons.purchase_requisition.wizard.PurchaseRequisition…``.

El orden espeja ``odoo19c: addons/purchase_requisition/wizard/__init__.py``.
"""
from .purchase_requisition_alternative_warning import (
    PurchaseRequisitionAlternativeWarning,
)
from .purchase_requisition_create_alternative import (
    PurchaseRequisitionCreateAlternative,
)

__all__ = [
    'PurchaseRequisitionAlternativeWarning',
    'PurchaseRequisitionCreateAlternative',
]
