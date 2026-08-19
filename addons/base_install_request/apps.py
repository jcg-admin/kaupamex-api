"""AppConfig — addons.base_install_request.

Sin modelos ni señales que registrar: ver
``models/base_module_install_request.py`` para el veredicto completo
(bloqueado en su totalidad — mismo hallazgo raíz que
``addons.base_import_module``: no hay instalador de módulos en runtime en
esta plataforma).
"""
from django.apps import AppConfig


class BaseInstallRequestConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.base_install_request'
    verbose_name = 'Solicitud de activación de módulo (bloqueado — ver docstring)'
