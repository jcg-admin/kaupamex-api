"""AppConfig — ``addons.purchase_requisition``.

A diferencia de ``purchase_stock``, este addon **declara tres modelos propios**
(``purchase.requisition``, ``purchase.requisition.line``,
``purchase.order.group``), que Django registra al importar ``models/``. Lo que
va por ``ready()`` son sólo las **extensiones** de modelos ajenos.

``importlib.import_module`` es la **excepción #4** de ``no-lazy-imports.md``:
una llamada de función, no un statement ``import``, así que el gate AST la deja
pasar. En tiempo de import del paquete el registro aún no está poblado y
colgar un campo sobre ``product.ProductSupplierinfo`` fallaría con
``AppRegistryNotReady``.
"""
import importlib

from django.apps import AppConfig


class PurchaseRequisitionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.purchase_requisition'
    label = 'purchase_requisition'
    verbose_name = 'Acuerdos de compra (purchase_requisition)'

    #: Módulos que extienden modelos de OTROS addons — ≙ los ``_inherit``.
    #: módulo → nombre de la función que ``ready()`` invoca.
    #:
    #: ``purchase.py`` aparece aquí **y** en ``models/__init__.py``: declara
    #: ``PurchaseOrderGroup`` (modelo propio, se importa temprano) y además
    #: extiende ``purchase.order``/``purchase.order.line`` (se aplica tarde).
    #:
    #: ``res_config_settings.py`` NO aparece: está NO PORTADO, con su bloqueo
    #: medido en el docstring. Los dos asistentes de ``wizard/`` tampoco:
    #: declaran clases propias sin tabla, no cuelgan nada de nadie.
    _EXTENSIONES = {
        'addons.purchase_requisition.models.purchase':
            'apply_purchase_requisition_purchase_extensions',
        'addons.purchase_requisition.models.product':
            'apply_purchase_requisition_product_extensions',
    }

    def ready(self):
        """Aplica lo que ``purchase_requisition`` cuelga de modelos ajenos."""
        for module_path, function_name in self._EXTENSIONES.items():
            getattr(importlib.import_module(module_path), function_name)()
