"""``action_id`` de ``ir.actions.todo`` con el nombre de la fuente.

≙ ``odoo19c: odoo/addons/base/models/ir_actions.py:1357``. El campo se
llamaba ``action`` con columna ``action_id``; el cambio es de estado: la
columna y su índice ya están en ``ir_actions_todo``, y el reverso pasa a
``related_name='+'`` como el resto de las claves de la fuente. Diseño:
``designs/ir-actions-todo-action-id-launch.md``.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0153_compute_ir_actions_server_automated_name'),
    ]

    operations = [migrations.SeparateDatabaseAndState(state_operations=[
        migrations.RenameField(
            model_name='iractionstodo',
            old_name='action',
            new_name='action_id',
        ),
        migrations.AlterField(
            model_name='iractionstodo',
            name='action_id',
            field=models.ForeignKey(
                db_column='action_id',
                db_constraint=False,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='+',
                to='base.iractionsactions',
                verbose_name='Acción',
            ),
        ),
    ])]
