"""AppConfig — ``addons.base_install_request``.

Cuelga la acción de ``models/ir_module_module.py`` sobre ``base.IrModule``. El
asistente (``models/base_module_install_request.py``) sigue bloqueado en su
parte de instalación en caliente — ver su docstring para el veredicto por
símbolo, ya acotado.
"""
import importlib

from django.apps import AppConfig


class BaseInstallRequestConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.base_install_request'
    verbose_name = 'Solicitud de activación de módulo'

    #: Módulos que cuelgan algo de un modelo AJENO — ≙ los archivos que la
    #: referencia declara con ``_inherit``. Cada uno expone
    #: ``apply_base_install_request_extensions()``.
    _EXTENSIONS = (
        'addons.base_install_request.models.ir_module_module',
    )

    def ready(self):
        """Aplica lo que este addon cuelga de ``base``.

        ``importlib.import_module`` y no un ``import`` al top — excepción #4 de
        ``no-lazy-imports.md``: es una llamada de función, no un statement
        ``import``, así que el gate AST la deja pasar y el registro de modelos
        ya está poblado en este punto.
        """
        for path in self._EXTENSIONS:
            importlib.import_module(path).apply_base_install_request_extensions()
