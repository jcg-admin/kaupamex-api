"""AppConfig — addons.base_setup.

Sirve la superficie de ajustes generales: el formulario ``res.config.settings``
con sus campos (``models/res_config_settings.py``), el proveedor de KPI
(``models/kpi_provider.py``), el añadido a la info de sesión
(``models/ir_http.py``) y el alta de usuarios por correo
(``models/res_users.py``).
"""
import importlib

from django.apps import AppConfig


class BaseSetupConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.base_setup'
    verbose_name = 'Ajustes generales (base_setup)'

    def ready(self):
        """Cuelga sobre modelos ajenos lo que la fuente les declara.

        ``importlib.import_module`` y no un ``import`` al top — excepción #4 de
        ``no-lazy-imports.md``: es una llamada de función, no un statement
        ``import``, y en este punto el registro de modelos ya está poblado.

        Dos enganches, cada uno con su mecanismo:

        - ``res.users`` es un modelo concreto ajeno → ``extend_model``.
        - el cuerpo de sesión lo produce una función de ``web`` → su registro
          de extensores (``register_session_info_extension``), que es el
          ``super()`` de la fuente en este árbol.
        """
        importlib.import_module(
            'addons.base_setup.models.res_users').apply_base_setup_extensions()
        session = importlib.import_module('addons.web.controllers.session')
        ir_http = importlib.import_module('addons.base_setup.models.ir_http')
        session.register_session_info_extension(ir_http.IrHttp.session_info)
