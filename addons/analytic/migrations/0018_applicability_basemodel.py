import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import addons.analytic.models.analytic_plan


def _user_column(column):
    return models.ForeignKey(
        blank=True,
        db_column=column,
        db_index=False,
        editable=False,
        null=True,
        on_delete=django.db.models.deletion.SET_NULL,
        related_name="+",
        to=settings.AUTH_USER_MODEL,
    )


class Migration(migrations.Migration):
    """``account.analytic.applicability`` pasa a ``BaseModel``: sus FK toman
    el nombre de la fuente y nacen las columnas del log-access.

    ≙ ``analytic_plan_id`` y ``company_id``
    (``odoo19c: addons/analytic/models/analytic_plan.py:411-431``) y
    ``product_categ_id`` de ``account``
    (``odoo19c: addons/account/models/account_analytic_plan.py:24-27``). Las
    columnas ya se llamaban ``*_id``: el ``db_column`` las fija y el renombre
    no toca datos. Diseño: ``designs/analytic-applicability-basemodel.md``.
    """

    dependencies = [
        ("analytic", "0017_seed_project_plan"),
        ("base", "0126_fill_cron_action_code"),
        ("product", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="accountanalyticapplicability",
            name="analytic_plan",
            field=models.ForeignKey(
                blank=True,
                db_column="analytic_plan_id",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="applicability_ids",
                to="analytic.accountanalyticplan",
                verbose_name="Plan analítico",
            ),
        ),
        migrations.RenameField(
            model_name="accountanalyticapplicability",
            old_name="analytic_plan",
            new_name="analytic_plan_id",
        ),
        migrations.AlterField(
            model_name="accountanalyticapplicability",
            name="company",
            field=models.ForeignKey(
                blank=True,
                db_column="company_id",
                default=addons.analytic.models.analytic_plan
                ._default_company_id,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="analytic_applicabilities",
                to="base.rescompany",
                verbose_name="Empresa",
            ),
        ),
        migrations.RenameField(
            model_name="accountanalyticapplicability",
            old_name="company",
            new_name="company_id",
        ),
        migrations.AlterField(
            model_name="accountanalyticapplicability",
            name="product_categ",
            field=models.ForeignKey(
                blank=True,
                db_column="product_categ_id",
                help_text=(
                    "Odoo product_categ_id. Categoría de producto sobre "
                    "la que aplica esta regla."
                ),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="analytic_applicabilities",
                to="product.productcategory",
            ),
        ),
        migrations.RenameField(
            model_name="accountanalyticapplicability",
            old_name="product_categ",
            new_name="product_categ_id",
        ),
        migrations.AddField(
            model_name="accountanalyticapplicability",
            name="create_date",
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="accountanalyticapplicability",
            name="write_date",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name="accountanalyticapplicability",
            name="create_uid",
            field=_user_column("create_uid"),
        ),
        migrations.AddField(
            model_name="accountanalyticapplicability",
            name="write_uid",
            field=_user_column("write_uid"),
        ),
    ]
