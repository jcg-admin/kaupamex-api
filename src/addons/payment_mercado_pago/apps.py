import importlib
from django.apps import AppConfig
from . import checks  # noqa: F401 — register(@payments) corre al importar.


class PaymentMercadoPagoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.payment_mercado_pago'
    verbose_name = 'Provider Mercado Pago'

    def ready(self):
        # Importa el módulo del gateway para que su ``register_gateway``
        # corra e inscriba el provider en el núcleo (T-033). Se usa
        # ``importlib.import_module`` —no un ``import`` statement— porque el
        # gate ``check_no_lazy_imports`` prohíbe imports dentro de funciones
        # y no tiene ``# noqa``: es la excepción #4 sancionada para
        # ``AppConfig.ready()``.
        importlib.import_module(f'{self.name}.gateway')
