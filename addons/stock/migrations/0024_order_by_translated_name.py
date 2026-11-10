"""Ordenar por el texto del idioma activo de ``name`` (TASK-GEN-0060).

``name`` es traducible: el orden por defecto sigue ``TranslatedValue``, el
mismo texto que ``Field.to_sql`` da en la fuente, no el ``jsonb`` crudo.
"""

import orm.fields_textual
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0023_translatable_columns_jsonb"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="productremoval",
            options={
                "ordering": [
                    models.OrderBy(orm.fields_textual.TranslatedValue("name"))
                ],
                "verbose_name": "Estrategia de retiro",
                "verbose_name_plural": "Estrategias de retiro",
            },
        ),
    ]
