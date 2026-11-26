"""``report.layout.view`` obligatorio y la ACL del modelo.

≙ ``odoo19c: odoo/addons/base/models/report_layout.py:12`` (``view_id``
``required=True``) y ``odoo/addons/base/security/ir.model.access.csv:123``.
La columna era nullable mientras ``ir.ui.view`` no estaba portado; ya lo
está. Una fila sin vista hace fallar el ``ALTER`` a propósito: no se le
inventa una vista ni se borra. Diseño:
``designs/basemodel-adoption-report-layout.md``.
"""

import django.db.models.deletion
from django.db import migrations, models

from addons.base.security.ir_model_access import seed_base_acl


def seed(apps, schema_editor):
    seed_base_acl(apps, schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0138_res_users_log_owner_in_create_uid'),
    ]

    operations = [
        migrations.AlterField(
            model_name='reportlayout',
            name='view',
            field=models.ForeignKey(
                help_text='Odoo view_id (required).',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='report_layouts',
                to='base.iruiview',
                verbose_name='Plantilla del documento',
            ),
        ),
        # Sin marcha atrás, mismo criterio que ``0059`` y ``0122``.
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
