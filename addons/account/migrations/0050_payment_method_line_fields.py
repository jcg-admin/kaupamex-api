# ≙ account.payment payment_method_line_id, payment_method_id y
# outstanding_account_id
# (odoo19c: addons/account/models/account_payment.py:74, :87 y :123): la
# línea de método de pago del pago, calculada y almacenada, y los dos
# campos almacenados que salen de ella. Las filas existentes los reciben
# de su diario.

import django.db.models.deletion
from django.db import migrations, models

from orm.migration_operations import ComputeStoredFields


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0049_payment_partner_res_partner"),
        ("base", "0118_set_null_ondelete_block_d"),
    ]

    operations = [
        migrations.AddField(
            model_name="accountpayment",
            name="outstanding_account_id",
            field=models.ForeignKey(
                blank=True,
                db_column="outstanding_account_id",
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="account.accountaccount",
            ),
        ),
        migrations.AddField(
            model_name="accountpayment",
            name="payment_method_id",
            field=models.ForeignKey(
                blank=True,
                db_column="payment_method_id",
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="account.accountpaymentmethod",
            ),
        ),
        migrations.AddField(
            model_name="accountpayment",
            name="payment_method_line_id",
            field=models.ForeignKey(
                blank=True,
                db_column="payment_method_line_id",
                help_text=(
                    "Manual: Pay or Get paid by any method outside of Odoo "
                    "(Odoo payment_method_line_id)."
                ),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="payments",
                to="account.accountpaymentmethodline",
            ),
        ),
        migrations.AddIndex(
            model_name="accountpayment",
            index=models.Index(
                condition=models.Q(("outstanding_account_id__isnull", False)),
                fields=["outstanding_account_id"],
                name="account_payment__outs_044e9fa2",
            ),
        ),
        ComputeStoredFields(
            'account', 'accountpayment',
            ['payment_method_line_id', 'payment_method_id',
             'outstanding_account_id']),
    ]
