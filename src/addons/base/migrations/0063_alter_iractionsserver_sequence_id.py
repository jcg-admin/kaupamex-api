"""``sequence_id`` cierra ADR-029 en ``ir.actions.server`` (#141).

Va aparte de 0062 y no dentro: 0062 ya estaba registrado como aplicado
cuando se corrigió la declaración de ``sequence_id`` —el ``db_column`` había
aterrizado por error en ``group_ids``, que es un M2M y no tiene columna—.
Reescribir una migración ya aplicada deja el grafo diciendo una cosa y la
base otra; una migración nueva las vuelve a alinear sin DDL fuera de banda.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0062_alter_iractionsserver_crud_model_id_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="iractionsserver",
            name="sequence_id",
            field=models.ForeignKey(
                blank=True,
                db_column="sequence_id",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="server_actions",
                to="base.irsequence",
                verbose_name="Secuencia a usar",
            ),
        ),
    ]
