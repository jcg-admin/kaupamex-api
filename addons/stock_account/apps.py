"""AppConfig — ``addons.stock_account``.

Además de sus dos modelos propios (``StockValuationLayer``, ``ProductCosting``),
este addon **extiende modelos ajenos** — los ``_inherit`` de la fuente. Esas
extensiones se aplican en ``ready()``, cuando el registro de modelos ya está
poblado: colgar un campo sobre ``stock.StockMove`` en tiempo de import rompe con
``AppRegistryNotReady``.

Mismo patrón que ``PurchaseStockConfig``: ``importlib.import_module`` es la
**excepción número 4** de ``no-lazy-imports.md`` — una llamada de función, no un
statement ``import``, así que el gate AST la deja pasar.
"""
import importlib

from django.apps import AppConfig


class StockAccountConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.stock_account'
    verbose_name = 'Valoración de inventario (stock_account)'

    #: Módulos que extienden modelos de OTROS addons — ≙ los ``_inherit`` de la
    #: fuente. módulo → nombre de la función que ``ready()`` invoca.
    #:
    #: La referencia declara 17 módulos en ``models/__init__.py``; aquí hay uno,
    #: y su docstring lleva la cobertura medida. Sucesor de los que faltan:
    #: tarea **#151**.
    _EXTENSIONS = {
        'addons.stock_account.models.stock_move':
            'apply_stock_account_stock_move_extensions',
    }

    def ready(self):
        """Aplica lo que ``stock_account`` cuelga de modelos ajenos."""
        for module_path, function_name in self._EXTENSIONS.items():
            getattr(importlib.import_module(module_path), function_name)()
