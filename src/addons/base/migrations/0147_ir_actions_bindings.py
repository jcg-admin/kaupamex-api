"""``binding_model_id`` en lugar de ``binding_model_name``.

≙ ``odoo19c: odoo/addons/base/models/ir_actions.py:74-75``: el anclaje de
una acción es un Many2one a ``ir.model``. Diseño:
``designs/ir-actions-bindings.md``.

Las tablas de los subtipos heredan de ``ir_actions`` (migración ``0140``), y
``ADD COLUMN``/``DROP COLUMN`` sobre ``ir_actions`` se propagan a las hijas:
una operación por modelo chocaría con la columna heredada. La base se toca una
sola vez, sobre ``ir_actions``; el estado, en los siete modelos. El valor se
resuelve contra ``ir_model.model`` con la misma normalización que
``IrModel._get_id`` (``registry.identity_for_key``). La clave foránea no se
hereda en PostgreSQL, así que se declara en cada tabla.
"""

import django.db.models.deletion
from django.db import migrations, models

from orm.registry import identity_for_key

MODELS = ('iractionsactions', 'iractionsacturl', 'iractionsactwindow',
          'iractionsclient', 'iractionsreport', 'iractionsserver',
          'iractionsactwindowclose')

TABLES = ('ir_actions', 'ir_act_window', 'ir_act_report_xml', 'ir_act_url',
          'ir_act_server', 'ir_act_client')


def _binding_field():
    return models.ForeignKey(
        blank=True,
        db_column='binding_model_id',
        help_text=(
            'Setting a value makes this action available in the sidebar for '
            'the given model.'
        ),
        null=True,
        on_delete=django.db.models.deletion.CASCADE,
        related_name='+',
        to='base.irmodel',
    )


def bind_to_model_rows(apps, schema_editor):
    """Resuelve cada ``binding_model_name`` a su fila de ``ir_model``."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT DISTINCT binding_model_name FROM ir_actions "
            "WHERE binding_model_name <> ''")
        names = [row[0] for row in cursor.fetchall()]
        for name in names:
            cursor.execute(
                "UPDATE ir_actions SET binding_model_id = m.id "
                "FROM ir_model m WHERE m.model = %s "
                "AND ir_actions.binding_model_name = %s",
                [identity_for_key(name), name])


ADD_SQL = 'ALTER TABLE ir_actions ADD COLUMN binding_model_id bigint NULL;'

CONSTRAIN_SQL = ' '.join(
    f'ALTER TABLE {table} ADD CONSTRAINT {table}_binding_model_id_fk '
    f'FOREIGN KEY (binding_model_id) REFERENCES ir_model (id) '
    f'DEFERRABLE INITIALLY DEFERRED; '
    f'CREATE INDEX {table}_binding_model_id_idx ON {table} '
    f'(binding_model_id);'
    for table in TABLES)

DROP_SQL = 'ALTER TABLE ir_actions DROP COLUMN binding_model_name;'


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0146_res_users_home_action'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                operation
                for model in MODELS
                for operation in (
                    migrations.RemoveField(
                        model_name=model, name='binding_model_name'),
                    migrations.AddField(
                        model_name=model, name='binding_model_id',
                        field=_binding_field()),
                )
            ],
            database_operations=[
                migrations.RunSQL(ADD_SQL, migrations.RunSQL.noop),
                migrations.RunPython(
                    bind_to_model_rows, migrations.RunPython.noop),
                migrations.RunSQL(CONSTRAIN_SQL, migrations.RunSQL.noop),
                migrations.RunSQL(DROP_SQL, migrations.RunSQL.noop),
            ],
        ),
    ]
