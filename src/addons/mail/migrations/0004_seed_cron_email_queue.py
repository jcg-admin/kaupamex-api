"""Siembra el cron de la cola de correo — equivalente de ``ir_cron_data.xml``.

La referencia declara ``ir_cron_mail_scheduler_action`` en el ``data/`` del
addon ``mail`` (``odoo19c: mail/data/ir_cron_data.xml:4-13``,
``odoo-tools@622ddc2a``). Aquí ese XML es esta data-migration.

Depende de ``base`` porque las dos filas que crea —``ir.actions.server`` e
``ir.cron``— viven ahí: en la referencia el "qué ejecutar" también es de
``ir.actions.server`` y ``ir.cron`` sólo lo delega.

Idempotente: un segundo pase no duplica ni pisa el intervalo que el operador
haya ajustado, que es lo que ``noupdate="1"`` garantiza en el XML original.
"""
from django.db import migrations

from addons.base.data import sembrar_cron
from addons.mail.data import CRON_EMAIL_QUEUE


def sembrar(apps, schema_editor):
    sembrar_cron(apps, schema_editor.connection.alias, CRON_EMAIL_QUEUE)


class Migration(migrations.Migration):

    dependencies = [
        ('mail', '0003_remove_mailalias_mail_alias_name_domain_unique_and_more'),
        ('base', '0008_alter_iractionsactions_path_and_more'),
    ]

    operations = [
        migrations.RunPython(sembrar, migrations.RunPython.noop),
    ]
