from django.apps import AppConfig


class PaymentCustomConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.payment_custom'
    verbose_name = 'Provider Pago personalizado (transferencia/wire)'
