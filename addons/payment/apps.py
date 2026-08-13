import importlib

from django.apps import AppConfig


class PaymentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.payment'
    verbose_name = 'Pagos (payment framework)'

    def ready(self):
        # Registra los receptores de notificación de este addon (T-035).
        # ``importlib.import_module`` —no un ``import`` statement— es la
        # excepción #4 sancionada para ``ready()``: el gate AST prohíbe
        # imports dentro de funciones y no tiene ``# noqa``.
        importlib.import_module(f'{self.name}.handlers')
