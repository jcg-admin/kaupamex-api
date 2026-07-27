"""Delete the six dead Order proxy models (O2C rebanada 5, H-API-06).

PendingOrder, ProcessingOrder, InPreparationOrder, ShippedOrder,
CancelledOrder and RefundedOrder had zero production consumers (PROVEN).
State-only: proxies share ``orders_order`` and own no table, so no schema
change is emitted.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0009_order_sale_order"),
    ]

    operations = [
        migrations.DeleteModel(name="PendingOrder"),
        migrations.DeleteModel(name="ProcessingOrder"),
        migrations.DeleteModel(name="InPreparationOrder"),
        migrations.DeleteModel(name="ShippedOrder"),
        migrations.DeleteModel(name="CancelledOrder"),
        migrations.DeleteModel(name="RefundedOrder"),
    ]
