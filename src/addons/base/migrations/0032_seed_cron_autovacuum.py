"""Siembra el cron del barrido automático (H-API-747).

El decorador ``@api.autovacuum`` y su colector estaban portados desde
``api@61b7651``, pero **nadie llamaba al colector**: los tres métodos marcados
—``IrProfile._gc_profile``, ``BusMessage._gc_messages`` e
``IrLogging._purge_expired``— eran capacidad muerta. La referencia cierra ese
hueco con un solo job (``odoo19c: odoo/addons/base/data/ir_cron_data.xml:3``),
y ésta es su forma nativa.

Un único cron para todo el barrido es la razón de ser del decorador: un método
de recolección que no amerita su propio job se marca y el colector lo recoge.
Por eso ``observability`` retira el suyo en su ``0004`` — la purga de logs pasó
a ser uno de los métodos recogidos, no un job aparte.
"""
from django.db import migrations

from addons.base.data import CRON_AUTOVACUUM, sembrar_cron


def sembrar(apps, schema_editor):
    sembrar_cron(apps, schema_editor.connection.alias, CRON_AUTOVACUUM)


def retirar(apps, schema_editor):
    """Retira el par acción + cron. El cron primero: su FK apunta a la acción."""
    alias = schema_editor.connection.alias
    IrActionsServer = apps.get_model('base', 'IrActionsServer')
    IrCron = apps.get_model('base', 'IrCron')

    accion = IrActionsServer.objects.using(alias).filter(
        model_name=CRON_AUTOVACUUM['model_name'],
        method_name=CRON_AUTOVACUUM['method_name'],
    ).first()
    if accion is None:
        return
    IrCron.objects.using(alias).filter(ir_actions_server=accion).delete()
    accion.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0031_ir_autovacuum'),
    ]

    operations = [
        migrations.RunPython(sembrar, retirar),
    ]
