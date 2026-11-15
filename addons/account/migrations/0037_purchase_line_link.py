# ≙ account.move.line is_downpayment y purchase_line_id
# (odoo19c: purchase/models/account_invoice.py:527-528).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0036_log_access_user_column_names"),
        ("purchase", "0014_order_sequence"),
    ]

    operations = [
        migrations.AddField(
            model_name="accountmoveline",
            name="is_downpayment",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="accountmoveline",
            name="purchase_line_id",
            field=models.ForeignKey(
                blank=True,
                db_column="purchase_line_id",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="invoice_lines",
                to="purchase.purchaseorderline",
                verbose_name="Purchase Order Line",
            ),
        ),
    ]
