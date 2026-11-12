"""Siembra ``base.public_partner`` y ``base.public_user``.

Las funciones viven en ``addons/base/data/res_users_data.py``; aquí sólo se
invocan sobre los modelos históricos. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
public-user-seed.md``.
"""
from django.db import migrations

from addons.base.data.res_users_data import seed_public_user


def seed(apps, schema_editor):
    seed_public_user(apps, schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0112_log_access_user_column_names'),
    ]

    operations = [
        # Sin marcha atrás, como el superusuario: borrarlo dejaría sin
        # dueño lo que el respaldo del volcado escribió como él.
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
