"""AppConfig — ``addons.base_import``.

Este addon no declara modelos **todavía**: lo portado hasta aquí es la capa
de heurísticas puras (``models/date_patterns.py``), que no toca el registro
de modelos ni extiende ninguno ajeno. Por eso ``ready()`` no aplica ninguna
extensión — a diferencia de ``base_iban`` o ``base_sparse_field``, que sí
cuelgan sobre modelos de otro addon y por eso lo hacen ahí.

Cuando entren ``base_import.mapping`` (modelo persistente) y
``base_import.import`` (el asistente transitorio), este AppConfig gana su
bloque de extensiones con el mismo criterio que sus hermanos.
"""
from django.apps import AppConfig


class BaseImportConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.base_import'
    label = 'base_import'
    verbose_name = 'Base — Importación de archivos'
