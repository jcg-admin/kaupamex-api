from django.apps import AppConfig


class SalePurchaseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.sale_purchase'
    verbose_name       = 'Venta ↔ compra (sale_purchase)'
