"""Columnas ``translate=True`` a ``jsonb`` ``{idioma: valor}`` (TASK-GEN-0060).

``ConvertColumnTranslatable`` es un ``AlterField`` que convierte la columna
por el campo: el texto actual queda bajo ``en_US``
(``tools.sql.convert_column_translatable``) y la reversa lo devuelve a la
columna de texto.
"""

import orm.fields_textual
from django.db import migrations

from orm.migration_operations import ConvertColumnTranslatable


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0103_compute_new_stored_columns"),
    ]

    operations = [
        ConvertColumnTranslatable(
            model_name="irmodelfields",
            name="field_description",
            field=orm.fields_textual.TranslatedChar(
                blank=True,
                default="",
                max_length=255,
                verbose_name="Etiqueta del campo",
            ),
        ),
    ]
