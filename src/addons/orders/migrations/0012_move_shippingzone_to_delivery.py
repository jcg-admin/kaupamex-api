"""Saca ``ShippingZone`` del estado de ``orders`` — H-API-46.

Sólo **estado**: la tabla no se toca aquí. La operación física (el rename a
``delivery_shipping_zone``) vive en la migración hermana de ``delivery``, que
depende de ésta. Partirlo así es lo que permite mover el modelo entre addons sin
que Django vea dos modelos compitiendo por la misma tabla en ningún punto del
plan.

``ShippingZone`` nunca fue una entidad espejo: es dominio de entrega que estaba
alojado en el addon del pedido por historia. Retirar ``orders`` en E5 sin este
paso previo se la habría llevado por delante.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0011_retire_order_status_mirror'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[migrations.DeleteModel(name='ShippingZone')],
            database_operations=[],
        ),
    ]
