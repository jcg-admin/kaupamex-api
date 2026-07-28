# E4-pre (H-API-26): la reseña ancla su prueba de compra a la orden canónica
# (sale.SaleOrder NOT NULL/PROTECT); la FK al espejo pasa a nullable/SET_NULL
# hasta su retiro en E5. Backfill total por construcción (Order.sale_order
# NOT NULL desde V5d). Ver payment/0005 para el detalle Subquery/OuterRef.

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import OuterRef, Subquery


def backfill_sale_order(apps, schema_editor):
    Review = apps.get_model('rating', 'Review')
    Order = apps.get_model('orders', 'Order')
    Review.objects.filter(sale_order__isnull=True).update(
        sale_order_id=Subquery(
            Order.objects.filter(pk=OuterRef('order_id'))
            .values('sale_order_id')[:1]))


class Migration(migrations.Migration):

    dependencies = [
        ("rating", "0002_review_sale_order"),
        ("orders", "0011_retire_order_status_mirror"),
        ("sale", "0011_saleorder_carrier_and_cancellation"),
    ]

    operations = [
        migrations.RunPython(backfill_sale_order, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="review",
            name="sale_order",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reviews",
                to="sale.saleorder",
            ),
        ),
        migrations.AlterField(
            model_name="review",
            name="order",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reviews",
                to="orders.order",
            ),
        ),
    ]
