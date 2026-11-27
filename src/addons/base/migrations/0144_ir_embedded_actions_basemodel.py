"""``ir.embedded.actions`` con la forma de la fuente.

≙ ``odoo19c: odoo/addons/base/models/ir_embedded_actions.py:8-111``,
``ir_filters.py:23``, ``security/ir.model.access.csv:109`` y
``security/base_security.xml:207-227``. Diseño:
``designs/ir-embedded-actions-basemodel.md``.

- ``parent_action``, ``action``, ``user`` y ``embedded_action`` (de
  ``ir.filters``) pasan a sus nombres ``*_id`` sólo en el estado: las
  columnas ya se llamaban así, y el índice y la restricción de
  ``ir.filters`` no cambian de SQL.
- ``groups`` pasa a ``groups_ids`` renombrando su tabla y sus columnas a las
  que deriva la fuente (``odoo/orm/fields_relational.py:1291-1295``).
- ``python_method`` pasa a admitir NULL y un valor vacío se escribe NULL,
  la forma que miden las restricciones de la fuente (``:31-41``).
- ``context`` guardaba JSON; se reescribe con ``repr`` del dict.
- ``name`` pasa a ``jsonb`` por idioma (``translate=True``).
- ``system`` se retira: la fuente decide ``is_deletable`` por el id externo.
"""

import json

import django.db.models.deletion
import orm.fields_relational
import orm.fields_textual
from django.conf import settings
from django.db import migrations, models

from addons.base.security.base_security import seed_base_rules
from addons.base.security.ir_model_access import seed_base_acl
from orm.migration_operations import ConvertColumnTranslatable


def empty_python_method_as_null(apps, schema_editor):
    """Un ``python_method`` vacío se escribe NULL."""
    alias = schema_editor.connection.alias
    apps.get_model('base', 'IrEmbeddedActions').objects.using(alias).filter(
        python_method='').update(python_method=None)


def _literal(text):
    """El literal de Python de un texto JSON, o ``None`` si no lo es."""
    try:
        return repr(json.loads(text)) if text else None
    except (TypeError, ValueError):
        return None


def context_as_python_literal(apps, schema_editor):
    """Reescribe cada ``context`` JSON como literal."""
    alias = schema_editor.connection.alias
    rows = apps.get_model('base', 'IrEmbeddedActions').objects.using(alias)
    for pk, text in rows.values_list('pk', 'context'):
        literal = _literal(text)
        if literal is not None and literal != text:
            rows.filter(pk=pk).update(context=literal)


