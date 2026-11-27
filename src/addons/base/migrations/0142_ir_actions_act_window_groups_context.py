"""``group_ids`` y ``context`` de la acción de ventana, como la fuente.

≙ ``odoo19c: odoo/addons/base/models/ir_actions.py:312-313`` (``context``,
texto de una expresión de Python) y ``:328-329`` (``group_ids``, tabla
``ir_act_window_group_rel`` con las columnas ``act_id`` y ``gid``). Diseño:
``designs/ir-actions-act-window-groups-context-read.md``.

El campo se renombra en el estado y las dos columnas en la base: las filas de
la relación se conservan. Cada ``context`` guardado como JSON se reescribe con
``repr`` del dict, que es el literal de Python que ``read`` evalúa con
``safe_eval``; ``json.dumps`` escribiría ``true``, ``false`` y ``null``.
"""

import json

import orm.fields_relational
from django.db import migrations, models


def context_as_python_literal(apps, schema_editor):
    """Reescribe cada ``context`` JSON como literal de Python."""
    alias = schema_editor.connection.alias
    actions = apps.get_model('base', 'IrActionsActWindow').objects.using(alias)
    for pk, text in actions.values_list('pk', 'context'):
        try:
            value = json.loads(text) if text else {}
        except (TypeError, ValueError):
            continue
        literal = repr(value)
        if literal != text:
            actions.filter(pk=pk).update(context=literal)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0141_ir_actions_act_window_views'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name='iractionsactwindow',
                    name='groups',
                ),
                migrations.AddField(
                    model_name='iractionsactwindow',
                    name='group_ids',
                    field=orm.fields_relational.Many2manyField(
                        blank=True,
                        column1='act_id',
                        column2='gid',
                        db_table='ir_act_window_group_rel',
                        related_name='act_window_ids',
                        to='base.resgroups',
                        verbose_name='Groups',
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    'ALTER TABLE ir_act_window_group_rel '
                    'RENAME COLUMN iractionsactwindow_id TO act_id; '
                    'ALTER TABLE ir_act_window_group_rel '
                    'RENAME COLUMN resgroups_id TO gid;',
                    'ALTER TABLE ir_act_window_group_rel '
                    'RENAME COLUMN act_id TO iractionsactwindow_id; '
                    'ALTER TABLE ir_act_window_group_rel '
                    'RENAME COLUMN gid TO resgroups_id;',
                ),
            ],
        ),
        migrations.AlterField(
            model_name='iractionsactwindow',
            name='context',
            field=models.CharField(
                default='{}',
                help_text=(
                    'Context dictionary as Python expression, empty by '
                    'default (Default: {})'
                ),
                verbose_name='Contexto',
            ),
        ),
        migrations.RunPython(
            context_as_python_literal, migrations.RunPython.noop),
    ]
