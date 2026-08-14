from django.apps import AppConfig


class SaleServiceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.sale_service'
    verbose_name       = 'Líneas de servicio en órdenes (sale_service)'
