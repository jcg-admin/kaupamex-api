"""AppConfig — addons.base_automation (Odoo base_automation)."""
import importlib

from django.apps import AppConfig


class BaseAutomationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.base_automation'
    verbose_name = 'Reglas de automatización'

    def ready(self):
        # Excepción #4 de no-lazy-imports: registro en ready() vía
        # importlib (llamada, no statement).
        # - models/signals.py: reemplazo Django-nativo de
        #   _register_hook/_unregister_hook (ver su docstring).
        # - models/ir_actions_server.py: chain_method sobre IrActionsServer
        #   e IrCron (≙ los dos _inherit de la referencia).
        importlib.import_module('addons.base_automation.models.signals')
        importlib.import_module('addons.base_automation.models.ir_actions_server')
