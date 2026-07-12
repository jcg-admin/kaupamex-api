"""AppConfig — apps.geo (catálogos geográficos de referencia).

Aloja catálogos de referencia geográfica reutilizables (códigos postales
SEPOMEX ahora; extensible a otros). Se separa de ``apps.users`` para aislar
un catálogo de referencia de gran volumen del ciclo de vida del modelo de
usuario (party). SOL-016, DEC-02.
"""
from django.apps import AppConfig


class GeoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.geo'
    verbose_name = 'Catálogos geográficos'
