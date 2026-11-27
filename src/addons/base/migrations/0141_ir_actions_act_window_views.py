"""``view_id`` y ``search_view_id`` de la acción de ventana, y su ACL.

≙ ``odoo19c: odoo/addons/base/models/ir_actions.py:309-331`` y
``odoo/addons/base/security/ir.model.access.csv:101``. Diseño:
``designs/ir-actions-act-window-basemodel.md``.
"""

import django.db.models.deletion
from django.db import migrations, models

from addons.base.security.ir_model_access import seed_base_acl


def seed(apps, schema_editor):
    seed_base_acl(apps, schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0140_ir_actions_table_inheritance"),
    ]

    operations = [
        migrations.AddField(
            model_name="iractionsactwindow",
            name="search_view_id",
            field=models.ForeignKey(
                blank=True,
                db_column="search_view_id",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="base.iruiview",
                verbose_name="Vista de búsqueda",
            ),
        ),
        migrations.AddField(
            model_name="iractionsactwindow",
            name="view_id",
            field=models.ForeignKey(
                blank=True,
                db_column="view_id",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="base.iruiview",
                verbose_name="Vista de referencia",
            ),
        ),
        # Sin marcha atrás, mismo criterio que ``0139``.
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
