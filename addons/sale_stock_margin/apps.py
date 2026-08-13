from django.apps import AppConfig


class SaleStockMarginConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.sale_stock_margin'
    verbose_name       = 'Margen ponderado por entrega (sale_stock_margin)'
