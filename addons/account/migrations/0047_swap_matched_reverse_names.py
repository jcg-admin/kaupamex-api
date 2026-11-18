# ≙ account.move.line matched_debit_ids / matched_credit_ids
# (odoo19c: addons/account/models/account_move_line.py:262-273): el
# inverso de credit_move_id es matched_debit_ids y el de debit_move_id es
# matched_credit_ids. Estaban cruzados. Sólo cambia el nombre inverso: no
# hay SQL.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0046_move_line_move_name_date"),
    ]

    operations = [
        migrations.AlterField(
            model_name="accountpartialreconcile",
            name="credit_move",
            field=models.ForeignKey(
                help_text=(
                    "Apunte del lado haber (Odoo credit_move_id, "
                    "requerido)."
                ),
                on_delete=django.db.models.deletion.CASCADE,
                related_name="matched_debit_ids",
                to="account.accountmoveline",
            ),
        ),
        migrations.AlterField(
            model_name="accountpartialreconcile",
            name="debit_move",
            field=models.ForeignKey(
                help_text=(
                    "Apunte del lado debe (Odoo debit_move_id, requerido)."
                ),
                on_delete=django.db.models.deletion.CASCADE,
                related_name="matched_credit_ids",
                to="account.accountmoveline",
            ),
        ),
    ]
