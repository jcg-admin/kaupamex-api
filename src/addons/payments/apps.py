import importlib
from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.payments'
    verbose_name       = 'Pagos'

    def ready(self):
        # Registra los receptores de las señales de ``sale``; ``importlib`` es
        # la excepción #4 sancionada para ``ready()`` (no-lazy-imports).
        importlib.import_module(f'{self.name}.handlers')
