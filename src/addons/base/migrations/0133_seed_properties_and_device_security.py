"""Siembra la ACL de ``res.device``, ``res.device.log`` y
``properties.base.definition``, y la regla de esta última.

≙ ``odoo19c: odoo/addons/base/security/ir.model.access.csv:145-147`` y
``base_security.xml:256-261``. Las tres filas faltaban porque el CSV califica
su identificador con el módulo y el derivador de ``_ACCESS`` no lo quitaba
(``designs/basemodel-adoption-properties-base-definition.md``). Las siembras
son idempotentes.
"""

from django.db import migrations

from addons.base.security.base_security import seed_base_rules
from addons.base.security.ir_model_access import seed_base_acl


def seed(apps, schema_editor):
    alias = schema_editor.connection.alias
    seed_base_acl(apps, alias)
    seed_base_rules(apps, alias)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0132_seed_ir_filters_security'),
    ]

    operations = [
        # Sin marcha atrás, mismo criterio que ``0059`` y ``0122``.
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
