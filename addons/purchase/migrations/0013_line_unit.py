# ≙ purchase.order.line product_uom_id (odoo19c: purchase_order_line.py:36).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("purchase", "0012_order_state_machine"),
        ("uom", "0008_log_access_user_column_names"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchaseorderline",
            name="product_uom_id",
            field=models.ForeignKey(
                blank=True,
                db_column="product_uom_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="uom.uom",
                verbose_name="Unit",
            ),
        ),
    ]
