"""``account.report.line.action`` sin clave foránea hacia ``ir_actions``.

≙ ``odoo19c: odoo/orm/fields_relational.py:313-314``: ``ir_actions`` se
hereda y un Many2one hacia ella no crea clave foránea. Diseño:
``designs/ir-actions-family-basemodel-and-inheritance.md`` (paso 1).
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0058_accountcodemapping'),
        ('base', '0140_ir_actions_table_inheritance'),
    ]

    operations = [
        migrations.AlterField(
            model_name='accountreportline',
            name='action',
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                help_text=(
                    'Acción a ejecutar al pulsar la línea; si está puesta, la '
                    'línea es un enlace (Odoo action_id).'
                ),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='account_report_lines',
                to='base.iractionsactions',
            ),
        ),
    ]
