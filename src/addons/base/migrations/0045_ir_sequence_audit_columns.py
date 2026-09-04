"""Las columnas de auditoría de ``ir.sequence`` y su rango (tarea #40).

La fuente no declara ``_log_access = False`` en ninguna de las dos clases
(``odoo19c: odoo/addons/base/models/ir_sequence.py``), así que su ORM les añade
las columnas de auditoría. Aquí las dos pasan a heredar ``TimeStampedModel``,
que es la forma adoptada del log-access en este árbol.

**Escrita a mano, y ése es el punto.** ``makemigrations`` no puede generarla
solo: añadir un campo con ``auto_now_add`` a una tabla que ya tiene filas abre
su cuestionario interactivo, y responderlo deja el ``default`` decidido en una
sesión y no en el repositorio. Aquí el ``default`` es explícito —
``django.utils.timezone.now``— con ``preserve_default=False``, que lo aplica a
las filas existentes y luego lo retira del modelo, dejando el ``auto_now_add``
como único poblador de las filas nuevas.
"""

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0044_res_device_log_partial_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="irsequence",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="irsequence",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name="irsequencedaterange",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="irsequencedaterange",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
