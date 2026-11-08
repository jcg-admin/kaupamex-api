"""Los hijos que se copian se declaran como ``One2many`` en el padre.

``ir.actions.server.child_ids`` y ``res.groups.model_access`` pasan a ser
``One2many`` declarados con ``copy=True`` (H-API-1161); sus ``Many2one``
llevan ``related_name='+'``. Sólo cambia el estado de Django: ninguna
columna se toca.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0098_transient_log_access_columns"),
    ]

    operations = [
        migrations.AlterField(
            model_name="iractionsserver",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "Odoo parent_id. Acción compuesta que encadena a ésta."),
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="base.iractionsserver",
                verbose_name="Acción padre",
            ),
        ),
        migrations.AlterField(
            model_name="irmodelaccess",
            name="group_id",
            field=models.ForeignKey(
                blank=True,
                db_column="group_id",
                help_text=(
                    "Vacío = acceso global. ondelete restrict de la fuente: "
                    "no se borra un grupo que aún concede permisos."),
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="base.resgroups",
                verbose_name="Grupo",
            ),
        ),
    ]
