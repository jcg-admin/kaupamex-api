"""Retira ``SearchEntry`` del estado de ``search_history`` (movido a website).

State-only (``SeparateDatabaseAndState``): la tabla ``search_history_entry`` NO
se toca — la adopta ``website.0003_searchentry``. Aquí sólo se elimina el modelo
del estado de ``search_history`` para que quede como paquete controlador sin
modelos propios. Depende de la migración de ``website`` que crea el modelo en su
estado, para que el grafo no quede con el modelo huérfano.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("search_history", "0001_initial"),
        ("website", "0003_searchentry"),
    ]

    state_operations = [
        migrations.DeleteModel(name="SearchEntry"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=state_operations,
            database_operations=[],
        ),
    ]
