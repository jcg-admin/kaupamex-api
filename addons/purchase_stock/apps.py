"""AppConfig — ``addons.purchase_stock``.

Todo lo que este addon aporta son **extensiones de modelos ajenos** (los diez
``_inherit`` de la fuente): no declara ningún modelo propio con ``_name`` nuevo.
Por eso ``models/__init__.py`` está vacío de imports y la carga entera pasa por
``ready()``, cuando el registro de modelos ya está poblado y ``add_to_class``
sobre una clase ajena no rompe con ``AppRegistryNotReady``.

Mismo patrón que ``HrRecruitmentConfig``/``AccountFleetConfig``:
``importlib.import_module`` es la **excepción #4** de ``no-lazy-imports.md`` —
una llamada de función, no un statement ``import``, así que el gate AST la deja
pasar.
"""
import importlib

from django.apps import AppConfig


class PurchaseStockConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.purchase_stock'
    label = 'purchase_stock'
    verbose_name = 'Compra ↔ inventario (purchase_stock)'

    #: Módulos que extienden modelos de OTROS addons — ≙ los ``_inherit`` de la
    #: fuente. módulo → nombre de la función que ``ready()`` invoca.
    #:
    #: El orden espeja el de ``odoo19c: addons/purchase_stock/models/
    #: __init__.py``, salvo que aquí faltan los tres módulos **sin código**:
    #: ``account_invoice``, ``account_move_line`` y ``res_config_settings``.
    #: Los tres existen como archivo —el sitio se lee contra la referencia— y
    #: llevan su bloqueo medido en el docstring; no tienen función que invocar.
    #:
    #: ``report/`` y ``wizard/`` no aparecen por lo mismo: sus siete archivos
    #: están NO PORTADOS, cada uno con su medición.
    _EXTENSIONES = {
        'addons.purchase_stock.models.product':
            'apply_purchase_stock_product_extensions',
        'addons.purchase_stock.models.stock_replenish_mixin':
            'apply_purchase_stock_stock_replenish_mixin_extensions',
        'addons.purchase_stock.models.purchase_order':
            'apply_purchase_stock_purchase_order_extensions',
        'addons.purchase_stock.models.purchase_order_line':
            'apply_purchase_stock_purchase_order_line_extensions',
        'addons.purchase_stock.models.res_partner':
            'apply_purchase_stock_res_partner_extensions',
        'addons.purchase_stock.models.res_company':
            'apply_purchase_stock_res_company_extensions',
        'addons.purchase_stock.models.stock':
            'apply_purchase_stock_stock_extensions',
        'addons.purchase_stock.models.stock_move':
            'apply_purchase_stock_stock_move_extensions',
        'addons.purchase_stock.models.stock_reference':
            'apply_purchase_stock_stock_reference_extensions',
        'addons.purchase_stock.models.stock_rule':
            'apply_purchase_stock_stock_rule_extensions',
    }

    def ready(self):
        """Aplica lo que ``purchase_stock`` cuelga de modelos ajenos."""
        for module_path, function_name in self._EXTENSIONES.items():
            getattr(importlib.import_module(module_path), function_name)()
