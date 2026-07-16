"""AppConfig — apps.modules.finance (MOD-028: modulo financiero, UC-FIN-01..08)."""
from django.apps import AppConfig


class FinanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.modules.finance'
    verbose_name = 'Finanzas'
