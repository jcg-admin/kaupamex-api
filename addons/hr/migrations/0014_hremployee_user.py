"""``hr.employee.user_id`` — columna y valor en las filas existentes.

≙ ``odoo19c: addons/hr/models/hr_employee.py:86-94`` (``related=
'resource_id.user_id'``, ``store=True``, ``index='btree_not_null'``). La
fuente calcula una columna almacenada nueva sobre las filas que ya existen
(``_auto_init``, ``odoo/orm/models.py:3220-3238``); aquí lo hace esta
migración, con el modelo histórico, copiando el usuario del recurso de cada
empleado. Diseño: ``designs/module-install-cycle.md``, L4a.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import OuterRef, Subquery


def copy_the_resource_user(apps, schema_editor):
    """El ``user_id`` de cada empleado es el de su recurso."""
    employee = apps.get_model('hr', 'HrEmployee')
    resource = apps.get_model('resource', 'ResourceResource')
    employee.objects.using(schema_editor.connection.alias).update(
        user_id=Subquery(resource.objects.filter(
            pk=OuterRef('resource_id')).values('user_id')[:1]))


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0104_translatable_columns_jsonb"),
        ("hr", "0013_translatable_columns_jsonb"),
        ("hr_skills", "0004_order_by_translated_name"),
        (
            "resource",
            "0002_resourcecalendarattendance_work_entry_type_and_more",
        ),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="hremployee",
            name="user_id",
            field=models.ForeignKey(
                blank=True,
                db_column="user_id",
                db_index=False,
                help_text=(
                    "Odoo user_id (related=resource_id.user_id, store=True)."
                ),
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="employee_ids",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Usuario",
            ),
        ),
        migrations.AddIndex(
            model_name="hremployee",
            index=models.Index(
                condition=models.Q(("user_id__isnull", False)),
                fields=["user_id"],
                name="hr_employee__user_id_index",
            ),
        ),
        migrations.RunPython(
            copy_the_resource_user, migrations.RunPython.noop,
        ),
    ]
