# ≙ purchase.order invoice_ids e invoice_count
# (odoo19c: purchase_order.py:125-126).

from django.db import migrations, models

from orm.migration_operations import ComputeStoredFields


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0037_purchase_line_link"),
        ("purchase", "0014_order_sequence"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchaseorder",
            name="invoice_count",
            field=models.IntegerField(
                default=0, editable=False, verbose_name="Bill Count"
            ),
        ),
        migrations.AddField(
            model_name="purchaseorder",
            name="invoice_ids",
            field=models.ManyToManyField(
                blank=True,
                editable=False,
                related_name="+",
                to="account.accountmove",
                verbose_name="Bills",
            ),
        ),
        ComputeStoredFields('purchase', 'purchaseorder', [
            'invoice_ids', 'invoice_count']),
    ]
