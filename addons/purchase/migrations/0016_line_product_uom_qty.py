# ≙ purchase.order.line product_uom_qty
# (odoo19c: purchase_order_line.py:24,484-490); las líneas existentes
# reciben su cantidad en la unidad del producto.

from django.db import migrations, models

from orm.migration_operations import ComputeStoredFields


class Migration(migrations.Migration):

    dependencies = [
        ("purchase", "0015_order_invoices"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchaseorderline",
            name="product_uom_qty",
            field=models.FloatField(
                blank=True, editable=False, null=True,
                verbose_name="Total Quantity"
            ),
        ),
        ComputeStoredFields('purchase', 'purchaseorderline',
                            ['product_uom_qty']),
    ]
