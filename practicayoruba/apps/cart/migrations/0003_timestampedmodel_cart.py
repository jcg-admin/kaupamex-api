"""
Migración de infraestructura: herencia-modelos-django — apps.cart

Cambios en BD:
  CartItem:    ADD created_at + ADD updated_at
  SavedCart:   RENAME saved_at → updated_at + ADD created_at
  SavedCartItem: ADD created_at + ADD updated_at

Cart: refactor puro (ya tenía ambos campos) — sin cambios en BD.
"""
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('cart', '0002_cart_voucher_fk'),
    ]

    operations = [
        # ─── CartItem: ADD created_at + updated_at ─────────────────────────
        migrations.AddField(
            model_name='cartitem',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True,
                                       default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='cartitem',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),

        # ─── SavedCart: RENAME saved_at → updated_at + ADD created_at ──────
        migrations.RenameField(
            model_name='savedcart',
            old_name='saved_at',
            new_name='updated_at',
        ),
        migrations.AddField(
            model_name='savedcart',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True,
                                       default=django.utils.timezone.now),
            preserve_default=False,
        ),

        # ─── SavedCartItem: ADD created_at + updated_at ────────────────────
        migrations.AddField(
            model_name='savedcartitem',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True,
                                       default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='savedcartitem',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
