"""``base_automation_id`` de ``ir.actions.server``.

≙ ``odoo19c: addons/base_automation/models/ir_actions_server.py:17``:
``Many2one('base.automation', index='btree_not_null', ondelete='cascade')``,
declarado por ``base_automation`` sobre la acción de servidor. Lo instala
``extend_model(campos=…)`` y, como todo campo de ese mecanismo, su migración
vive en la app dueña del modelo (precedente: ``0028``, campos de
``account``). Diseño: ``designs/ir-actions-server-model-id.md``.

El valor sale de la tabla-liga ``base_automation_action`` que lo sustituía;
``base_automation/0010`` la retira después de esta copia.
"""

import django.db.models.deletion
from django.db import migrations, models


def copy_links(apps, schema_editor):
    """Cada liga acción → regla pasa a la columna de la acción."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "UPDATE ir_act_server a SET base_automation_id = l.automation_id "
            "FROM base_automation_action l WHERE l.action_id = a.id")


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0149_ir_actions_server_model_id'),
        ('base_automation', '0009_rewrite_model_identities'),
    ]

    operations = [
        migrations.AddField(
            model_name='iractionsserver',
            name='base_automation_id',
            field=models.ForeignKey(
                blank=True,
                db_column='base_automation_id',
                db_index=False,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='+',
                to='base_automation.baseautomation',
                verbose_name='Automation Rule',
            ),
        ),
        migrations.AddIndex(
            model_name='iractionsserver',
            index=models.Index(
                condition=models.Q(('base_automation_id__isnull', False)),
                fields=['base_automation_id'],
                name='ir_act_server__base_a_3ebf5647',
            ),
        ),
        migrations.RunPython(copy_links, migrations.RunPython.noop),
    ]
