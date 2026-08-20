"""Siembra el cron de retención de logs (DEC-LOG-05).

Equivalente nativo del ``data/ir_cron_data.xml`` que la referencia declara en
el addon dueño del job. Depende de ``base`` porque las dos filas que crea
—``ir.actions.server`` e ``ir.cron``— viven ahí.

Idempotente: un segundo pase no duplica ni pisa el intervalo que el operador
haya ajustado (``noupdate="1"`` del XML original).

**El spec va inline, no importado.** Vivía en ``observability/data/__init__.py``
y esa forma tenía un defecto que ``0003`` tuvo que documentar: al editar el
módulo vivo cambiaba lo que esta migración siembra **retroactivamente**, así que
una base nueva y una base vieja acababan con filas distintas para el mismo
número de migración. Una data-migration es un hecho fechado; su dato se congela
aquí. El módulo se retiró con la disolución de ``observability`` (H-API-752).
"""
from django.db import migrations

from addons.base.data import sembrar_cron

# Congelado tal como estaba al escribirse esta migración. NO se edita: lo que
# cambie el horario de un job ya sembrado es otra migración, no ésta.
CRON_PURGE_LOGS = {
    'name': 'Observability: purgar logs por retencion',
    'model_name': 'base.IrLogging',
    'method_name': 'purge_expired',
    'interval_number': 1,
    'interval_type': 'days',
    'priority': 8,
}


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
