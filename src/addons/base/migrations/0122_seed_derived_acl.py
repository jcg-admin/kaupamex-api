"""Siembra las filas de la ACL de ``base`` que la derivación añade.

``_ACCESS`` se vuelve a derivar de
``odoo19c: odoo/addons/base/security/ir.model.access.csv`` al adoptar
``ir.mail_server`` a ``BaseModel``. Entran cinco filas: la de
``ir.mail_server`` y cuatro de modelos que ya tenían ``_name`` sin que nadie
hubiera vuelto a derivar la lista (``ir.exports``, ``ir.exports.line`` y las
dos de ``res.groups.privilege``).

``0059`` siembra lo que ``_ACCESS`` declara al aplicarse, así que una base
creada después ya las trae. Esta migración las lleva a las que ya pasaron por
``0059``: ``seed_base_acl`` es idempotente.
"""

from django.db import migrations

from addons.base.security.ir_model_access import seed_base_acl


def seed(apps, schema_editor):
    seed_base_acl(apps, schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0121_rescompany_mail_fields'),
    ]

    operations = [
        # Sin marcha atrás, mismo criterio que ``0059`` y ``0095``.
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
