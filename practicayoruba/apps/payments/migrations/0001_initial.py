"""Sprint 15 — Payment, Refund, PaymentGatewayEvent."""
from decimal import Decimal
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ('orders', '0002_timestampedmodel_orders'),
    ]

    operations = [
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id',                  models.BigAutoField(auto_created=True, primary_key=True)),
                ('created_at',          models.DateTimeField(auto_now_add=True)),
                ('updated_at',          models.DateTimeField(auto_now=True)),
                ('gateway',             models.CharField(max_length=20, db_index=True,
                    choices=[('MERCADOPAGO','MercadoPago'),('PAYPAL','PayPal')])),
                ('gateway_payment_id',  models.CharField(max_length=200, null=True, blank=True, unique=True)),
                ('preference_id',       models.CharField(max_length=200, null=True, blank=True)),
                ('status',              models.CharField(max_length=30, db_index=True, default='PENDING',
                    choices=[('PENDING','Pendiente'),('APPROVED','Aprobado'),('FAILED','Fallido'),
                             ('REFUNDED','Reembolsado'),('PARTIALLY_REFUNDED','Reembolso parcial'),
                             ('CANCELLED','Cancelado')])),
                ('amount',              models.DecimalField(decimal_places=2, max_digits=10,
                    validators=[django.core.validators.MinValueValidator(Decimal('0.01'))])),
                ('installments',        models.PositiveIntegerField(default=1)),
                ('order',               models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='payments', to='orders.order')),
            ],
            options={'db_table': 'payments_payment', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='Refund',
            fields=[
                ('id',               models.BigAutoField(auto_created=True, primary_key=True)),
                ('created_at',       models.DateTimeField(auto_now_add=True)),
                ('updated_at',       models.DateTimeField(auto_now=True)),
                ('amount',           models.DecimalField(decimal_places=2, max_digits=10,
                    validators=[django.core.validators.MinValueValidator(Decimal('0.01'))])),
                ('reason',           models.TextField(blank=True, default='')),
                ('gateway_refund_id', models.CharField(max_length=200, null=True, blank=True)),
                ('status',           models.CharField(max_length=20, db_index=True, default='PENDING',
                    choices=[('PENDING','Pendiente'),('APPROVED','Aprobado'),('FAILED','Fallido')])),
                ('payment',          models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='refunds', to='payments.payment')),
            ],
            options={'db_table': 'payments_refund', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='PaymentGatewayEvent',
            fields=[
                ('id',         models.BigAutoField(auto_created=True, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('event_type', models.CharField(max_length=40, db_index=True,
                    choices=[('WEBHOOK_RECEIVED','Webhook recibido'),
                             ('PREFERENCE_CREATED','Preferencia creada'),
                             ('PAYMENT_APPROVED','Pago aprobado'),
                             ('PAYMENT_FAILED','Pago fallido'),
                             ('REFUND_CREATED','Reembolso creado')])),
                ('raw_body',   models.TextField()),
                ('payment',    models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='gateway_events', to='payments.payment')),
            ],
            options={'db_table': 'payments_gateway_event', 'ordering': ['-created_at']},
        ),
    ]
