import importlib

from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.addons.notifications'
    verbose_name = 'Notificaciones'

    def ready(self):
        # Signal wiring. No puede ser un `import` top-level de apps.py
        # porque apps.addons.notifications.signals importa modelos
        # (apps.addons.orders/payments/returns/support) antes de que el app
        # registry este listo (AppRegistryNotReady). Excepcion #3 de
        # no-lazy-imports.md (constraint de lifecycle, no ciclo de
        # codigo): se difiere con importlib.import_module — `import
        # importlib` queda visible al top del modulo.
        importlib.import_module('apps.addons.notifications.handlers')
        importlib.import_module('apps.addons.notifications.signals')
