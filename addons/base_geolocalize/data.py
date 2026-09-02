"""Datos semilla del addon — equivalente nativo de ``data/data.xml``.

Fiel a ``base_geolocalize/data/data.xml`` de Odoo
(``geoprovider_open_street``, ``geoprovider_google_map``). El **orden importa**:
``BaseGeocoder._get_provider()`` cae en ``openstreetmap`` cuando el parámetro
``base_geolocalize.geo_provider`` no está seteado, porque toma
``order_by('pk').first()``.

Spec único que consumen la data-migration ``0002_seed_geo_providers`` (arranque)
y ``seed()`` (re-aplicación sobre el modelo vivo, H-API-22).
"""
from django.db import DEFAULT_DB_ALIAS

from addons.base_geolocalize.models import GeoProvider

GEO_PROVIDERS = [
    ('openstreetmap', 'Open Street Map'),
    ('googlemap',     'Google Place Map'),
]


def seed(using=DEFAULT_DB_ALIAS):
    """Crea los proveedores ausentes, preservando el orden de ``data.xml``."""
    for tech_name, name in GEO_PROVIDERS:
        GeoProvider.objects.using(using).get_or_create(
            tech_name=tech_name, defaults={'name': name})
