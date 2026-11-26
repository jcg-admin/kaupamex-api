"""Siembra la ACL y las reglas de ``ir.filters``.

≙ ``odoo19c: odoo/addons/base/security/ir.model.access.csv:114-117`` (cuatro
filas ``ir_filters all``) y ``base_security.xml:74-104`` (tres reglas). Con
``_name`` declarado por ``0131``, ``_ACCESS`` y ``_RULES`` las llevan; esta
migración las siembra en las bases que ya pasaron por ``0059``. Las dos
siembras son idempotentes.
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
        ('base', '0131_ir_filters_port_19'),
    ]

    operations = [
        # Sin marcha atrás, mismo criterio que ``0059`` y ``0122``.
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
