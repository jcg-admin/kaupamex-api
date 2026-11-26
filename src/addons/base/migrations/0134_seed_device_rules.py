"""Siembra las cuatro reglas de ``res.device`` y ``res.device.log``.

≙ ``odoo19c: odoo/addons/base/security/base_security.xml:229-252``: cada
usuario lee sus dispositivos y sus logs; el administrador, todos. Primer paso
de ``designs/basemodel-adoption-res-device.md``. La siembra es idempotente.
"""

from django.db import migrations

from addons.base.security.base_security import seed_base_rules


def seed(apps, schema_editor):
    seed_base_rules(apps, schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0133_seed_properties_and_device_security'),
    ]

    operations = [
        # Sin marcha atrás, mismo criterio que ``0059`` y ``0122``.
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
