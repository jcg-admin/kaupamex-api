# ≙ purchase.order name default New y date_order default now
# (odoo19c: purchase_order.py:79-89).

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("purchase", "0013_line_unit"),
    ]

    operations = [
        migrations.AlterField(
            model_name="purchaseorder",
            name="date_order",
            field=models.DateTimeField(
                blank=True,
                default=django.utils.timezone.now,
                help_text="Fecha de la orden (Odoo date_order).",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="purchaseorder",
            name="name",
            field=models.CharField(
                blank=True,
                default="New",
                help_text="Referencia de la orden (Odoo purchase.order.name).",
                max_length=32,
            ),
        ),
    ]
