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

from addons.mail.data import CANONICAL_SUBTYPES


def sembrar(apps, schema_editor):
    """``mail.mt_comment`` y ``mail.mt_note`` del ``mail_data.xml``."""
    MailMessageSubtype = apps.get_model('mail', 'MailMessageSubtype')
    alias = schema_editor.connection.alias
    for spec in CANONICAL_SUBTYPES:
        MailMessageSubtype.objects.using(alias).update_or_create(
            name=spec['name'], res_model='',
            defaults={k: v for k, v in spec.items() if k != 'name'},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("mail", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(sembrar, migrations.RunPython.noop),
    ]
