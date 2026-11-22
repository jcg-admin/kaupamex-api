"""Vincula el cron ya sembrado a su ``xml_id``,
``website_sale.ir_cron_send_availability_email``.

Es el ``id`` del ``<record model="ir.cron">`` de la fuente (``odoo19c:
addons/website_sale/data/ir_cron_data.xml:3-10``). Volver a sembrar el spec
encuentra la acción por su método, porque aún no hay fila de
``ir.model.data``, y registra el ``xml_id``
(``designs/cron-xml-id-natural-key.md``).
"""
from django.db import migrations

from addons.base.data import sembrar_cron
from addons.website_sale.models.website import CRON_SEND_ABANDONED_CART_EMAIL


def seed(apps, schema_editor):
    sembrar_cron(apps, schema_editor.connection.alias,
                 CRON_SEND_ABANDONED_CART_EMAIL)


class Migration(migrations.Migration):

    dependencies = [
        ('website_sale', '0007_log_access_user_column_names'),
        ('base', '0127_cron_xml_ids'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
