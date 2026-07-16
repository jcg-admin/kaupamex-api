import importlib

from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.addons.orders'
    verbose_name = 'Órdenes'

    def ready(self):
        # Signal wiring. No puede ser un `import` top-level de apps.py
        # porque apps.addons.orders.signals (vía downstream handlers) llega a
        # importar modelos antes de que el app registry este listo
        # (AppRegistryNotReady). Excepcion #3 de no-lazy-imports.md
        # (constraint de lifecycle, no ciclo de codigo): se difiere con
        # importlib.import_module — `import importlib` queda visible al
        # top del modulo.
        importlib.import_module('apps.addons.orders.signals')
