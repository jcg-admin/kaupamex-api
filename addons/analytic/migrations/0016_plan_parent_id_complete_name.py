import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


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


def fill_complete_name(apps, schema_editor):
    """Rellena ``complete_name`` en las filas que ya existían.

    ≙ ``_compute_complete_name`` (``odoo19c: addons/analytic/models/
    analytic_plan.py:139-145``), recorriendo de la raíz a las hojas por la
    longitud de ``parent_path``: cada padre ya tiene su nombre completo
    cuando llega su hijo.
    """
    plan_model = apps.get_model("analytic", "AccountAnalyticPlan")
    names = {}
    rows = plan_model.objects.values_list(
        "pk", "name", "parent_id", "parent_path")
    by_depth = sorted(rows, key=lambda row: len(row[3] or ""))
    for pk, name, parent_id, _path in by_depth:
        complete = (
            f"{names[parent_id]} / {name}" if parent_id in names else name
        )
        names[pk] = complete
        plan_model.objects.filter(pk=pk).update(complete_name=complete)


class Migration(migrations.Migration):
    """``parent`` del plan pasa a ``parent_id`` en forma C y nace
    ``complete_name`` almacenado.

    ≙ ``parent_id``/``children_ids`` (``odoo19c: addons/analytic/models/
    analytic_plan.py:29-47``) y ``complete_name`` (``:52-57``). La columna ya
    se llamaba ``parent_id``: el ``db_column`` la fija y el renombre no toca
    datos. Como ``BaseModel``, el plan recibe además las cuatro columnas del
    log-access (``odoo19c: odoo/orm/models.py:287-292``); las filas
    existentes reciben la fecha de la migración.
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
        migrations.RunPython(fill_complete_name, migrations.RunPython.noop),
    ]
