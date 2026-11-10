"""Ordenar por el texto del idioma activo de ``name`` (TASK-GEN-0060).

``name`` es traducible: el orden por defecto sigue ``TranslatedValue``, el
mismo texto que ``Field.to_sql`` da en la fuente, no el ``jsonb`` crudo.
"""

import orm.fields_textual
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hr_skills", "0003_translatable_columns_jsonb"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="hrskill",
            options={
                "ordering": [
                    "sequence",
                    models.OrderBy(orm.fields_textual.TranslatedValue("name")),
                ],
                "verbose_name": "Habilidad",
                "verbose_name_plural": "Habilidades",
            },
        ),
        migrations.AlterModelOptions(
            name="hrskilltype",
            options={
                "ordering": [
                    "sequence",
                    models.OrderBy(orm.fields_textual.TranslatedValue("name")),
                ],
                "verbose_name": "Tipo de habilidad",
                "verbose_name_plural": "Tipos de habilidad",
            },
        ),
    ]
