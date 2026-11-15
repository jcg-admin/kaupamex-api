# ≙ account.move.line parent_state
# (odoo19c: account/models/account_move_line.py:68), relacionado almacenado
# del estado del asiento; las filas existentes lo reciben de su asiento.

from django.db import migrations, models

from orm.migration_operations import ComputeStoredFields


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0038_model_headers"),
    ]

    operations = [
        migrations.AddField(
            model_name="accountmoveline",
            name="parent_state",
            field=models.CharField(blank=True, editable=False, max_length=8,
                                   null=True),
        ),
        ComputeStoredFields('account', 'accountmoveline', ['parent_state']),
    ]
