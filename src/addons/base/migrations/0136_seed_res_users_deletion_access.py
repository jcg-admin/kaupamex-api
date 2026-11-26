"""Siembra la ACL de ``res.users.deletion``.

≙ ``odoo19c: odoo/addons/base/security/ir.model.access.csv:87-88``: nula
para todos y completa para ``group_erp_manager``, ahora que el modelo es
``models.BaseModel`` (``designs/basemodel-adoption-res-users-deletion.md``).
La siembra es idempotente.
"""

from django.db import migrations

from addons.base.security.ir_model_access import seed_base_acl


def seed(apps, schema_editor):
    seed_base_acl(apps, schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0135_seed_ir_actions_todo_access'),
    ]

    operations = [
        # Sin marcha atrás, mismo criterio que ``0059`` y ``0122``.
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
