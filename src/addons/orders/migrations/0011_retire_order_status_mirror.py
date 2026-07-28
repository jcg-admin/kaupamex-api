"""O2C V5d (ADR-024) — retiro de la columna espejo ``orders_order.status``.

Cierra el cut-over ``orders → sale``: el estado de una orden deja de vivir en
un enum monolítico y pasa a derivarse de los tres ejes canónicos (comercial
``sale.SaleOrder.state`` · pago ``payment.Payment`` · fulfillment
``delivery.ShipmentGuide``) vía ``orders.status_projection.order_status``.

Dos operaciones acopladas — la segunda es la que hace irreversible al fallback:

1. ``RemoveField(status)`` — R8 (``api@d688ae2``) ya había dejado la columna sin
   escritores; aquí se elimina.
2. ``AlterField(sale_order)`` a ``null=False`` + ``on_delete=PROTECT``. Sin la
   columna espejo, una fila sin canónica no tiene estado que proyectar; y
   ``SET_NULL`` habría reintroducido el ``NULL`` al borrar una ``SaleOrder``
   (H-API-19). ``PROTECT`` cierra esa puerta.

Sin data migration de backfill: el port 0008 de ``sale`` sólo creó ``SaleOrder``
para los drafts (que borró), de modo que "enlazable" ≈ 0 — una huérfana habría
que **sintetizarla**, no enlazarla. La decisión del ejecutor (2026-07-27) es que
el proyecto está en desarrollo, sin datos reales y con la base recreable, así
que el retiro procede sin backfill. Ver ``plan-backfill-sale-order-o2c`` y
H-API-19/H-API-20.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('sale', '0008_port_draft_orders_to_sale'),
        ('orders', '0010_delete_dead_order_proxies'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='order',
            name='status',
        ),
        migrations.AlterField(
            model_name='order',
            name='sale_order',
            field=models.OneToOneField(
                help_text='SaleOrder canónica de la que este Order es espejo (V3a).',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='legacy_order',
                to='sale.saleorder',
            ),
        ),
    ]
