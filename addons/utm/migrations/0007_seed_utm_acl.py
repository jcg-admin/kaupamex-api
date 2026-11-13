"""Siembra la ACL de ``utm`` (``odoo19c: addons/utm/security/
ir.model.access.csv``).

Los cinco modelos de ``utm`` derivan de ``BaseModel`` y su acceso pasa por
``check_access``; sin estas filas un usuario interno quedaba sin permiso.
Idempotente por la terna ``(nombre, modelo, grupo)``.
"""
from django.db import migrations

from addons.utm.security.ir_model_access import seed_utm_acl


def forwards(apps, schema_editor):
    seed_utm_acl(apps, schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = [
        ('utm', '0006_log_access_user_column_names'),
        ('base', '0059_seed_base_security'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
