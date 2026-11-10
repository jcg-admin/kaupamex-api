"""``hr.employee.parent_id`` en forma C, con ``child_ids`` como reverso.

≙ ``odoo19c: addons/hr/models/hr_employee.py:193-195``. El campo pasa de
``parent`` a ``parent_id`` y su reverso de ``children`` a ``child_ids``; la
columna sigue siendo ``parent_id``, así que sólo cambia el estado. Diseño:
``designs/module-install-cycle.md``, L4e (e2).
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hr", "0015_hremployee_work_contact_employee_ids"),
    ]

    operations = [
        # Primero se fija la columna sobre el nombre viejo y después se
        # renombra el campo: así ninguna de las dos operaciones toca la tabla.
        migrations.AlterField(
            model_name="hremployee",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                db_column="parent_id",
                help_text="Odoo parent_id.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="child_ids",
                to="hr.hremployee",
                verbose_name="Gerente",
            ),
        ),
        migrations.RenameField(
            model_name="hremployee",
            old_name="parent",
            new_name="parent_id",
        ),
    ]
