"""
UC-ORD-04: agregar campos de cancelación a Order.
H-ORD-001: los FRs de cancelación referencian estos campos pero no existían.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0002_timestampedmodel_orders'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='cancellation_reason',
            field=models.TextField(blank=True, default='',
                help_text='Motivo de la cancelación (comprador o admin).'),
        ),
        migrations.AddField(
            model_name='order',
            name='cancelled_at',
            field=models.DateTimeField(null=True, blank=True,
                help_text='Timestamp de la cancelación. Null si la orden no está cancelada.'),
        ),
    ]