def seed(apps, schema_editor):
    alias = schema_editor.connection.alias
    seed_base_acl(apps, alias)
    seed_base_rules(apps, alias)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0143_ir_actions_view_url_client'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='irembeddedactions',
            options={
                'ordering': ['sequence', 'id'],
                'verbose_name': 'Embedded Actions',
                'verbose_name_plural': 'Embedded Actions',
            },
        ),
        migrations.RemoveConstraint(
            model_name='irembeddedactions',
            name='ir_embedded_actions_only_one_action_defined',
        ),
        migrations.RemoveConstraint(
            model_name='irembeddedactions',
            name='ir_embedded_actions_python_method_requires_name',
        ),
        migrations.AlterField(
            model_name='irembeddedactions',
            name='python_method',
            field=models.CharField(
                blank=True, help_text='Python method returning an action',
                null=True),
        ),
        migrations.RunPython(
            empty_python_method_as_null, migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name='irembeddedactions', name='action'),
                migrations.RemoveField(
                    model_name='irembeddedactions', name='parent_action'),
                migrations.RemoveField(
                    model_name='irembeddedactions', name='user'),
                migrations.AddField(
                    model_name='irembeddedactions',
                    name='action_id',
                    field=models.ForeignKey(
                        blank=True,
                        db_column='action_id',
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='+',
                        to='base.iractionsactions',
                        verbose_name='Action',
                    ),
                ),
                migrations.AddField(
                    model_name='irembeddedactions',
                    name='parent_action_id',
                    field=models.ForeignKey(
                        db_column='parent_action_id',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='+',
                        to='base.iractionsactwindow',
                        verbose_name='Parent Action',
                    ),
                    preserve_default=False,
                ),
                migrations.AddField(
                    model_name='irembeddedactions',
                    name='user_id',
                    field=models.ForeignKey(
                        blank=True,
                        db_column='user_id',
                        help_text=(
                            'User specific embedded action. If empty, shared '
                            'embedded action'
                        ),
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='+',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='User',
                    ),
                ),
                migrations.RemoveConstraint(
                    model_name='irfilters',
                    name='ir_filters_check_res_id_only_when_embedded_action',
                ),
                migrations.RemoveIndex(
                    model_name='irfilters',
                    name='ir_filters_get_filters_index',
                ),
                migrations.RemoveField(
                    model_name='irfilters', name='embedded_action'),
                migrations.AddField(
                    model_name='irfilters',
                    name='embedded_action_id',
                    field=models.ForeignKey(
                        blank=True,
                        db_column='embedded_action_id',
                        help_text=(
                            'The embedded action this filter is applied to'),
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='filter_ids',
                        to='base.irembeddedactions',
                        verbose_name='Embedded action',
                    ),
                ),
                migrations.AddIndex(
                    model_name='irfilters',
                    index=models.Index(
                        fields=[
                            'model_id',
                            'action_id',
                            'embedded_action_id',
                            'embedded_parent_res_id',
                        ],
                        name='ir_filters_get_filters_index',
                    ),
                ),
                migrations.AddConstraint(
                    model_name='irfilters',
                    constraint=models.CheckConstraint(
                        condition=models.Q(
                            ('embedded_action_id__isnull', True),
                            ('embedded_parent_res_id__isnull', False),
                            _negated=True,
                        ),
                        name=(
                            'ir_filters_check_res_id_only_when_embedded_action'
                        ),
                    ),
                ),
            ],
            database_operations=[],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name='irembeddedactions', name='groups'),
                migrations.AddField(
                    model_name='irembeddedactions',
                    name='groups_ids',
                    field=orm.fields_relational.Many2manyField(
                        blank=True,
                        column1='ir_embedded_actions_id',
                        column2='res_groups_id',
                        db_table='ir_embedded_actions_res_groups_rel',
                        help_text=(
                            'Groups that can execute the embedded action. '
                            'Leave empty to allow everybody.'
                        ),
                        related_name='+',
                        to='base.resgroups',
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    'ALTER TABLE ir_embedded_actions_groups '
                    'RENAME TO ir_embedded_actions_res_groups_rel; '
                    'ALTER TABLE ir_embedded_actions_res_groups_rel '
                    'RENAME COLUMN irembeddedactions_id '
                    'TO ir_embedded_actions_id; '
                    'ALTER TABLE ir_embedded_actions_res_groups_rel '
                    'RENAME COLUMN resgroups_id TO res_groups_id;',
                    migrations.RunSQL.noop,
                ),
            ],
        ),
        migrations.AlterField(
            model_name='irembeddedactions',
            name='context',
            field=models.CharField(
                blank=True,
                default='{}',
                help_text=(
                    'Context dictionary as Python expression, empty by '
                    'default (Default: {})'
                ),
                null=True,
            ),
        ),
        migrations.RunPython(
            context_as_python_literal, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='irembeddedactions',
            name='default_view_mode',
            field=models.CharField(
                blank=True,
                help_text=(
                    'Default view (if none, default view of the action is '
                    'taken)'
                ),
                null=True,
                verbose_name='Default View',
            ),
        ),
        migrations.AlterField(
            model_name='irembeddedactions',
            name='domain',
            field=models.CharField(
                blank=True,
                default='[]',
                help_text=(
                    'Domain applied to the active id of the parent model'),
                null=True,
            ),
        ),
        ConvertColumnTranslatable(
            model_name='irembeddedactions',
            name='name',
            field=orm.fields_textual.TranslatedChar(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='irembeddedactions',
            name='parent_res_id',
            field=models.IntegerField(
                blank=True, null=True, verbose_name='Active Parent Id'),
        ),
        migrations.AlterField(
            model_name='irembeddedactions',
            name='parent_res_model',
            field=models.CharField(verbose_name='Active Parent Model'),
        ),
        migrations.AlterField(
            model_name='irembeddedactions',
            name='sequence',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.RemoveField(model_name='irembeddedactions', name='system'),
        migrations.AddConstraint(
            model_name='irembeddedactions',
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ('action_id__isnull', False),
                        ('python_method__isnull', True),
                    ),
                    models.Q(
                        ('action_id__isnull', True),
                        ('python_method__isnull', False),
                    ),
                    _connector='OR',
                ),
                name='ir_embedded_actions_check_only_one_action_defined',
            ),
        ),
        migrations.AddConstraint(
            model_name='irembeddedactions',
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ('name__isnull', True),
                    ('python_method__isnull', False),
                    _negated=True,
                ),
                name='ir_embedded_actions_check_python_method_requires_name',
            ),
        ),
        # Sin marcha atrás, mismo criterio que ``0139``.
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
