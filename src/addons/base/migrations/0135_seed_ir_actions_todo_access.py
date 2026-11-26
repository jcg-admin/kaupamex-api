"""Siembra la ACL de ``ir.actions.todo``.

≙ ``odoo19c: odoo/addons/base/security/ir.model.access.csv:104``: el modelo
pasa a ``models.BaseModel`` y sólo ``group_system`` lo gestiona
(``designs/basemodel-adoption-ir-actions-todo.md``). La siembra es
idempotente.
"""

from django.db import migrations

from addons.base.security.ir_model_access import seed_base_acl


def seed(apps, schema_editor):
    seed_base_acl(apps, schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0134_seed_device_rules'),
    ]

    operations = [
        # Sin marcha atrás, mismo criterio que ``0059`` y ``0122``.
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
