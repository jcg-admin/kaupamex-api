"""Configuración de la app ``crm``."""
import importlib

from django.apps import AppConfig


class CrmConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.crm'
    verbose_name       = 'CRM (crm.lead)'

    #: Los módulos que cuelgan algo de un modelo AJENO — ≙ los archivos que la
    #: referencia declara con ``_inherit`` sobre un modelo de otro addon. Cada
    #: uno expone ``apply_crm_extensions()``.
    _EXTENSIONS = (
        'addons.crm.models.calendar',
        'addons.crm.models.crm_team',
        'addons.crm.models.crm_team_member',
        'addons.crm.models.digest',
        'addons.crm.models.ir_config_parameter',
        'addons.crm.models.mail_activity',
        'addons.crm.models.res_config_settings',
        'addons.crm.models.res_partner',
        'addons.crm.models.res_users',
        'addons.crm.models.utm',
    )

    def ready(self):
        """Aplica lo que ``crm`` cuelga de modelos ajenos.

        Es el momento equivalente al ``_inherit`` de la referencia: aquí el
        registro de modelos ya está poblado.

        ``importlib.import_module`` y no un ``import`` al top porque en tiempo
        de import de este módulo el registro aún no está listo
        (``AppRegistryNotReady``). Es la excepción #4 de ``no-lazy-imports``,
        que sanciona exactamente esta forma: una llamada de función, no un
        statement ``import``. Mismo patrón que ``AccountConfig.ready()``.
        """
        for ruta in self._EXTENSIONS:
            importlib.import_module(ruta).apply_crm_extensions()
