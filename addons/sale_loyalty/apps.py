import importlib

from django.apps import AppConfig


class SaleLoyaltyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.sale_loyalty'
    verbose_name       = 'Venta ↔ cupones (sale_loyalty)'

    def ready(self):
        # Registra los receptores de las señales de ``sale`` (T-034). Se usa
        # ``importlib.import_module`` —no un ``import`` statement— porque el
        # gate ``check_no_lazy_imports`` prohíbe imports dentro de funciones
        # y no tiene ``# noqa``: excepción #4 sancionada para ``ready()``.
        importlib.import_module(f'{self.name}.handlers')
