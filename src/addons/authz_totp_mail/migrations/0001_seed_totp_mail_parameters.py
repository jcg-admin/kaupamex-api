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

from addons.authz_totp_mail.data import TOTP_MAIL_PARAMETERS


def sembrar(apps, schema_editor):
    """Crea las claves ausentes sobre el modelo histórico."""
    SystemParameter = apps.get_model('base', 'SystemParameter')
    alias = schema_editor.connection.alias
    for key, value in TOTP_MAIL_PARAMETERS.items():
        if not SystemParameter.objects.using(alias).filter(key=key).exists():
            SystemParameter.objects.using(alias).create(key=key, value=value)


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(sembrar, migrations.RunPython.noop),
    ]
