from django.apps import AppConfig
from . import checks  # noqa: F401 — register(@payments) corre al importar.


class PaymentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'apps.payments'
    verbose_name       = 'Pagos'
