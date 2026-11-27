"""``model_id`` de ``ir.actions.server`` en lugar de ``model_name``.

≙ ``odoo19c: odoo/addons/base/models/ir_actions.py:635-638``: el modelo de
una acción de servidor es un Many2one requerido a ``ir.model``, y
``model_name`` es su ``related`` sin columna. Diseño:
``designs/ir-actions-server-model-id.md``.

La columna vieja guardaba el ``_name`` o la etiqueta de Django; el valor se
resuelve con ``registry.identity_for_key``, la misma normalización que
``IrModel._get_id``. En una base nueva esta migración corre antes del reflejo
de modelos, así que la fila de ``ir.model`` se crea si falta; el reflejo la
completa después por su clave ``model`` (``IrModel._reflect_models``).
"""

import django.db.models.deletion
from django.db import migrations, models

from orm.registry import identity_for_key


def _model_id_field(null):
    return models.ForeignKey(
        blank=null,
        db_column='model_id',
        help_text='Model on which the server action runs.',
        null=null,
        on_delete=django.db.models.deletion.CASCADE,
        related_name='+',
        to='base.irmodel',
        verbose_name='Model',
    )


def resolve_model_ids(apps, schema_editor):
    """Cada ``model_name`` a su fila de ``ir.model``, creada si falta."""
    alias = schema_editor.connection.alias
    IrActionsServer = apps.get_model('base', 'IrActionsServer')
    IrModel = apps.get_model('base', 'IrModel')
    names = (IrActionsServer.objects.using(alias)
             .values_list('model_name', flat=True).distinct())
    for name in list(names):
        identity = identity_for_key(name)
        row, _ = IrModel.objects.using(alias).get_or_create(
            model=identity, defaults={'name': identity})
        IrActionsServer.objects.using(alias).filter(
            model_name=name).update(model_id=row.pk)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0148_ir_actions_server_parent_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='iractionsserver',
            name='model_id',
            field=_model_id_field(null=True),
        ),
        migrations.RunPython(resolve_model_ids, migrations.RunPython.noop),
        # Las claves foráneas son ``DEFERRABLE INITIALLY DEFERRED``: los
        # disparadores del paso de datos quedan pendientes y PostgreSQL
        # rehúsa el ``ALTER TABLE`` siguiente mientras lo estén.
        migrations.RunSQL('SET CONSTRAINTS ALL IMMEDIATE',
                          migrations.RunSQL.noop),
        migrations.AlterField(
            model_name='iractionsserver',
            name='model_id',
            field=_model_id_field(null=False),
        ),
        migrations.RemoveField(
            model_name='iractionsserver',
            name='model_name',
        ),
    ]
