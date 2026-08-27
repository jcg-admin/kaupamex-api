"""AppConfig — addons.base_import_module.

Sin modelos ni señales que registrar: ver
``models/base_import_module.py`` para el veredicto completo (bloqueado
en su totalidad — divergencia arquitectónica, no pieza ausente puntual).
Existe como app Django válida únicamente para que el addon sea
localizable en ``addons/`` con la misma forma que sus hermanos —
``INSTALLED_APPS`` no necesita incluirlo mientras no aporte nada.
"""
from django.apps import AppConfig


class BaseImportModuleConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.base_import_module'
    verbose_name = 'Importación de módulos (bloqueado — ver docstring)'
