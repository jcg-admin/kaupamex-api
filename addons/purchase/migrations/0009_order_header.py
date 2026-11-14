"""Cabecera de ``purchase.order`` y ``purchase.order.line``: ``priority``,
``partner_ref`` y ``sequence``, y el orden de la fuente
(``odoo19c: purchase_order.py:26,78-87``; ``purchase_order_line.py:17,22``)."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("purchase", "0008_log_access_user_column_names"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="purchaseorder",
            options={
                "ordering": ["-priority", "-id"],
                "verbose_name": "Orden de compra",
                "verbose_name_plural": "Órdenes de compra",
            },
        ),
        migrations.AlterModelOptions(
            name="purchaseorderline",
            options={
                "ordering": ["order_id", "sequence", "id"],
                "verbose_name": "Línea de orden de compra",
                "verbose_name_plural": "Líneas de orden de compra",
            },
        ),
        migrations.AddField(
            model_name="purchaseorder",
            name="partner_ref",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "Reference of the sales order or bid sent by the vendor. "
                    "It's used to do the matching when you receive the "
                    "products as this reference is usually written on the "
                    "delivery order sent by your vendor."
                ),
                max_length=255,
                verbose_name="Vendor Reference",
            ),
        ),
        migrations.AddField(
            model_name="purchaseorder",
            name="priority",
            field=models.CharField(
                choices=[("0", "Normal"), ("1", "Urgent")],
                db_index=True,
                default="0",
                max_length=1,
                verbose_name="Priority",
            ),
        ),
        migrations.AddField(
            model_name="purchaseorderline",
            name="sequence",
            field=models.IntegerField(default=10),
        ),
    ]
