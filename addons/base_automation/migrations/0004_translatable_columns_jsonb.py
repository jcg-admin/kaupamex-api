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
            "base_automation",
            "0003_alter_baseautomation_trg_date_calendar_and_more",
        ),
    ]

    operations = [
        ConvertColumnTranslatable(
            model_name="baseautomation",
            name="name",
            field=orm.fields_textual.TranslatedChar(
                help_text=(
                    "Odoo name (tracking=True en la referencia: sin chatter "
                    "genérico portado, el seguimiento de cambios no aplica)."
                ),
                max_length=255,
                verbose_name="Nombre de la regla",
            ),
        ),
    ]
