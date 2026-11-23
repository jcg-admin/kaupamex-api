"""Porta ``stock.picking.scheduled_date`` (``odoo19c: :595-598``).

El campo es almacenado y calculado: ``ComputeStoredFields`` lo calcula
sobre las filas existentes con ``_compute_scheduled_date`` (``:864-873``),
como la fuente marca para cómputo las filas de una columna calculada nueva
(``odoo19c: odoo/orm/models.py:3220-3238``).
"""

import django.utils.timezone
from django.db import migrations, models

from orm.migration_operations import ComputeStoredFields


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0032_restrict_ondelete_block_f"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="stockpicking",
            options={
                "ordering": ["-priority", "scheduled_date", "-id"],
                "verbose_name": "Transferencia de inventario",
                "verbose_name_plural": "Transferencias de inventario",
            },
        ),
        migrations.AddField(
            model_name="stockpicking",
            name="scheduled_date",
            field=models.DateTimeField(
                db_index=True,
                default=django.utils.timezone.now,
                help_text=(
                    "Fecha prevista para procesar la primera parte del "
                    "envío. Fijarla a mano la fija como fecha prevista de "
                    "todos los movimientos (Odoo scheduled_date)."
                ),
                verbose_name="Fecha prevista",
            ),
        ),
        ComputeStoredFields("stock", "stockpicking", ["scheduled_date"]),
    ]
