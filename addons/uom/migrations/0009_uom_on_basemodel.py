"""``uom.uom`` sobre ``BaseModel``: tres campos con la forma de la fuente.

≙ ``odoo19c: addons/uom/models/uom_uom.py:35-43``. ``factor`` y ``sequence``
pasan a ser cómputos almacenados y ``related_uom_ids`` un ``One2many``
declarado, así que la FK del hijo lleva ``related_name='+'``. En la base sólo
cambia una cosa: ``sequence`` es un ``Integer`` de la fuente y pierde el
``CHECK`` de entero positivo que ``PositiveIntegerField`` añadía.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("uom", "0008_log_access_user_column_names"),
    ]

    operations = [
        migrations.AlterField(
            model_name="uom",
            name="factor",
            field=models.FloatField(
                default=1.0,
                editable=False,
                help_text=(
                    "Cantidad absoluta: producto de la cadena de factores "
                    "relativos (Odoo factor, compute recursivo almacenado)."
                ),
            ),
        ),
        migrations.AlterField(
            model_name="uom",
            name="relative_uom_id",
            field=models.ForeignKey(
                blank=True,
                db_column="relative_uom_id",
                help_text=(
                    "Unidad de referencia de la que cuelga "
                    "(Odoo relative_uom_id)."
                ),
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="uom.uom",
            ),
        ),
        migrations.AlterField(
            model_name="uom",
            name="sequence",
            field=models.IntegerField(
                default=0,
                help_text=(
                    "Orden de presentación (Odoo sequence). Se deriva del "
                    "factor."
                ),
            ),
        ),
    ]
