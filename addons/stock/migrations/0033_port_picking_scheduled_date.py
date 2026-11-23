"""Porta ``stock.picking.scheduled_date`` (``odoo19c: :595-598``).

El campo es almacenado y calculado: las filas existentes reciben el valor
que ``_compute_scheduled_date`` (``:864-873``) les daría, y las que no
tienen movimientos pendientes conservan su fecha de alta, que es lo que el
``default=fields.Datetime.now`` de la fuente les habría puesto al crearse.
"""

import django.utils.timezone
from django.db import migrations, models
from django.db.models import Max, Min, Q


def backfill_scheduled_date(apps, schema_editor):
    """Rellena ``scheduled_date`` con la regla de
    ``_compute_scheduled_date``.
    """

    StockPicking = apps.get_model("stock", "StockPicking")
    StockMove = apps.get_model("stock", "StockMove")
    pending = ~Q(state__in=("done", "cancel"))
    for picking in StockPicking.objects.all().iterator():
        moves = StockMove.objects.filter(pending, picking_id=picking.pk)
        aggregate = (
            Min("date") if picking.move_type == "direct" else Max("date")
        )
        date = moves.aggregate(value=aggregate)["value"]
        StockPicking.objects.filter(pk=picking.pk).update(
            scheduled_date=date or picking.create_date
        )


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
        migrations.RunPython(
            backfill_scheduled_date, migrations.RunPython.noop
        ),
    ]
