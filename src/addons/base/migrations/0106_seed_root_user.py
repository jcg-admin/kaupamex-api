"""Siembra ``base.partner_root`` y ``base.user_root`` (``SUPERUSER_ID``).

Las funciones viven en ``addons/base/data/res_users_data.py``; aquí sólo se
invocan sobre los modelos históricos.
"""
from django.db import migrations

from addons.base.data.res_users_data import seed_root_user


def seed(apps, schema_editor):
    seed_root_user(apps, schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0105_irrule_model_id_global'),
    ]

    operations = [
        # Sin marcha atrás, como los grupos y los países: borrar el
        # superusuario dejaría sin dueño lo que ya lo apunte.
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
