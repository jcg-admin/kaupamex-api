"""Vincula el cron ya sembrado a su ``xml_id``, ``base.autovacuum_job``.

Es el ``id`` del ``<record model="ir.cron">`` de la fuente (``odoo19c:
odoo/addons/base/data/ir_cron_data.xml:3-11``). Volver a sembrar el spec
encuentra la acción por su método, porque aún no hay fila de
``ir.model.data``, y registra el ``xml_id``
(``designs/cron-xml-id-natural-key.md``).
"""
from django.db import migrations

from addons.base.data import sembrar_cron
from addons.base.data import CRON_AUTOVACUUM


def seed(apps, schema_editor):
    sembrar_cron(apps, schema_editor.connection.alias, CRON_AUTOVACUUM)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0126_fill_cron_action_code'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
