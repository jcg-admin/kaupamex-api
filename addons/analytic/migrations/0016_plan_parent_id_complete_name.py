import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

from orm.migration_operations import ComputeStoredFields


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
    """``parent`` del plan pasa a ``parent_id`` en forma C y nace
    ``complete_name`` almacenado.

    ≙ ``parent_id``/``children_ids`` (``odoo19c: addons/analytic/models/
    analytic_plan.py:29-47``) y ``complete_name`` (``:52-57``). La columna ya
    se llamaba ``parent_id``: el ``db_column`` la fija y el renombre no toca
    datos. ``complete_name`` se calcula sobre las filas existentes con
    ``ComputeStoredFields``. Como ``BaseModel``, el plan recibe además las
    cuatro columnas del log-access (``odoo19c: odoo/orm/models.py:287-292``);
    las filas existentes reciben la fecha de la migración.
    """

    dependencies = [
        ("analytic", "0015_account_company_id"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="accountanalyticplan",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                db_column="parent_id",
                help_text="Odoo parent_id (ondelete=cascade).",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="children_ids",
                to="analytic.accountanalyticplan",
                verbose_name="Plan padre",
            ),
        ),
        migrations.RenameField(
            model_name="accountanalyticplan",
            old_name="parent",
            new_name="parent_id",
        ),
        migrations.AddField(
            model_name="accountanalyticplan",
            name="complete_name",
            field=models.CharField(
                blank=True, editable=False, max_length=1024, null=True,
                verbose_name="Complete Name",
            ),
        ),
        migrations.AddField(
            model_name="accountanalyticplan",
            name="create_date",
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="accountanalyticplan",
            name="write_date",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name="accountanalyticplan",
            name="create_uid",
            field=_user_column("create_uid"),
        ),
        migrations.AddField(
            model_name="accountanalyticplan",
            name="write_uid",
            field=_user_column("write_uid"),
        ),
        # ≙ ``odoo19c: odoo/orm/models.py:3220-3238``: la columna nueva se
        # calcula sobre las filas existentes con el mecanismo del ORM.
        ComputeStoredFields(
            "analytic", "accountanalyticplan", ["complete_name"]),
    ]
