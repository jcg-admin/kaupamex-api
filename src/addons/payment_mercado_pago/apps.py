from django.apps import AppConfig
from . import checks  # noqa: F401 — register(@payments) corre al importar.


class PaymentMercadoPagoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.payment_mercado_pago'
    verbose_name = 'Provider Mercado Pago'
