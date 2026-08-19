"""AppConfig del addon ``website``."""
import importlib

from django.apps import AppConfig, apps

from orm.inherits import apply_inherits
from orm.registry import MODELS_BY_NAME


class WebsiteConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.website'
    verbose_name = 'Website (páginas de contenido)'

    def ready(self):
        """Instala la delegación ``_inherits`` y la extensión de la vista.

        Dos cableados, no uno:

        1. La extensión que el addon del sitio cuelga sobre ``ir.ui.view``
           (≙ su ``_inherit``, tarea #565) — va **primero** porque
           ``website.page`` lee por delegación lo que ella instala.
        2. La delegación ``_inherits`` de ``website.page`` a esa vista.

        Equivale a ``_inherits = {'ir.ui.view': 'view_id'}`` de la referencia
        (``odoo19c: addons/website/models/website_page.py:26``): la página
        expone los campos de su ``ir.ui.view`` como propios.

        Mismo patrón que ``BaseConfig.ready()`` con ``res.users`` →
        ``res.partner``: **el par delegado→FK sale del atributo, no de aquí**
        (tarea #385) — se lee de ``WebsitePage._inherits``, así que cambiar
        la cabecera cambia el cableado. ``apps.get_model`` es una llamada,
        no un ``import`` (excepción #4 de ``no-lazy-imports.md``), y por lo
        mismo la extensión de la vista se alcanza con
        ``importlib.import_module``: en tiempo de import de este módulo el
        registro aún no está listo. Mismo patrón que ``WebsiteSaleConfig``.
        """
        view_module = importlib.import_module(
            'addons.website.models.ir_ui_view')
        view_module.apply_website_ir_ui_view_extensions()

        page = apps.get_model('website', 'WebsitePage')
        for model_name, fk_name in page._inherits.items():
            apply_inherits(
                page,
                MODELS_BY_NAME[model_name],
                fk_name,
            )
