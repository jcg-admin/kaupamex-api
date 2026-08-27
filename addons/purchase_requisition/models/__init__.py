"""Modelos del addon ``purchase_requisition``.

A diferencia de ``purchase_stock``, este addon **sí declara modelos propios**
—``purchase.requisition``, ``purchase.requisition.line`` y
``purchase.order.group``—, así que este paquete **sí importa**: sin el import,
``ModelBase`` nunca registra las tres clases y no habría tabla que migrar.

Lo que NO se importa aquí son las **extensiones** de modelos ajenos
(``product.supplierinfo``, ``purchase.order``, ``purchase.order.line``): esas
se aplican desde ``PurchaseRequisitionConfig.ready()``, cuando el registro ya
está poblado. Por eso ``product.py`` no aparece en esta lista y sí en
``_EXTENSIONES``, y ``purchase.py`` aparece en las dos — porque declara
``PurchaseOrderGroup`` (modelo propio) **y** extiende la orden.

El orden espeja ``odoo19c: addons/purchase_requisition/models/__init__.py``.
"""
from .purchase import PurchaseOrderGroup
from .purchase_requisition import PurchaseRequisition, PurchaseRequisitionLine

__all__ = [
    'PurchaseOrderGroup',
    'PurchaseRequisition',
    'PurchaseRequisitionLine',
]
