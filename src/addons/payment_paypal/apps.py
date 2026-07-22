from django.apps import AppConfig


class PaymentPaypalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.payment_paypal'
    verbose_name = 'Provider PayPal'
