"""Sprint 14 — Order, OrderItem, OrderValue, OrderAddress."""
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion
import apps.orders.models

class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('chartsize', '0001_initial'),
        ('settings_app', '0004_sitesettings_contact_staticpage'),
    ]

    operations = [
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id',               models.BigAutoField(auto_created=True, primary_key=True)),
                ('order_number',     models.CharField(db_index=True, max_length=20, unique=True)),
                ('guest_email',      models.EmailField(blank=True, null=True)),
                ('status',           models.CharField(
                    db_index=True, default='PENDING', max_length=20,
                    choices=[('PENDING','Pendiente de pago'),
                             ('PROCESSING','Procesando pago'),
                             ('IN_PREPARATION','En preparación'),
                             ('SHIPPED','Enviado'),('DELIVERED','Entregado'),
                             ('CANCELLED','Cancelado'),('REFUNDED','Reembolsado')],
                )),
                ('voucher_code',     models.CharField(blank=True, default='', max_length=50)),
                ('voucher_discount', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10)),
                ('notes',            models.TextField(blank=True, default='')),
                ('created_at',       models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at',       models.DateTimeField(auto_now=True)),
                ('user',             models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='orders', to=settings.AUTH_USER_MODEL,
                )),
                ('shipping_method',  models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='orders', to='settings_app.shippingmethod',
                )),
            ],
            options={'db_table': 'orders_order', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='OrderItem',
            fields=[
                ('id',            models.BigAutoField(auto_created=True, primary_key=True)),
                ('product_name',  models.CharField(max_length=200)),
                ('variant_label', models.CharField(blank=True, default='', max_length=100)),
                ('sku',           models.CharField(max_length=70)),
                ('unit_price',    models.DecimalField(decimal_places=2, max_digits=10)),
                ('quantity',      models.PositiveIntegerField(
                    validators=[django.core.validators.MinValueValidator(1)])),
                ('subtotal',      models.DecimalField(decimal_places=2, max_digits=10)),
                ('order',   models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='items', to='orders.order')),
                ('variant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='order_items', to='chartsize.productvariant')),
            ],
            options={'db_table': 'orders_order_item'},
        ),
        migrations.CreateModel(
            name='OrderValue',
            fields=[
                ('id',            models.BigAutoField(auto_created=True, primary_key=True)),
                ('subtotal',      models.DecimalField(decimal_places=2, max_digits=10)),
                ('tax',           models.DecimalField(decimal_places=2, max_digits=10)),
                ('shipping_cost', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10)),
                ('discount',      models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10)),
                ('total',         models.DecimalField(decimal_places=2, max_digits=10)),
                ('order', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='value', to='orders.order')),
            ],
            options={'db_table': 'orders_order_value'},
        ),
        migrations.CreateModel(
            name='OrderAddress',
            fields=[
                ('id',             models.BigAutoField(auto_created=True, primary_key=True)),
                ('recipient_name', models.CharField(max_length=200)),
                ('street',         models.CharField(max_length=255)),
                ('city',           models.CharField(max_length=100)),
                ('state',          models.CharField(max_length=100)),
                ('zip_code',       models.CharField(max_length=10)),
                ('country',        models.CharField(default='MX', max_length=2)),
                ('phone',          models.CharField(blank=True, default='', max_length=20)),
                ('order', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='address', to='orders.order')),
            ],
            options={'db_table': 'orders_order_address'},
        ),
    ]
