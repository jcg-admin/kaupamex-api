"""Siembra los formatos de papel de ``base`` (``report_paperformat_data``).

La función vive en ``addons/base/data/report_paperformat_data.py``; aquí sólo
se invoca sobre los modelos históricos.
"""
from django.db import migrations

from addons.base.data.report_paperformat_data import seed_paperformats


def seed(apps, schema_editor):
    seed_paperformats(apps, schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0106_seed_root_user'),
    ]

    operations = [
        # Sin marcha atrás, como el resto de datos de base: borrarlos dejaría
        # sin formato a las compañías que ya los apunten.
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
