from django.apps import AppConfig


class AnalyticConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.analytic'
    verbose_name       = 'Contabilidad analítica (planes, cuentas, distribución)'
