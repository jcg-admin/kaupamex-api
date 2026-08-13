"""Siembra inicial del addon — la data-migration que su ``data`` declara.

Reposición de H-API-263: el spec de semilla se escribió para **dos**
consumidores —esta migración (arranque de la BD) y ``seed()`` (re-aplicación
sobre el modelo vivo)— y sólo sobrevivió el segundo. Con la BD recreada desde
cero eso dejó de ser latente: los parámetros no existían y los tests que los
leen fallaban.

Importa **el spec** (una constante), no ``seed()``: una migración no debe
ejecutar comportamiento de la app, que cambia bajo sus pies. Escribe sobre el
modelo **histórico** vía ``apps.get_model``.

Idempotente y ``noupdate`` como el XML de la referencia: nunca pisa un valor
que ya exista.
"""
from django.db import migrations

from addons.base_geolocalize.data import GEO_PROVIDERS


def sembrar(apps, schema_editor):
    """Crea los proveedores preservando el orden del ``data.xml``.

    El orden **es** contrato: ``Geocoder._get_provider()`` cae en
    ``openstreetmap`` cuando el parámetro no está seteado, porque toma
    ``order_by('pk').first()``. Insertar al revés cambiaría el proveedor por
    defecto sin que nada lo declare.
    """
    GeoProvider = apps.get_model('base_geolocalize', 'GeoProvider')
    alias = schema_editor.connection.alias
    for tech_name, name in GEO_PROVIDERS:
        GeoProvider.objects.using(alias).get_or_create(
            tech_name=tech_name, defaults={'name': name})


class Migration(migrations.Migration):

    dependencies = [
        ("base_geolocalize", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(sembrar, migrations.RunPython.noop),
    ]
