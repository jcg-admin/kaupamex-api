"""``origin``, ``fiscal_position_id`` y ``payment_term_id`` de
``purchase.order`` (``odoo19c: purchase_order.py:80-82,143,153``)."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0039_parent_state"),
        ("purchase", "0020_line_qty_invoiced"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchaseorder",
            name="fiscal_position_id",
            field=models.ForeignKey(
                blank=True,
                db_column="fiscal_position_id",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="account.accountfiscalposition",
                verbose_name="Fiscal Position",
            ),
        ),
        migrations.AddField(
            model_name="purchaseorder",
            name="origin",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "Reference of the document that generated this purchase "
                    "order request (e.g. a sales order)"),
                max_length=255,
                verbose_name="Source",
            ),
        ),
        migrations.AddField(
            model_name="purchaseorder",
            name="payment_term_id",
            field=models.ForeignKey(
                blank=True,
                db_column="payment_term_id",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="account.accountpaymentterm",
                verbose_name="Payment Terms",
            ),
        ),
    ]
