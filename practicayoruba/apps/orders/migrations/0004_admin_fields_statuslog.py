"""
Sprint 19 — UC-ORD-07, UC-ORD-08, UC-ORD-10:
  - Order.admin_cancelled_by (H-ADM-003)
  - OrderStatusLog (H-ADM-001)
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0003_order_cancellation_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # H-ADM-003: admin_cancelled_by en Order
        migrations.AddField(
            model_name='order',
            name='admin_cancelled_by',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='admin_cancelled_orders',
                to=settings.AUTH_USER_MODEL,
                help_text='Admin que canceló la orden. Null si la cancela el comprador.',
            ),
        ),

        # H-ADM-001: OrderStatusLog — auditoría de transiciones
        migrations.CreateModel(
            name='OrderStatusLog',
            fields=[
                ('id',              models.BigAutoField(auto_created=True, primary_key=True)),
                ('created_at',      models.DateTimeField(auto_now_add=True)),
                ('updated_at',      models.DateTimeField(auto_now=True)),
                ('previous_status', models.CharField(max_length=20)),
                ('new_status',      models.CharField(max_length=20)),
                ('notes',           models.TextField(blank=True, default='')),
                ('order',           models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='status_logs', to='orders.order',
                )),
                ('changed_by',      models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='order_status_changes',
                    to=settings.AUTH_USER_MODEL,
                    help_text='Usuario que realizó el cambio. Null si fue el sistema.',
                )),
            ],
            options={
                'db_table':     'orders_status_log',
                'ordering':     ['-created_at'],
                'verbose_name': 'Historial de estado de orden',
            },
        ),
    ]
