# ≙ purchase.order.line qty_invoiced y qty_to_invoice (odoo19c:
# purchase_order_line.py:58,66-67). Las líneas existentes reciben su
# cantidad facturada y por facturar calculadas desde sus facturas.

from django.db import migrations, models

from orm.migration_operations import ComputeStoredFields


class Migration(migrations.Migration):

    dependencies = [
        ("purchase", "0019_line_qty_received"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchaseorderline",
            name="qty_invoiced",
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                editable=False,
                max_digits=16,
                null=True,
                verbose_name="Billed Qty",
            ),
        ),
        migrations.AddField(
            model_name="purchaseorderline",
            name="qty_to_invoice",
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                editable=False,
                max_digits=16,
                null=True,
                verbose_name="To Invoice Quantity",
            ),
        ),
        ComputeStoredFields(
            "purchase", "purchaseorderline",
            ["qty_invoiced", "qty_to_invoice"]),
    ]
