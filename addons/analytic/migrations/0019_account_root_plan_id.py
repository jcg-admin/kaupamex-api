import django.db.models.deletion
from django.db import migrations, models

from orm.migration_operations import ComputeStoredFields


class Migration(migrations.Migration):
    """``root_plan_id`` de la cuenta analítica, relacionado y almacenado.

    ≙ ``odoo19c: addons/analytic/models/analytic_account.py:44-49``
    (``related="plan_id.root_id", store=True``). La columna nueva se calcula
    sobre las filas existentes con el mecanismo del ORM. Diseño:
    ``designs/analytic-account-related-fields.md``.
    """

    dependencies = [
        ("analytic", "0018_applicability_basemodel"),
    ]

    operations = [
        migrations.AddField(
            model_name="accountanalyticaccount",
            name="root_plan_id",
            field=models.ForeignKey(
                blank=True,
                db_column="root_plan_id",
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="analytic.accountanalyticplan",
                verbose_name="Root Plan",
            ),
        ),
        ComputeStoredFields(
            "analytic", "accountanalyticaccount", ["root_plan_id"]),
    ]
