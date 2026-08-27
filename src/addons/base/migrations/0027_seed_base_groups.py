"""Siembra los 12 grupos de ``base`` con sus identificadores externos.

≙ la carga de ``odoo19c: odoo/addons/base/security/base_groups.xml``, que la
referencia hace al instalar el módulo. El **spec y el sembrador** viven en
``addons/base/data/res_groups_data.py``; aquí sólo se invocan sobre los modelos
históricos, igual que ``0017_seed_countries`` y ``0026_seed_langs``.

El motivo de que el dato no viva en esta migración es el mismo que registró
:ref:`h-api-337`: un test transaccional hace ``flush`` y borra las filas que
sembró la migración, mientras ``django_migrations`` las sigue dando por
aplicadas. Con el spec en ``data/``, ``tests/conftest.py`` puede re-aplicarlo
—una sola definición, sin dos copias que puedan divergir— y la sesión siguiente
no arranca con ``has_group`` devolviendo ``False`` para todo.
"""
from django.db import migrations

from addons.base.data.res_groups_data import seed_base_groups


def seed(apps, schema_editor):
    return seed_base_groups(apps, schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0026_seed_langs'),
    ]

    operations = [
        # Sin marcha atrás, mismo criterio que países e idiomas: borrar los
        # grupos dejaría sin resolver toda pertenencia que ya los apunte, y
        # revertir esta migración busca volver al esquema, no vaciar la tabla.
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
