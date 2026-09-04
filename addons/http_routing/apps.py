"""AppConfig — ``addons.http_routing`` (familia ``web`` de la referencia)."""
import importlib

from django.apps import AppConfig


class HttpRoutingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.http_routing'
    verbose_name = 'Enrutado web (slug legible, idioma en la URL)'

    #: Módulos que extienden modelos de OTRO addon — ≙ ``_inherit``. Los tres
    #: archivos de modelo de la fuente extienden ``ir.http``, ``ir.qweb`` y
    #: ``res.lang``, los tres declarados en ``base``. Mismo patrón que
    #: ``WebConfig._EXTENSIONES``.
    _EXTENSIONS = (
        ('addons.http_routing.models.ir_http', 'apply_http_routing_extensions'),
        ('addons.http_routing.models.ir_qweb', 'apply_ir_qweb_extensions'),
        ('addons.http_routing.models.res_lang', 'apply_res_lang_extensions'),
    )

    def ready(self):
        """Cuelga las extensiones de ``http_routing`` sobre modelos de ``base``.

        ``importlib.import_module`` y no un ``import`` al top — excepción #4
        de ``no-lazy-imports.md``: es una llamada de función, no un statement
        ``import``, así que el gate AST la deja pasar. Mismo patrón que
        ``WebConfig.ready()``.
        """
        for path, entry_point in self._EXTENSIONS:
            getattr(importlib.import_module(path), entry_point)()
