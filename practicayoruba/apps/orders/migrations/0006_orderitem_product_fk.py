"""
Agrega OrderItem.product — FK nullable a catalogue.Product.

No forma parte del snapshot financiero (product_name/sku/unit_price son el snapshot).
Se usa para resolver el thumbnail en el listado de órdenes (H-ORD-003 / UC-ORD-03)
y para restaurar stock en cancelaciones (UC-ORD-04 / UC-INV-03).

null=True porque el producto puede ser eliminado después del checkout.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0005_sync_model_drift'),
        ('catalogue', '0008_fix_postgres_fields_to_mariadb'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderitem',
            name='product',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='order_items',
                to='catalogue.product',
                help_text='Producto original. null si fue eliminado. No es snapshot.',
            ),
        ),
    ]
