"""
Migration — Rename status value 'PAGADA' → 'PAID' in orders_order.

H-ORD-S01: canon-idioma residual. All enum values must be EN.
'PAGADA' was the only Spanish string surviving the T-709 sweep.

Also updates OrderStatusLog.previous_status and new_status fields
(plain CharField, not choices-constrained) to keep audit history consistent.
"""
from django.db import migrations, models


def pagada_to_paid(apps, schema_editor):
    db = schema_editor.connection.alias

    Order = apps.get_model('orders', 'Order')
    Order.objects.using(db).filter(status='PAGADA').update(status='PAID')

    OrderStatusLog = apps.get_model('orders', 'OrderStatusLog')
    OrderStatusLog.objects.using(db).filter(previous_status='PAGADA').update(
        previous_status='PAID'
    )
    OrderStatusLog.objects.using(db).filter(new_status='PAGADA').update(
        new_status='PAID'
    )


def paid_to_pagada(apps, schema_editor):
    """Reverse: restore Spanish value for rollback support."""
    db = schema_editor.connection.alias

    Order = apps.get_model('orders', 'Order')
    Order.objects.using(db).filter(status='PAID').update(status='PAGADA')

    OrderStatusLog = apps.get_model('orders', 'OrderStatusLog')
    OrderStatusLog.objects.using(db).filter(previous_status='PAID').update(
        previous_status='PAGADA'
    )
    OrderStatusLog.objects.using(db).filter(new_status='PAID').update(
        new_status='PAGADA'
    )


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0015_orderstatuslog_created_at_db_index'),
    ]

    operations = [
        migrations.RunPython(pagada_to_paid, reverse_code=paid_to_pagada),
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(
                choices=[
                    ('PENDING',           'Pendiente de pago'),
                    ('PROCESSING',        'Procesando pago'),
                    ('PAID',              'Pagado'),
                    ('IN_PREPARATION',    'En preparación'),
                    ('SHIPPED',           'Enviado'),
                    ('DELIVERED',         'Entregado'),
                    ('CANCELLED',         'Cancelado'),
                    ('CANCELLED_TIMEOUT', 'Cancelado por timeout'),
                    ('REFUNDED',          'Reembolsado'),
                ],
                db_index=True,
                default='PENDING',
                max_length=20,
            ),
        ),
    ]
