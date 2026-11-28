"""``module_id`` de dependencias y exclusiones con el nombre de la fuente.

≙ ``odoo19c: odoo/addons/base/models/ir_module.py:1009,1074``. Los dos
campos se llamaban ``module`` con columna ``module_id``; el cambio es de
estado: la columna ya existe, y el reverso pasa a ``related_name='+'`` porque
el módulo declara sus propios ``dependencies_id`` y ``exclusion_ids``
(``:295-299``). Diseño: ``designs/ir-module-dependency-module-id.md``.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0154_ir_actions_todo_action_id'),
    ]

    operations = [migrations.SeparateDatabaseAndState(state_operations=[
        migrations.RenameField(
            model_name='irmoduledependency',
            old_name='module',
            new_name='module_id',
        ),
        migrations.AlterField(
            model_name='irmoduledependency',
            name='module_id',
            field=models.ForeignKey(
                blank=True,
                db_column='module_id',
                help_text='El addon que declara la dependencia.',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='+',
                to='base.irmodule',
            ),
        ),
        migrations.RenameField(
            model_name='irmoduleexclusion',
            old_name='module',
            new_name='module_id',
        ),
        migrations.AlterField(
            model_name='irmoduleexclusion',
            name='module_id',
            field=models.ForeignKey(
                blank=True,
                db_column='module_id',
                help_text='El addon que declara la exclusión.',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='+',
                to='base.irmodule',
            ),
        ),
    ])]
