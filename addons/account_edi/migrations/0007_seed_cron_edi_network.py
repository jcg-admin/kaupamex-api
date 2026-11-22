"""Siembra ``account_edi.ir_cron_edi_network``.

≙ ``odoo19c: addons/account_edi/data/cron.xml:2-10``: el cron de las
operaciones con web-service, diario e inactivo, con su identificador externo.
Lo activa crear un formato que necesita web-service
(``account_edi_format.py:40-42``) y lo disparan el asiento y el documento
(``account_move.py:264``, ``:283``; ``account_edi_document.py:251``).
Diseño: ``designs/account-edi-network-cron.md``.
"""

from django.db import migrations

from addons.account_edi.data import CRON_EDI_NETWORK
from addons.base.data import sembrar_cron


def sembrar(apps, schema_editor):
    sembrar_cron(apps, schema_editor.connection.alias, CRON_EDI_NETWORK)


def retirar(apps, schema_editor):
    """Retira el identificador, el cron y su acción, en ese orden."""
    alias = schema_editor.connection.alias
    IrActionsServer = apps.get_model('base', 'IrActionsServer')
    IrCron = apps.get_model('base', 'IrCron')
    IrModelData = apps.get_model('base', 'IrModelData')
    module, _, name = CRON_EDI_NETWORK['xml_id'].partition('.')
    IrModelData.objects.using(alias).filter(module=module, name=name).delete()
    accion = IrActionsServer.objects.using(alias).filter(
        model_name=CRON_EDI_NETWORK['model_name'],
        method_name=CRON_EDI_NETWORK['method_name'],
    ).first()
    if accion is None:
        return
    IrCron.objects.using(alias).filter(ir_actions_server=accion).delete()
    accion.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('account_edi', '0006_journal_edi_format_ids_state'),
        # La siembra escribe en ``base``: acción, cron e identificador.
        ('base', '0125_irattachment_res_id_help_text'),
    ]

    operations = [
        migrations.RunPython(sembrar, retirar),
    ]
