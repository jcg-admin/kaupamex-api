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
        ("hr_skills", "0002_alter_hrresumeline_certificate_filename_and_more"),
    ]

    operations = [
        ConvertColumnTranslatable(
            model_name="hrresumeline",
            name="name",
            field=orm.fields_textual.TranslatedChar(verbose_name="Nombre"),
        ),
        ConvertColumnTranslatable(
            model_name="hrresumelinetype",
            name="name",
            field=orm.fields_textual.TranslatedChar(verbose_name="Nombre"),
        ),
        ConvertColumnTranslatable(
            model_name="hrskill",
            name="name",
            field=orm.fields_textual.TranslatedChar(verbose_name="Nombre"),
        ),
        ConvertColumnTranslatable(
            model_name="hrskilltype",
            name="name",
            field=orm.fields_textual.TranslatedChar(verbose_name="Nombre"),
        ),
    ]
