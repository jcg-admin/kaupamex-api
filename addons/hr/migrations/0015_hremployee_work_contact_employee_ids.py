"""``res.partner.employee_ids`` — el reverso de ``work_contact`` con el
nombre de la fuente.

≙ ``odoo19c: addons/hr/models/res_partner.py:11-13`` (``One2many(
'hr.employee', 'work_contact_id')``). Sólo cambia el estado: el nombre del
reverso no tiene columna. Diseño: ``designs/module-install-cycle.md``, L4b.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0104_translatable_columns_jsonb"),
        ("hr", "0014_hremployee_user"),
    ]

    operations = [
        migrations.AlterField(
            model_name="hremployee",
            name="work_contact",
            field=models.ForeignKey(
                blank=True,
                help_text="Odoo work_contact_id.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="employee_ids",
                to="base.respartner",
                verbose_name="Contacto de trabajo",
            ),
        ),
    ]
