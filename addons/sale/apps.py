import importlib

from django.apps import AppConfig


class SaleConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.sale'
    verbose_name       = 'Ventas (sale.order)'

    def ready(self):
        # Cuelga lo que ``sale`` extiende en ResCompany (quotation_validity_
        # days, tarea #256) ANTES del resolutor de audiencia: la orden lee
        # ese campo al calcular su vigencia, así que tiene que existir en el
        # registro de modelos primero. ``importlib.import_module`` es la
        # excepción #4 sancionada para ``ready()``.
        importlib.import_module(f'{self.name}.models.res_company') \
            .apply_sale_extensions()
        # Inscribe el resolutor de audiencia "compradores de un producto" en
        # el registro de ``mail`` (T-035).
        importlib.import_module(f'{self.name}.audience')
