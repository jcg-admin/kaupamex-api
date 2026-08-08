"""Siembra el cron de retención de logs (DEC-LOG-05).

Equivalente nativo del ``data/ir_cron_data.xml`` que la referencia declara en
el addon dueño del job. Depende de ``base`` porque las dos filas que crea
—``ir.actions.server`` e ``ir.cron``— viven ahí.

Idempotente: un segundo pase no duplica ni pisa el intervalo que el operador
haya ajustado (``noupdate="1"`` del XML original).
"""
from django.db import migrations

from addons.base.data import sembrar_cron
from addons.observability.data import CRON_PURGE_LOGS


def sembrar(apps, schema_editor):
    sembrar_cron(apps, schema_editor.connection.alias, CRON_PURGE_LOGS)


class Migration(migrations.Migration):

    dependencies = [
        ('observability', '0001_initial'),
        ('base', '0008_alter_iractionsactions_path_and_more'),
    ]

    operations = [
        migrations.RunPython(sembrar, migrations.RunPython.noop),
    ]
