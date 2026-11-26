"""Siembra la regla de ``ir.ui.view.custom``: cada usuario, sus vistas.

``ir_ui_view_custom_personal`` (``odoo19c: odoo/addons/base/security/
base_security.xml:50-54``) acompaña la adopción de ``BaseModel`` de
``ir.ui.view.custom``. ``0059`` siembra lo que ``_RULES`` declara al
aplicarse, así que una base creada después ya la trae; esta migración la lleva
a las que ya pasaron por ``0059``: ``seed_base_rules`` es idempotente por
nombre.
"""

from django.db import migrations

from addons.base.security.base_security import seed_base_rules


def seed(apps, schema_editor):
    seed_base_rules(apps, schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0129_res_users_share'),
    ]

    operations = [
        # Sin marcha atrás, mismo criterio que ``0059`` y ``0122``.
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
