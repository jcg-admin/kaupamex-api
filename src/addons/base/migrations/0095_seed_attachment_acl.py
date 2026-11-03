"""Siembra la ACL de ``ir.attachment`` en las bases ya migradas.

≙ las dos filas de ``odoo19c: odoo/addons/base/security/ir.model.access.csv``
que dan permiso sobre ``model_ir_attachment``: ``group_user`` con los cuatro
permisos y la fila global en cero. Hasta este pase ``ir.attachment`` era una
fila de Django y nadie comprobaba su ACL; al derivar de
:class:`~orm.models.BaseModel` (:ref:`h-api-1083`) su recordset la comprueba
como cualquier otro, y sin filas deniega todo.

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
        ('base', '0094_seed_default_parameters'),
    ]

    operations = [
        # Sin marcha atrás, mismo criterio que ``0059``: retirar la ACL
        # dejaría los adjuntos denegando todo sin que nada lo dijera.
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
