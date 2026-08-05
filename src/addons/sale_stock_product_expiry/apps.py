from django.apps import AppConfig


class SaleStockProductExpiryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.sale_stock_product_expiry'
    verbose_name       = 'Caducidad en líneas de venta (sale_stock_product_expiry)'
