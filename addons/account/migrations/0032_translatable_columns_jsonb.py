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
        ("account", "0031_compute_new_stored_columns"),
    ]

    operations = [
        ConvertColumnTranslatable(
            model_name="accounttax",
            name="invoice_label",
            field=orm.fields_textual.TranslatedChar(
                blank=True, max_length=255, null=True
            ),
        ),
    ]
