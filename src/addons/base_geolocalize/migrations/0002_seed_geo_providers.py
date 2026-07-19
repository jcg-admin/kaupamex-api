# Data migration — siembra el catálogo de proveedores (Odoo
# base_geolocalize/data/data.xml: geoprovider_open_street, geoprovider_google_map).
# Idempotente (get_or_create) para no duplicar en reruns / --reuse-db.
from django.db import migrations


def seed_geo_providers(apps, schema_editor):
    GeoProvider = apps.get_model('base_geolocalize', 'GeoProvider')
    # Orden fiel a data.xml: openstreetmap primero, googlemap segundo — así
    # Geocoder._get_provider() cae en "openstreetmap" cuando el parámetro
    # base_geolocalize.geo_provider no está seteado (order_by('pk').first()).
    GeoProvider.objects.get_or_create(
        tech_name='openstreetmap', defaults={'name': 'Open Street Map'})
    GeoProvider.objects.get_or_create(
        tech_name='googlemap', defaults={'name': 'Google Place Map'})


def unseed_geo_providers(apps, schema_editor):
    GeoProvider = apps.get_model('base_geolocalize', 'GeoProvider')
    GeoProvider.objects.filter(
        tech_name__in=['openstreetmap', 'googlemap']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('base_geolocalize', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_geo_providers, unseed_geo_providers),
    ]
