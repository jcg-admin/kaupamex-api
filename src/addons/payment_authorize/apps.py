from django.apps import AppConfig


class PaymentAuthorizeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.payment_authorize'
    verbose_name = 'Provider Authorize.Net'
