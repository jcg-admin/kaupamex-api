"""Sprint 13 — Voucher y VoucherChangeLog."""
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Voucher',
            fields=[
                ('id',                 models.BigAutoField(auto_created=True, primary_key=True)),
                ('code',               models.CharField(max_length=50, unique=True)),
                ('voucher_type',       models.CharField(
                    max_length=20, db_index=True,
                    choices=[('FIXED','Descuento fijo'),('PERCENTAGE','Porcentaje'),
                             ('FREE_SHIPPING','Envio gratis')],
                )),
                ('discount_value',     models.DecimalField(
                    blank=True, null=True, decimal_places=2, max_digits=10,
                    validators=[django.core.validators.MinValueValidator(Decimal('0.01'))],
                )),
                ('discount_pct',       models.DecimalField(
                    blank=True, null=True, decimal_places=2, max_digits=5,
                    validators=[django.core.validators.MinValueValidator(Decimal('0.01'))],
                )),
                ('max_discount',       models.DecimalField(
                    blank=True, null=True, decimal_places=2, max_digits=10)),
                ('min_order_amount',   models.DecimalField(
                    decimal_places=2, default=Decimal('0.00'), max_digits=10,
                    validators=[django.core.validators.MinValueValidator(Decimal('0.00'))],
                )),
                ('max_uses',           models.PositiveIntegerField(blank=True, null=True)),
                ('current_uses',       models.PositiveIntegerField(default=0)),
                ('valid_from',         models.DateTimeField()),
                ('valid_until',        models.DateTimeField(blank=True, null=True)),
                ('is_active',          models.BooleanField(default=True, db_index=True)),
                ('restricted_to_email', models.EmailField(blank=True, null=True)),
                ('deactivated_at',     models.DateTimeField(blank=True, null=True)),
                ('created_at',         models.DateTimeField(auto_now_add=True)),
                ('updated_at',         models.DateTimeField(auto_now=True)),
                ('created_by',         models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_vouchers', to=settings.AUTH_USER_MODEL,
                )),
                ('deactivated_by',     models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='deactivated_vouchers', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'voucher_voucher', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='VoucherChangeLog',
            fields=[
                ('id',         models.BigAutoField(auto_created=True, primary_key=True)),
                ('changes',    models.JSONField()),
                ('changed_at', models.DateTimeField(auto_now_add=True)),
                ('changed_by', models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                )),
                ('voucher',    models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='change_log', to='voucher.voucher',
                )),
            ],
            options={'db_table': 'voucher_change_log', 'ordering': ['-changed_at']},
        ),
    ]
