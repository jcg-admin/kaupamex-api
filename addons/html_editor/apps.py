"""AppConfig — ``addons.html_editor`` (familia ``web`` de la referencia)."""
import importlib

from django.apps import AppConfig


class HtmlEditorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.html_editor'
    verbose_name = 'HTML Editor'

    #: Módulos que extienden modelos de OTRO addon — ≙ ``_inherit``. Los seis
    #: archivos de modelo de la fuente que llevan ``_inherit`` publican cada
    #: uno su ``apply_html_editor_extensions()``. Mismo patrón que
    #: ``WebConfig._EXTENSIONES`` y ``HttpRoutingConfig._EXTENSIONS``.
    #:
    #: El orden **no** es indiferente: ``ir_websocket`` envuelve una función de
    #: ``bus`` y ``ir_qweb_fields`` cuelga sobre ``base``; los seis son
    #: idempotentes (``chain_method``/``wrap_method`` lo son por su recorrido
    #: de marcas), así que una segunda invocación —autoreloader, o un test que
    #: las llame— no duplica nada.
    _EXTENSIONS = (
        'addons.html_editor.models.models',
        'addons.html_editor.models.ir_attachment',
        'addons.html_editor.models.ir_http',
        'addons.html_editor.models.ir_qweb_fields',
        'addons.html_editor.models.ir_ui_view',
        'addons.html_editor.models.ir_websocket',
    )

    def ready(self):
        """Cuelga las extensiones de ``html_editor`` sobre ``base`` y ``bus``.

        ``importlib.import_module`` y no un ``import`` al top — excepción #4
        de ``no-lazy-imports.md``: es una llamada de función, no un statement
        ``import``, así que el gate AST la deja pasar.
        """
        for path in self._EXTENSIONS:
            importlib.import_module(path).apply_html_editor_extensions()
