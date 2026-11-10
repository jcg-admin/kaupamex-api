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
        ("hr", "0012_alter_hremployee_mobility_card_and_more"),
    ]

    operations = [
        ConvertColumnTranslatable(
            model_name="hrcontracttype",
            name="name",
            field=orm.fields_textual.TranslatedChar(
                help_text="Nombre del tipo de contrato (Odoo name).",
                verbose_name="Nombre",
            ),
        ),
        ConvertColumnTranslatable(
            model_name="hrdeparturereason",
            name="name",
            field=orm.fields_textual.TranslatedChar(
                help_text="Nombre del motivo de baja (Odoo name).",
                verbose_name="Motivo",
            ),
        ),
    ]
