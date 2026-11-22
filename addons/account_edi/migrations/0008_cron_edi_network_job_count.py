"""Escribe en la acción del cron EDI el ``code`` de la fuente.

``odoo19c: addons/account_edi/data/cron.xml:6`` ejecuta
``model._cron_process_documents_web_services(job_count=20)``; la siembra de
``0007`` lo dejó vacío porque el cron aún no ejecutaba ``code``
(``designs/cron-runs-server-action.md``).
"""
from django.db import migrations

from addons.account_edi.data import CRON_EDI_NETWORK


def write_code(apps, schema_editor):
    alias = schema_editor.connection.alias
    IrActionsServer = apps.get_model('base', 'IrActionsServer')
    IrActionsServer.objects.using(alias).filter(
        model_name=CRON_EDI_NETWORK['model_name'],
        method_name=CRON_EDI_NETWORK['method_name'],
    ).update(code=CRON_EDI_NETWORK['code'])


class Migration(migrations.Migration):

    dependencies = [
        ('account_edi', '0007_seed_cron_edi_network'),
        ('base', '0126_fill_cron_action_code'),
    ]

    operations = [
        migrations.RunPython(write_code, migrations.RunPython.noop),
    ]
