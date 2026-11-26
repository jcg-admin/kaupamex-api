"""``ir.filters`` pasa a la forma de Odoo 19.

≙ ``odoo19c: odoo/addons/base/models/ir_filters.py:7-109``. El dueño único
``user`` (forma de 18) se convierte en ``user_ids``, la relación
``ir_filters_res_users_rel``: cada fila con dueño pasa a tener ese usuario y
una sin dueño queda compartida (relación vacía), que es lo que la regla
de la fuente lee como global. ``model_id`` pasa de la etiqueta de Django a la
identidad que guarda ``ir_model.model``. Se retira la unicidad de 18, que 19
no declara. Con ``_name`` declarado entran las cuatro columnas de auditoría;
las filas existentes toman la hora de la migración, como en ``0119``.
Diseño: ``designs/ir-filters-port-19.md``.
"""

import django.db.models.deletion
import django.utils.timezone
import orm.fields_relational
from django.conf import settings
from django.db import migrations, models

from orm.registry import identity_for_key


def forwards(apps, schema_editor):
    """El dueño a la relación y la etiqueta a la identidad."""
    alias = schema_editor.connection.alias
    filters = apps.get_model('base', 'IrFilters').objects.using(alias)
    for row in filters.exclude(user_id=None):
        row.user_ids.add(row.user_id)
    for row in filters.all():
        identity = identity_for_key(row.model_id)
        if identity != row.model_id:
            filters.filter(pk=row.pk).update(model_id=identity)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0130_seed_view_custom_rule'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='irfilters',
            name='uq_ir_filters_model_user_action_name',
        ),
        migrations.AddField(
            model_name='irfilters',
            name='create_date',
            field=models.DateTimeField(auto_now_add=True, default=None),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='irfilters',
            name='create_uid',
            field=models.ForeignKey(
                blank=True,
                db_column='create_uid',
                db_index=False,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='irfilters',
            name='user_ids',
            field=orm.fields_relational.Many2manyField(
                blank=True,
                column1='ir_filters_id',
                column2='res_users_id',
                db_table='ir_filters_res_users_rel',
                help_text=(
                    'The users the filter is shared with. If empty, the '
                    'filter is shared with all users.'
                ),
                related_name='+',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Users',
            ),
        ),
        migrations.AddField(
            model_name='irfilters',
            name='write_date',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='irfilters',
            name='write_uid',
            field=models.ForeignKey(
                blank=True,
                db_column='write_uid',
                db_index=False,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='irfilters',
            name='action_id',
            field=models.ForeignKey(
                blank=True,
                db_column='action_id',
                help_text=(
                    'The menu action this filter applies to. When left empty '
                    'the filter applies to all menus for this model.'
                ),
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='filter_ids',
                to='base.iractionsactions',
                verbose_name='Action',
            ),
        ),
        migrations.AlterField(
            model_name='irfilters',
            name='context',
            field=models.TextField(default='{}', help_text='Odoo context.'),
        ),
        migrations.AlterField(
            model_name='irfilters',
            name='domain',
            field=models.TextField(default='[]', help_text='Odoo domain.'),
        ),
        migrations.AlterField(
            model_name='irfilters',
            name='embedded_action',
            field=models.ForeignKey(
                blank=True,
                help_text='The embedded action this filter is applied to',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='filter_ids',
                to='base.irembeddedactions',
                verbose_name='Embedded action',
            ),
        ),
        migrations.AlterField(
            model_name='irfilters',
            name='embedded_parent_res_id',
            field=models.IntegerField(
                blank=True,
                help_text=(
                    'id of the record the filter should be applied to. Only '
                    'used in combination with embedded actions'
                ),
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name='irfilters',
            name='is_default',
            field=models.BooleanField(
                default=False,
                help_text='Odoo is_default.',
                verbose_name='Default Filter',
            ),
        ),
        migrations.AlterField(
            model_name='irfilters',
            name='model_id',
            field=models.CharField(
                help_text='Identidad del modelo (Odoo model_id).',
                max_length=128,
                verbose_name='Model',
            ),
        ),
        migrations.AlterField(
            model_name='irfilters',
            name='name',
            field=models.CharField(
                help_text='Nombre del filtro (Odoo name, requerido).',
                max_length=256,
                verbose_name='Filter Name',
            ),
        ),
        migrations.AlterField(
            model_name='irfilters',
            name='sort',
            field=models.CharField(
                default='[]',
                help_text='Odoo sort.',
                max_length=512,
            ),
        ),
        # Sin marcha atrás: la relación no cabe en una sola columna.
        migrations.RunPython(forwards, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='irfilters',
            name='user',
        ),
    ]
