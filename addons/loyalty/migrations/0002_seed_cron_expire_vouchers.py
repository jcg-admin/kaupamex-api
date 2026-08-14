"""Siembra el cron de caducidad de vouchers (UC-SYS-02).

Equivalente nativo del ``data/ir_cron_data.xml`` que la referencia declara en
el addon dueño del job. Depende de ``base`` porque las dos filas que crea
—``ir.actions.server`` e ``ir.cron``— viven ahí.

Idempotente: un segundo pase no duplica ni pisa el intervalo que el operador
haya ajustado (``noupdate="1"`` del XML original).
"""
from django.db import migrations

from addons.base.data import sembrar_cron
from addons.loyalty.data import CRON_EXPIRE_VOUCHERS


def sembrar(apps, schema_editor):
    sembrar_cron(apps, schema_editor.connection.alias, CRON_EXPIRE_VOUCHERS)


class Migration(migrations.Migration):

    dependencies = [
        ('loyalty', '0001_initial'),
        ('base', '0008_alter_iractionsactions_path_and_more'),
    ]

    operations = [
        migrations.RunPython(sembrar, migrations.RunPython.noop),
    ]
