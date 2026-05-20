"""
Remove redundant UniqueConstraint(fields=['user'], condition=Q(user__isnull=False))
en cart.Cart.

Cart.user es OneToOneField que ya crea UNIQUE a nivel BD; SQL standard
permite multiples NULLs en columnas UNIQUE, asi que la constraint
parcial era redundante y solo emitia el system check W036 sobre
MariaDB ("does not support unique constraints with conditions").

Esta migracion solo afecta el estado de Django: el constraint nunca
se creo en la BD (Django lo omite cuando el backend no lo soporta).
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cart', '0004_sync_model_drift'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='cart',
            name='unique_user_cart',
        ),
    ]
