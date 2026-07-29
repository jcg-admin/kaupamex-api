import importlib

from django.apps import AppConfig


class SaleConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.sale'
    verbose_name       = 'Ventas (sale.order)'

    def ready(self):
        # Inscribe el resolutor de audiencia "compradores de un producto" en
        # el registro de ``mail`` (T-035). ``importlib.import_module`` es la
        # excepción #4 sancionada para ``ready()``.
        importlib.import_module(f'{self.name}.audience')
