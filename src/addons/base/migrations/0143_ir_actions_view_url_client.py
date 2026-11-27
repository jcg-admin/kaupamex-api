"""``act_window.view``, ``act_url`` y ``client`` con la forma de la fuente.

≙ ``odoo19c: odoo/addons/base/models/ir_actions.py:411-425``,
``:445-460``, ``:1426-1462`` y
``odoo/addons/base/security/ir.model.access.csv:105-110``. Diseño:
``designs/ir-actions-view-url-client-basemodel.md``.

- ``act_window`` pasa a ``act_window_id`` sólo en el estado: la columna ya
  se llamaba ``act_window_id`` y la restricción de unicidad no cambia.
- ``view_id`` pasa de entero a Many2one a ``ir.ui.view``; antes se vacían
  los valores que no apuntan a ninguna vista, que la clave foránea
  rechazaría.
- ``context`` y ``params_store`` de ``client`` guardaban JSON; se reescriben
  con ``repr`` del dict, el literal de Python que ``safe_eval`` lee.
"""

import json

import django.db.models.deletion
from django.db import migrations, models

from addons.base.security.ir_model_access import seed_base_acl


def clear_dangling_view_ids(apps, schema_editor):
    """Vacía cada ``view_id`` que no apunta a una vista."""
    alias = schema_editor.connection.alias
    views = apps.get_model('base', 'IrUiView').objects.using(alias)
    rows = apps.get_model('base', 'IrActionsActWindowView').objects.using(
        alias)
    rows.exclude(view_id=None).exclude(
        view_id__in=views.values('pk')).update(view_id=None)


def _literal(text):
    """El literal de Python de un texto JSON, o ``None`` si no lo es."""
    try:
        return repr(json.loads(text)) if text else None
    except (TypeError, ValueError):
        return None


def context_as_python_literal(apps, schema_editor):
    """Reescribe cada ``context`` JSON de ``client`` como literal."""
    alias = schema_editor.connection.alias
    clients = apps.get_model('base', 'IrActionsClient').objects.using(alias)
    for pk, text in clients.values_list('pk', 'context'):
        literal = _literal(text)
        if literal is not None and literal != text:
            clients.filter(pk=pk).update(context=literal)


def params_as_python_literal(apps, schema_editor):
    """Reescribe cada ``params_store`` JSON como ``repr`` en bytes."""
    alias = schema_editor.connection.alias
    clients = apps.get_model('base', 'IrActionsClient').objects.using(alias)
    for pk, stored in clients.values_list('pk', 'params_store'):
        if stored is None:
            continue
        text = bytes(stored).decode()
        literal = _literal(text)
        if literal is not None and literal != text:
            clients.filter(pk=pk).update(params_store=literal.encode())


def seed(apps, schema_editor):
    seed_base_acl(apps, schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0142_ir_actions_act_window_groups_context'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='iractionsactwindowview',
                    name='ir_act_window_view_unique_mode_per_action',
                ),
                migrations.RemoveField(
                    model_name='iractionsactwindowview',
                    name='act_window',
                ),
                migrations.AddField(
                    model_name='iractionsactwindowview',
                    name='act_window_id',
                    field=models.ForeignKey(
                        blank=True,
                        db_column='act_window_id',
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='view_ids',
                        to='base.iractionsactwindow',
                        verbose_name='Action',
                    ),
                ),
                migrations.AddConstraint(
                    model_name='iractionsactwindowview',
                    constraint=models.UniqueConstraint(
                        fields=('act_window_id', 'view_mode'),
                        name='ir_act_window_view_unique_mode_per_action',
                    ),
                ),
            ],
            database_operations=[],
        ),
        migrations.RunPython(
            clear_dangling_view_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='iractionsactwindowview',
            name='view_id',
            field=models.ForeignKey(
                blank=True,
                db_column='view_id',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
                to='base.iruiview',
                verbose_name='View',
            ),
        ),
        migrations.AlterField(
            model_name='iractionsclient',
            name='context',
            field=models.CharField(
                default='{}',
                help_text=(
                    'Context dictionary as Python expression, empty by '
                    'default (Default: {})'
                ),
                verbose_name='Context Value',
            ),
        ),
        migrations.RunPython(
            context_as_python_literal, migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='iractionsclient',
                    name='params_store',
                    field=models.BinaryField(
                        blank=True, null=True, verbose_name='Params storage'),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    'ALTER TABLE ir_act_client '
                    'ALTER COLUMN params_store DROP DEFAULT, '
                    'ALTER COLUMN params_store DROP NOT NULL, '
                    'ALTER COLUMN params_store TYPE bytea '
                    "USING convert_to(params_store::text, 'UTF8');",
                    migrations.RunSQL.noop,
                ),
            ],
        ),
        migrations.RunPython(
            params_as_python_literal, migrations.RunPython.noop),
        # Sin marcha atrás, mismo criterio que ``0139``.
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
