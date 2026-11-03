"""Re-deriva la ACL de ``base`` desde el CSV de la referencia.

``_ACCESS`` sembraba un subconjunto escrito a mano cuyo docstring decía
cubrir todas las filas de modelo existente (:ref:`h-api-1143`). La lista se
deriva ahora de ``odoo19c: odoo/addons/base/security/ir.model.access.csv``.
Esta migración la lleva a las bases que ya pasaron por ``0059``:

1. **Renombra** las ocho filas que se sembraron con un nombre inventado al
   nombre del CSV. El par se fijó por modelo, grupo y permisos, que coinciden
   en las ocho; ninguna cambia lo que concede.
2. **Siembra** las que faltan, con ``seed_base_acl``, idempotente por la terna
   ``(name, modelo, grupo)``: el CSV repite nombres con grupos distintos.
"""

from django.db import migrations

from addons.base.security.ir_model_access import seed_base_acl

#: ``(nombre sembrado, nombre del CSV)``.
RENAMES = (
    ('ir_module_category', 'ir_module_category group_user'),
    ('ir_module_module', 'ir_module_module group_user'),
    ('ir_module_module_dependency',
     'ir_module_module_dependency group_system'),
    ('res_users group_portal', 'res_users all'),
    ('res_users group_public', 'res_users all'),
    ('res_users group_user', 'res_users all'),
    ('res_users_apikeys group_portal', 'API keys access portal'),
    ('res_users_apikeys group_user', 'API keys access employees'),
)


def rederive(apps, schema_editor):
    alias = schema_editor.connection.alias
    access = apps.get_model('base', 'IrModelAccess')
    for old_name, new_name in RENAMES:
        access.objects.using(alias).filter(name=old_name).update(
            name=new_name)
    seed_base_acl(apps, alias)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0095_seed_attachment_acl'),
    ]

    operations = [
        # Sin marcha atrás, mismo criterio que ``0059``: deshacer devolvería
        # nombres que no son los de la fuente y retiraría permisos que la
        # fuente concede.
        migrations.RunPython(rederive, migrations.RunPython.noop),
    ]
