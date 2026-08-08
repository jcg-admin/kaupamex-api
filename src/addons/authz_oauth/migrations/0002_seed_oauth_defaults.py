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

from addons.authz_oauth.data import OAUTH_PARAMETERS, OAUTH_PROVIDERS


def sembrar(apps, schema_editor):
    """Parámetros y los dos proveedores del XML de la referencia."""
    SystemParameter = apps.get_model('base', 'SystemParameter')
    OauthProvider = apps.get_model('authz_oauth', 'OauthProvider')
    alias = schema_editor.connection.alias
    for key, value in OAUTH_PARAMETERS.items():
        if not SystemParameter.objects.using(alias).filter(key=key).exists():
            SystemParameter.objects.using(alias).create(key=key, value=value)
    for spec in OAUTH_PROVIDERS:
        if not OauthProvider.objects.using(alias).filter(
                name=spec['name']).exists():
            OauthProvider.objects.using(alias).create(**spec)


class Migration(migrations.Migration):

    dependencies = [
        ("authz_oauth", "0001_initial"),
        ("base", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(sembrar, migrations.RunPython.noop),
    ]
