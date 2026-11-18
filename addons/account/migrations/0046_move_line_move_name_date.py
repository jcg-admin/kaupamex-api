# ≙ account.move.line move_name y date
# (odoo19c: addons/account/models/account_move_line.py:63 y :69),
# relacionados almacenados del número y de la fecha del asiento, que cita
# _order; las filas existentes los reciben de su asiento.

from django.db import migrations, models

from orm.migration_operations import ComputeStoredFields


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0045_restrict_ondelete_block_f"),
    ]

    operations = [
        migrations.AddField(
            model_name="accountmoveline",
            name="date",
            field=models.DateField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="accountmoveline",
            name="move_name",
            field=models.CharField(blank=True, db_index=True, editable=False,
                                   max_length=255, null=True),
        ),
        ComputeStoredFields('account', 'accountmoveline',
                            ['move_name', 'date']),
    ]
