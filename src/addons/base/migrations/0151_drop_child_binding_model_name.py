"""Retira la ``binding_model_name`` que ``0147`` dejó en las tablas hijas.

La primera versión de ``0147`` la retiraba sólo de ``ir_actions``. Las cinco
tablas de subtipo la tenían como columna local desde antes de heredar de
``ir_actions`` (``0140``), y PostgreSQL no retira de una hija la columna local
que se retira del padre: quedaba ``NOT NULL`` y sin campo en el modelo, así que
toda inserción posterior fallaba en una base nueva. ``0147`` ya la retira de
las seis tablas; esta migración la retira en las bases que aplicaron la
versión anterior. Diseño: ``designs/ir-actions-bindings.md``.
"""

from django.db import migrations

TABLES = ('ir_act_window', 'ir_act_report_xml', 'ir_act_url',
          'ir_act_server', 'ir_act_client')

DROP_SQL = ' '.join(
    f'ALTER TABLE {table} DROP COLUMN IF EXISTS binding_model_name;'
    for table in TABLES)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0150_ir_actions_server_base_automation_id'),
    ]

    operations = [
        migrations.RunSQL(DROP_SQL, migrations.RunSQL.noop),
    ]
