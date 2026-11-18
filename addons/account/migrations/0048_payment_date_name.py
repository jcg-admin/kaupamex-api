# ≙ account.payment name y date
# (odoo19c: addons/account/models/account_payment.py:15 y :16), los dos
# campos que cita _order, y la secuencia de la que sale el número
# (odoo19c: addons/account/data/ir_sequence.xml:4).
#
# date entra nula, se rellena con la fecha de create_date de cada fila --el
# día en que su valor por defecto se habría evaluado-- y pasa a obligatoria.

import orm.fields_temporal
from django.db import migrations, models

from addons.account.data import seed_payment_sequence
from orm.migration_operations import ComputeStoredFields


def fill_payment_date(apps, schema_editor):
    """La fecha de las filas existentes: el día de su ``create_date``."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            'UPDATE account_payment SET date = create_date::date '
            'WHERE date IS NULL')


def seed(apps, schema_editor):
    seed_payment_sequence(apps, schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0047_swap_matched_reverse_names"),
        ("base", "0118_set_null_ondelete_block_d"),
    ]

    operations = [
        migrations.AddField(
            model_name="accountpayment",
            name="date",
            field=models.DateField(null=True),
        ),
        migrations.RunPython(fill_payment_date, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="accountpayment",
            name="date",
            field=models.DateField(
                default=orm.fields_temporal._date_context_today),
        ),
        migrations.AddField(
            model_name="accountpayment",
            name="name",
            field=models.CharField(blank=True, editable=False,
                                   max_length=255, null=True),
        ),
        migrations.RunPython(seed, migrations.RunPython.noop),
        ComputeStoredFields('account', 'accountpayment', ['name']),
    ]
