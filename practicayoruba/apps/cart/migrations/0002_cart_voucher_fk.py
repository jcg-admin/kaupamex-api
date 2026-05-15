"""
Sprint 13: Agrega Cart.voucher FK a Voucher.
La migración 0001 de cart omitió este campo porque apps.voucher no existía.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('cart', '0001_initial'),
        ('voucher', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='cart',
            name='voucher',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='carts', to='voucher.voucher',
            ),
        ),
    ]
