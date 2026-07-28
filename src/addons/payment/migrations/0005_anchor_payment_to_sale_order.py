# E4-pre (H-API-26): inversión del anclaje de ejes — el pago se ancla a la
# orden canónica (sale.SaleOrder), no al espejo (orders.Order).
#
# Hasta aquí el esquema exigía una fila espejo por cada pago (order NOT NULL)
# y toleraba pagos sin canónica (sale_order nullable) — exactamente al revés
# de lo que E5 (baja del espejo) necesita. El backfill es total por
# construcción: Order.sale_order es NOT NULL desde V5d, así que todo pago con
# espejo tiene canónica derivable.
#
# El backfill usa Subquery/OuterRef porque update() no admite referencias de
# campos joined (F('order__sale_order') lanza FieldError).

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import OuterRef, Subquery


def backfill_sale_order(apps, schema_editor):
    Payment = apps.get_model('payment', 'Payment')
    Order = apps.get_model('orders', 'Order')
    Payment.objects.filter(sale_order__isnull=True).update(
        sale_order_id=Subquery(
            Order.objects.filter(pk=OuterRef('order_id'))
            .values('sale_order_id')[:1]))


class Migration(migrations.Migration):

    dependencies = [
        ("payment", "0004_alter_payment_gateway"),
        ("orders", "0011_retire_order_status_mirror"),
        ("sale", "0011_saleorder_carrier_and_cancellation"),
    ]

    operations = [
        migrations.RunPython(backfill_sale_order, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="payment",
            name="sale_order",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="payments",
                to="sale.saleorder",
            ),
        ),
        migrations.AlterField(
            model_name="payment",
            name="order",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="payments",
                to="orders.order",
            ),
        ),
    ]
