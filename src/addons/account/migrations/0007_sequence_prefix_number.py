"""Parte ``name`` en prefijo + número entero, y rellena lo ya numerado.

El backfill NO es opcional: sin él, los asientos existentes quedan con
``sequence_number = 0`` y ``sequence_prefix = ''``, así que el ``MAX`` del
siguiente asiento no los ve y la numeración vuelve a empezar en 00001 —
chocando con el ``UNIQUE`` de ``name``. La columna nueva sólo sirve si
describe también el pasado. Ver H-API-339.
"""
from django.db import migrations, models


def partir_nombres(apps, schema_editor):
    """Deriva las dos columnas de los ``name`` ya asignados.

    Sólo toca los que tienen forma ``prefijo/NNNNN``: los borradores (``/``) y
    cualquier nombre sin número quedan en su default, que es lo correcto —
    todavía no ocupan un lugar en la secuencia.
    """
    AccountMove = apps.get_model('account', 'AccountMove')
    alias = schema_editor.connection.alias
    pendientes = []
    for move in AccountMove.objects.using(alias).exclude(name='/').iterator():
        if not move.name or '/' not in move.name:
            continue
        base, _, ultimo = move.name.rpartition('/')
        if not ultimo.isdigit():
            continue
        move.sequence_prefix = f'{base}/'
        move.sequence_number = int(ultimo)
        pendientes.append(move)
    if pendientes:
        AccountMove.objects.using(alias).bulk_update(
            pendientes, ['sequence_prefix', 'sequence_number'], batch_size=500,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0006_accountreportexpression_accountreport_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="accountmove",
            name="sequence_number",
            field=models.IntegerField(
                db_index=True,
                default=0,
                help_text="El número dentro del prefijo, como entero. Es la columna que se agrega con MAX para obtener el siguiente (Odoo sequence_number).",
            ),
        ),
        migrations.AddField(
            model_name="accountmove",
            name="sequence_prefix",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text="Todo lo que precede al número en `name`, p. ej. ``INV/VTA/2026/`` (Odoo sequence_prefix).",
                max_length=255,
            ),
        ),
        migrations.RunPython(partir_nombres, migrations.RunPython.noop),
    ]
