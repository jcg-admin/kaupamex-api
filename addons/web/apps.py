"""AppConfig — addons.web (familia ``web`` de la referencia)."""
import importlib

from django.apps import AppConfig


class WebConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.web'
    verbose_name = 'Web — sesión del cliente'

    #: Módulos que extienden modelos de OTRO addon — ≙ ``_inherit``. Mismo
    #: patrón que ``AccountQrCodeSepaConfig._EXTENSIONES``: ``ir_http.py``
    #: cuelga ``is_a_bot``/``bots`` sobre ``base.IrHttp`` (H-API-369);
    #: ``res_partner.py`` cuelga ``_build_vcard``/``_get_vcard_file`` sobre
    #: ``base.ResPartner``.
    _EXTENSIONES = (
        'addons.web.models.ir_http',
        'addons.web.models.ir_model',
        'addons.web.models.ir_ui_menu',
        'addons.web.models.ir_ui_view',
        'addons.web.models.res_partner',
        'addons.web.models.res_users',
        'addons.web.models.res_users_settings',
    )

    def ready(self):
        """Cuelga las extensiones de ``web`` sobre modelos de ``base``.

        ``importlib.import_module`` y no un ``import`` al top — excepción #4
        de ``no-lazy-imports.md``: es una llamada de función, no un
        statement ``import``, así que el gate AST la deja pasar. Mismo
        patrón que ``AccountConfig.ready()``/``AccountQrCodeSepaConfig.ready()``.
        """
        for ruta in self._EXTENSIONES:
            importlib.import_module(ruta).apply_web_extensions()
