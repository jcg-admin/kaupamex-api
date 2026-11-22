"""Vincula el cron ya sembrado a su ``xml_id``,
``mail.ir_cron_mail_scheduler_action``.

Es el ``id`` del ``<record model="ir.cron">`` de la fuente (``odoo19c:
addons/mail/data/ir_cron_data.xml:4-13``). Volver a sembrar el spec
encuentra la acción por su método, porque aún no hay fila de
``ir.model.data``, y registra el ``xml_id``
(``designs/cron-xml-id-natural-key.md``).
"""
from django.db import migrations

from addons.base.data import sembrar_cron
from addons.mail.data import CRON_EMAIL_QUEUE


def seed(apps, schema_editor):
    sembrar_cron(apps, schema_editor.connection.alias, CRON_EMAIL_QUEUE)


class Migration(migrations.Migration):

    dependencies = [
        ('mail', '0013_res_id_help_text'),
        ('base', '0127_cron_xml_ids'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
