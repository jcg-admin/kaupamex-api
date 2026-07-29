# Data migration — siembra el catálogo de proveedores (Odoo
# base_geolocalize/data/data.xml: geoprovider_open_street, geoprovider_google_map).
# Idempotente (get_or_create) para no duplicar en reruns / --reuse-db.
from django.db import migrations

from addons.base_geolocalize.data import GEO_PROVIDERS


def seed_geo_providers(apps, schema_editor):
    GeoProvider = apps.get_model('base_geolocalize', 'GeoProvider')
    # Orden fiel a data.xml: openstreetmap primero, googlemap segundo — así
    # Geocoder._get_provider() cae en "openstreetmap" cuando el parámetro
    # base_geolocalize.geo_provider no está seteado (order_by('pk').first()).
    for tech_name, name in GEO_PROVIDERS:
        GeoProvider.objects.get_or_create(
            tech_name=tech_name, defaults={'name': name})


def unseed_geo_providers(apps, schema_editor):
    GeoProvider = apps.get_model('base_geolocalize', 'GeoProvider')
    GeoProvider.objects.filter(
        tech_name__in=[t for t, _ in GEO_PROVIDERS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('base_geolocalize', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_geo_providers, unseed_geo_providers),
    ]
