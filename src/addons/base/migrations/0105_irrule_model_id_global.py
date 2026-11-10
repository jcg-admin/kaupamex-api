"""``ir.rule.model_id`` y ``ir.rule.global`` — columnas y valores.

≙ ``odoo19c: odoo/addons/base/models/ir_rule.py:24`` (``model_id``) y
``:270-279`` (``global``, almacenado y calculado de los grupos). Las filas
que ya existen toman ``model_id`` de la fila de ``ir.model`` que nombra su
``model_name`` (o quedan sin él si el modelo no tiene fila), y ``global`` lo
calcula ``ComputeStoredFields`` con su ``_compute_global``, como
``_auto_init`` calcula una columna almacenada nueva (TASK-API-0516).
Diseño: ``designs/module-install-cycle.md``, L4d.
"""

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import OuterRef, Subquery

from orm.migration_operations import ComputeStoredFields


def fill_the_model_id(apps, schema_editor):
    """``model_id`` desde la etiqueta."""
    alias = schema_editor.connection.alias
    rule = apps.get_model('base', 'IrRule')
    model = apps.get_model('base', 'IrModel')
    rule.objects.using(alias).update(model_id=Subquery(
        model.objects.filter(model=OuterRef('model_name')).values('pk')[:1]))


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0104_translatable_columns_jsonb"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="irrule",
            options={
                "ordering": ["-model_id", "id"],
                "verbose_name": "Regla de registro",
                "verbose_name_plural": "Reglas de registro",
            },
        ),
        migrations.AddField(
            model_name="irrule",
            name="global",
            field=models.BooleanField(
                default=True,
                editable=False,
                help_text=(
                    "If no group is specified the rule is global and applied "
                    "to everyone (Odoo global)."
                ),
                verbose_name="Global",
            ),
        ),
        migrations.AddField(
            model_name="irrule",
            name="model_id",
            field=models.ForeignKey(
                blank=True,
                db_column="model_id",
                help_text="Odoo model_id.",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="rule_ids",
                to="base.irmodel",
                verbose_name="Modelo (ir.model)",
            ),
        ),
        migrations.RunPython(
            fill_the_model_id, migrations.RunPython.noop,
        ),
        ComputeStoredFields('base', 'irrule', ['global']),
    ]
