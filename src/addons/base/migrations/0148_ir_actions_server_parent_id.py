"""``parent_id`` de ``ir.actions.server`` con el nombre de la fuente.

≙ ``odoo19c: odoo/addons/base/models/ir_actions.py:648``. El campo se llamaba
``parent`` con columna ``parent_id``; el cambio es de estado: la columna, su
clave foránea y su índice ya están en ``ir_act_server``. Diseño:
``designs/ir-actions-server-parent-id.md``.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0147_ir_actions_bindings'),
    ]

    operations = [migrations.SeparateDatabaseAndState(state_operations=[
        migrations.RenameField(
            model_name='iractionsserver',
            old_name='parent',
            new_name='parent_id',
        ),
        migrations.AlterField(
            model_name='iractionsserver',
            name='parent_id',
            field=models.ForeignKey(
                blank=True,
                db_column='parent_id',
                help_text='Acción compuesta que encadena a ésta.',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='+',
                to='base.iractionsserver',
                verbose_name='Parent Action',
            ),
        ),
    ])]
