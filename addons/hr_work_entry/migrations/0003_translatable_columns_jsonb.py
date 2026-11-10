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
        (
            "hr_work_entry",
            "0002_alter_hrworkentry_name_alter_hrworkentry_state_and_more",
        ),
    ]

    operations = [
        ConvertColumnTranslatable(
            model_name="hrworkentrytype",
            name="display_code",
            field=orm.fields_textual.TranslatedChar(
                blank=True,
                default="",
                help_text=(
                    "This code can be changed, it is only for a display "
                    "purpose (3 letters max)"
                ),
                max_length=3,
                verbose_name="Display Code",
            ),
        ),
        ConvertColumnTranslatable(
            model_name="hrworkentrytype",
            name="name",
            field=orm.fields_textual.TranslatedChar(
                help_text="Odoo name (required, translate)."
            ),
        ),
    ]
