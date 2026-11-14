import importlib

from django.apps import AppConfig


class PurchaseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.purchase'
    verbose_name = 'Compras (purchase)'

    def ready(self):
        # Cuelga lo que ``purchase`` extiende en ResCompany (po_lock,
        # po_double_validation, po_double_validation_amount) — ≙
        # ``purchase/models/res_company.py``. ``importlib.import_module`` es
        # la excepción #4 sancionada para ``ready()``.
        importlib.import_module(
            f'{self.name}.models.res_company'
        ).apply_purchase_extensions()
