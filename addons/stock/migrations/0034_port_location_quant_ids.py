"""El reverso de ``stock.quant.location`` toma el nombre de la fuente.

≙ ``quant_ids = fields.One2many('stock.quant', 'location_id')``
(``odoo19c: addons/stock/models/stock_location.py:80``). Sólo cambia el
estado de Django: el ``related_name`` no tiene columna.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0033_port_picking_scheduled_date"),
    ]

    operations = [
        migrations.AlterField(
            model_name="stockquant",
            name="location",
            field=models.ForeignKey(
                help_text="Ubicación (Odoo location_id).",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="quant_ids",
                to="stock.stocklocation",
            ),
        ),
    ]
