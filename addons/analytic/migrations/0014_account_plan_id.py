import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """``plan`` de la cuenta pasa a ``plan_id`` en forma C (ADR-029).

    ≙ ``plan_id`` (``odoo19c: addons/analytic/models/analytic_account.py:38``)
    y su inverso ``account_ids`` (``analytic_plan.py:58``). La columna ya se
    llamaba ``plan_id``: el ``db_column`` la fija y el renombre no toca datos.
    """

    dependencies = [
        ("analytic", "0013_model_headers"),
    ]

    operations = [
        migrations.AlterField(
            model_name="accountanalyticaccount",
            name="plan",
            field=models.ForeignKey(
                db_column="plan_id",
                help_text=(
                    "Odoo plan_id (requerido). on_delete=PROTECT: un plan con "
                    "cuentas no se puede borrar por accidente (Odoo no fija "
                    "ondelete explícito aquí; PROTECT es la adaptación "
                    "segura)."
                ),
                on_delete=django.db.models.deletion.PROTECT,
                related_name="account_ids",
                to="analytic.accountanalyticplan",
                verbose_name="Plan",
            ),
        ),
        migrations.RenameField(
            model_name="accountanalyticaccount",
            old_name="plan",
            new_name="plan_id",
        ),
        migrations.AlterModelOptions(
            name="accountanalyticaccount",
            options={
                "ordering": ["plan_id", "name"],
                "verbose_name": "Cuenta analítica",
                "verbose_name_plural": "Cuentas analíticas",
            },
        ),
    ]
