"""Vincula el cron ya sembrado a su ``xml_id``,
``auto_backup.backup_scheduler``.

Es el ``id`` del ``<record model="ir.cron">`` de la fuente (``odoo18c:
app_auto_backup/data/backup_data.xml:4``). Volver a sembrar el spec
encuentra la acción por su método, porque aún no hay fila de
``ir.model.data``, y registra el ``xml_id``
(``designs/cron-xml-id-natural-key.md``).
"""
from django.db import migrations

from addons.base.data import sembrar_cron
from addons.auto_backup.data import CRON_BACKUP


def seed(apps, schema_editor):
    sembrar_cron(apps, schema_editor.connection.alias, CRON_BACKUP)


class Migration(migrations.Migration):

    dependencies = [
        ('auto_backup', '0007_log_access_user_column_names'),
        ('base', '0127_cron_xml_ids'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
