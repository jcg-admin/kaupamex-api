"""``sale_order_line.state`` pasa a ``related='order.state', store=True``.

≙ ``odoo19c: addons/sale/models/sale_order_line.py:56-59``. Las filas
existentes llevaban el estado con que nació la línea, porque nada lo
sincronizaba; ``ComputeStoredFields`` las recalcula con el related, como la
fuente marca para cómputo las filas de un calculado almacenado nuevo
(``odoo19c: odoo/orm/models.py:3220-3238``). La vuelta atrás no deshace el
cómputo: el valor es el correcto con o sin el related.
"""

from django.db import migrations, models

from orm.migration_operations import ComputeStoredFields


class Migration(migrations.Migration):

    dependencies = [
        ("sale", "0020_report_saleorder_iterates_recordset"),
    ]

    operations = [
        migrations.AlterField(
            model_name="saleorderline",
            name="state",
            field=models.CharField(
                blank=True,
                choices=[
                    ("draft", "Cotización"),
                    ("sent", "Cotización enviada"),
                    ("sale", "Orden de venta"),
                    ("cancel", "Cancelada"),
                ],
                db_index=True,
                editable=False,
                help_text=(
                    'Odoo state ("Order Status", related order_id.state, '
                    'store, precompute, copy=False). El vocabulario es el '
                    'de la orden.'
                ),
                max_length=10,
                null=True,
                verbose_name="Estado de la orden",
            ),
        ),
        ComputeStoredFields('sale', 'saleorderline', ['state']),
    ]
