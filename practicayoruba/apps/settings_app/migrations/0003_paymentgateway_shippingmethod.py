"""
Migration Sprint 8:
- PaymentGateway (UC-CFG-01)
- ShippingMethod (UC-CFG-02)
"""
from decimal import Decimal
from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('settings_app', '0002_sitesettings_avatar_max_size_mb_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentGateway',
            fields=[
                ('id',              models.BigAutoField(auto_created=True, primary_key=True)),
                ('provider',        models.CharField(
                    choices=[('mercado_pago', 'Mercado Pago'), ('paypal', 'PayPal')],
                    max_length=20, unique=True, verbose_name='Proveedor de pago',
                )),
                ('is_active',       models.BooleanField(default=False, db_index=True,
                                        verbose_name='Activo')),
                ('credentials_enc', models.TextField(blank=True, default='',
                                        verbose_name='Credenciales cifradas (Fernet JSON)')),
                ('verified_at',     models.DateTimeField(blank=True, null=True,
                                        verbose_name='Última verificación de conectividad')),
                ('updated_at',      models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'settings_payment_gateway', 'verbose_name': 'Gateway de pago'},
        ),
        migrations.CreateModel(
            name='ShippingMethod',
            fields=[
                ('id',             models.BigAutoField(auto_created=True, primary_key=True)),
                ('name',           models.CharField(max_length=100, verbose_name='Nombre')),
                ('description',    models.TextField(blank=True, default='')),
                ('cost',           models.DecimalField(
                    decimal_places=2, max_digits=8,
                    validators=[django.core.validators.MinValueValidator(Decimal('0.00'))],
                    verbose_name='Costo de envio',
                )),
                ('estimated_days', models.PositiveSmallIntegerField(
                    validators=[django.core.validators.MinValueValidator(1)],
                    verbose_name='Dias habiles estimados',
                )),
                ('is_active',      models.BooleanField(default=True, db_index=True)),
                ('free_threshold', models.DecimalField(
                    blank=True, null=True, decimal_places=2, max_digits=10,
                    verbose_name='Monto minimo para envio gratis',
                )),
                ('zones',          models.JSONField(default=list, blank=True)),
                ('updated_at',     models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'settings_shipping_method',
                'ordering': ['cost', 'name'],
                'verbose_name': 'Metodo de envio',
            },
        ),
    ]
