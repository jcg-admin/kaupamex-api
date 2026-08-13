import importlib
from django.apps import AppConfig


class PaymentStripeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.payment_stripe'
    verbose_name = 'Provider Stripe'

    def ready(self):
        # Importa el módulo del gateway para que su ``register_gateway``
        # corra e inscriba el provider en el núcleo (T-033). Se usa
        # ``importlib.import_module`` —no un ``import`` statement— porque el
        # gate ``check_no_lazy_imports`` prohíbe imports dentro de funciones
        # y no tiene ``# noqa``: es la excepción #4 sancionada para
        # ``AppConfig.ready()``.
        importlib.import_module(f'{self.name}.gateway')
