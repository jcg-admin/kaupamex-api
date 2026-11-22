"""Siembra el cron de las automatizaciones por tiempo, inactivo.

La fuente lo declara como
``base_automation.ir_cron_data_base_automation_check``, con ``active=False``
(``odoo19c: addons/base_automation/data/base_automation_data.xml:4-12``).
Aquí sólo existía en las bases que siembra el fixture de
``tests/conftest.py``; esta migración lo crea en toda base, con su
``xml_id`` (``designs/cron-xml-id-natural-key.md``).
"""
from django.db import migrations

from addons.base.data import sembrar_cron
from addons.base_automation.data import CRON_BASE_AUTOMATION_CHECK


def seed(apps, schema_editor):
    sembrar_cron(apps, schema_editor.connection.alias,
                 CRON_BASE_AUTOMATION_CHECK)


class Migration(migrations.Migration):

    dependencies = [
        ('base_automation', '0007_log_access_user_column_names'),
        ('base', '0127_cron_xml_ids'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
