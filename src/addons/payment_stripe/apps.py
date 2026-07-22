from django.apps import AppConfig


class PaymentStripeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.payment_stripe'
    verbose_name = 'Provider Stripe'
