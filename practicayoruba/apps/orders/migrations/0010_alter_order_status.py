from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0009_checkout_attempt'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(
                choices=[
                    ('PENDING',              'Pendiente de pago'),
                    ('PROCESSING',           'Procesando pago'),
                    ('IN_PREPARATION',       'En preparación'),
                    ('SHIPPED',              'Enviado'),
                    ('DELIVERED',            'Entregado'),
                    ('CANCELLED',            'Cancelado'),
                    ('REFUNDED',             'Reembolsado'),
                    ('CANCELLED_BY_TIMEOUT', 'Cancelado por timeout de pago'),
                ],
                db_index=True,
                default='PENDING',
                max_length=20,
            ),
        ),
    ]
