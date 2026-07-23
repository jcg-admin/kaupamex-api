from django.apps import AppConfig


class SaleStockConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.sale_stock'
    verbose_name       = 'Venta ↔ inventario (sale_stock)'
