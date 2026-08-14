"""AppConfig — addons.digest (Odoo digest)."""
import importlib

from django.apps import AppConfig


class DigestConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.digest'
    verbose_name = 'Digests de KPIs periódicos'

    def ready(self):
        # Excepción #4 de no-lazy-imports: registro de signals en ready()
        # vía importlib (llamada, no statement). La señal replica el
        # ``create()`` override de ``digest/models/res_users.py`` de la
        # referencia (auto-suscripción al digest por defecto).
        importlib.import_module('addons.digest.models.signals')
