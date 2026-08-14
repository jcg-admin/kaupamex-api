from django.apps import AppConfig


class ProductConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.product'
    verbose_name = 'Producto — configuración (base del monolito modular product)'
