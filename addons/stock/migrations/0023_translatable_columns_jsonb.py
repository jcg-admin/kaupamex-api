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
        ("stock", "0022_relax_many2one_by_omission"),
    ]

    operations = [
        ConvertColumnTranslatable(
            model_name="productremoval",
            name="method",
            field=orm.fields_textual.TranslatedChar(
                help_text=(
                    "FIFO, LIFO... — aquí además FEFO, closest y "
                    "least_packages (Odoo method)."
                ),
                max_length=32,
                verbose_name="Method",
            ),
        ),
        ConvertColumnTranslatable(
            model_name="productremoval",
            name="name",
            field=orm.fields_textual.TranslatedChar(
                help_text="Nombre de la estrategia (Odoo name).",
                max_length=120,
                verbose_name="Name",
            ),
        ),
        ConvertColumnTranslatable(
            model_name="stockpickingtype",
            name="name",
            field=orm.fields_textual.TranslatedChar(
                help_text="Nombre del tipo de operación (Odoo name).",
                max_length=100,
                verbose_name="Operation Type",
            ),
        ),
    ]
