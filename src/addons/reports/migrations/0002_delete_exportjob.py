"""Retira ``ExportJob`` del estado de ``reports`` (movido a ``base``).

State-only (``SeparateDatabaseAndState``): la tabla ``report_export_job`` NO se
toca — la adopta ``base.0012_report_export_job``. Aquí sólo se elimina el modelo
del estado de ``reports`` para que ``reports`` quede como paquete controlador
sin modelos propios. Depende de la migración de ``base`` que crea el modelo en
su estado, para que el grafo no quede con el modelo huérfano.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0001_initial"),
        ("base", "0012_report_export_job"),
    ]

    state_operations = [
        migrations.DeleteModel(name="ExportJob"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=state_operations,
            database_operations=[],
        ),
    ]
