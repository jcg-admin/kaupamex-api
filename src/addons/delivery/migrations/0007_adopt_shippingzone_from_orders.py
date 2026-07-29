"""Adopta ``ShippingZone`` en ``delivery`` y renombra su tabla — H-API-46.

Contraparte de ``orders/0012``: aquella saca el modelo del estado de ``orders``
(sin tocar la tabla) y ésta lo crea en el estado de ``delivery``, también sin
tocarla. Sólo después se renombra la tabla física
``orders_shipping_zone`` → ``delivery_shipping_zone``, ya con el modelo en su
addon definitivo.

El orden importa: si ``delivery`` creara el modelo antes de que ``orders`` lo
borre del estado, Django tendría dos modelos apuntando a la misma tabla. De ahí
la dependencia explícita.

Por qué se mueve: ``ShippingZone`` es dominio de **entrega** —su hermano
``ShippingMethod`` ya vive aquí, igual que ``Courier`` y ``CarrierRateCard``—.
Estaba en ``orders`` por historia, y retirar ese addon en E5 la habría
eliminado con el espejo.
"""
from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('delivery', '0006_shippingmethod_product'),
        ('orders', '0012_move_shippingzone_to_delivery'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='ShippingZone',
                    fields=[
                        ('id', models.BigAutoField(
                            auto_created=True, primary_key=True,
                            serialize=False, verbose_name='ID')),
                        ('name', models.CharField(max_length=100)),
                        ('zip_code_prefix', models.CharField(
                            max_length=5, unique=True)),
                        ('is_active', models.BooleanField(default=True)),
                        ('estimated_days_min', models.PositiveSmallIntegerField(
                            blank=True, null=True,
                            help_text='Días hábiles mínimos de entrega en la zona.',
                            validators=[django.core.validators.MinValueValidator(1)])),
                        ('estimated_days_max', models.PositiveSmallIntegerField(
                            blank=True, null=True,
                            help_text='Días hábiles máximos de entrega en la zona.',
                            validators=[django.core.validators.MinValueValidator(1)])),
                        ('cost', models.DecimalField(
                            blank=True, decimal_places=2, max_digits=10, null=True,
                            help_text='Costo de envío específico de la zona. '
                                      'Vacío = usar el del método.',
                            validators=[django.core.validators.MinValueValidator(
                                Decimal('0'))])),
                        ('free_threshold', models.DecimalField(
                            blank=True, decimal_places=2, max_digits=10, null=True,
                            help_text='Compra mínima para envío gratis en la zona. '
                                      'Vacío = usar el del método de envío.',
                            validators=[django.core.validators.MinValueValidator(
                                Decimal('0'))])),
                    ],
                    options={'db_table': 'orders_shipping_zone'},
                ),
            ],
            database_operations=[],
        ),
        migrations.AlterModelTable(
            name='shippingzone',
            table='delivery_shipping_zone',
        ),
    ]
