import django.db.models.deletion
from django.db import migrations, models

import addons.analytic.models.analytic_account


class Migration(migrations.Migration):
    """``company`` de la cuenta pasa a ``company_id`` en forma C (ADR-029).

    ≙ ``company_id`` con ``default=lambda self: self.env.company``
    (``odoo19c: addons/analytic/models/analytic_account.py:61``). La columna
    ya se llamaba ``company_id``: el ``db_column`` la fija y el renombre no
    toca datos.
    """

    dependencies = [
        ("analytic", "0014_account_plan_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="accountanalyticaccount",
            name="company",
            field=models.ForeignKey(
                blank=True,
                db_column="company_id",
                default=(
                    addons.analytic.models.analytic_account
                    ._default_company_id),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="analytic_accounts",
                to="base.rescompany",
                verbose_name="Empresa",
            ),
        ),
        migrations.RenameField(
            model_name="accountanalyticaccount",
            old_name="company",
            new_name="company_id",
        ),
    ]
