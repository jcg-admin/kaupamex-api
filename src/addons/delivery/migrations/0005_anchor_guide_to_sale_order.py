# E4-pre (H-API-26): la guía de envío se ancla a la orden canónica
# (sale.SaleOrder OneToOne NOT NULL/PROTECT); la FK al espejo pasa a
# nullable/SET_NULL hasta su retiro en E5. Backfill total por construcción
# (Order.sale_order NOT NULL desde V5d). Ver payment/0005 para el detalle
# del patrón Subquery/OuterRef.

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import OuterRef, Subquery


def backfill_sale_order(apps, schema_editor):
    ShipmentGuide = apps.get_model('delivery', 'ShipmentGuide')
    Order = apps.get_model('orders', 'Order')
    ShipmentGuide.objects.filter(sale_order__isnull=True).update(
        sale_order_id=Subquery(
            Order.objects.filter(pk=OuterRef('order_id'))
            .values('sale_order_id')[:1]))


class Migration(migrations.Migration):

    dependencies = [
        ("delivery", "0004_shipmentguide_sale_order"),
        ("orders", "0011_retire_order_status_mirror"),
        ("sale", "0011_saleorder_carrier_and_cancellation"),
    ]

    operations = [
        migrations.RunPython(backfill_sale_order, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="shipmentguide",
            name="sale_order",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="shipment_guide",
                to="sale.saleorder",
            ),
        ),
        migrations.AlterField(
            model_name="shipmentguide",
            name="order",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="shipment_guide",
                to="orders.order",
            ),
        ),
    ]
