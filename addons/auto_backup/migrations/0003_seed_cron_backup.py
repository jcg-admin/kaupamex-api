"""Siembra el planificador del respaldo (:ref:`h-api-763`).

``app_auto_backup/data/backup_data.xml:4-13`` declara un ``ir.cron`` cada 12
horas que llama a ``model.schedule_backup()`` sobre ``db.backup``. El addon
portado tenía el método —bajo otro nombre y sin configuración— y **ningún
disparador**: capacidad muerta, la misma forma que :ref:`h-api-747` registró
para el barrido de ``@api.autovacuum``.

La periodicidad de la fuente se conserva verbatim (12 h, prioridad 5). Un
segundo pase no la pisa: ``sembrar_cron`` es idempotente sobre la clave
natural ``(model_name, method_name)``, que es el equivalente nativo del
``noupdate="1"`` de la referencia — si el operador ajusta el intervalo, se
respeta.
"""
from django.db import migrations

from addons.auto_backup.data import CRON_BACKUP
from addons.base.data import sembrar_cron


def sembrar(apps, schema_editor):
    sembrar_cron(apps, schema_editor.connection.alias, CRON_BACKUP)


def retirar(apps, schema_editor):
    """Retira el par acción + cron. El cron primero: su FK apunta a la acción."""
    alias = schema_editor.connection.alias
    IrActionsServer = apps.get_model('base', 'IrActionsServer')
    IrCron = apps.get_model('base', 'IrCron')

    accion = IrActionsServer.objects.using(alias).filter(
        model_name=CRON_BACKUP['model_name'],
        method_name=CRON_BACKUP['method_name'],
    ).first()
    if accion is None:
        return
    IrCron.objects.using(alias).filter(ir_actions_server=accion).delete()
    accion.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('auto_backup', '0002_dbbackup_dbbackupdetails_delete_backuprecord'),
        # La siembra escribe en ``base``: el par acción + cron vive allí.
        ('base', '0032_seed_cron_autovacuum'),
    ]

    operations = [
        migrations.RunPython(sembrar, retirar),
    ]
