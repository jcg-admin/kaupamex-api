"""Vincula el cron de vouchers a su ``xml_id``,
``loyalty.ir_cron_expire_vouchers``.

``loyalty`` de la fuente no siembra ningún cron, así que el identificador es
propio del proyecto, con el prefijo ``ir_cron_`` de la convención de la
fuente. Volver a sembrar el spec encuentra la acción por su método y
registra el ``xml_id`` (``designs/cron-xml-id-natural-key.md``).
"""
from django.db import migrations

from addons.base.data import sembrar_cron
from addons.loyalty.data import CRON_EXPIRE_VOUCHERS


def seed(apps, schema_editor):
    sembrar_cron(apps, schema_editor.connection.alias, CRON_EXPIRE_VOUCHERS)


class Migration(migrations.Migration):

    dependencies = [
        ('loyalty', '0005_log_access_user_column_names'),
        ('base', '0127_cron_xml_ids'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
