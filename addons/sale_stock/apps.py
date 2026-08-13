import importlib
from django.apps import AppConfig


class SaleStockConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.sale_stock'
    verbose_name       = 'Venta ↔ inventario (sale_stock)'

    def ready(self):
        # Registra los receptores de las señales de ``sale`` (T-034);
        # ``importlib`` es la excepción #4 sancionada para ``ready()``.
        importlib.import_module(f'{self.name}.handlers')
