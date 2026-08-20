"""Specs de siembra del addon ``auto_backup``."""

# El planificador del respaldo, verbatim de
# ``app_auto_backup/data/backup_data.xml:4-13`` (``backup_scheduler``):
# cada 12 horas, prioridad 5, activo, y ``model.schedule_backup()`` sobre
# ``db.backup``.
#
# ``model_name`` lleva la etiqueta Django del modelo —no su ``_name`` de
# Odoo— porque es lo que ``IrCron._callback`` resuelve con
# ``apps.get_model()``; mismo criterio que ``CRON_AUTOVACUUM`` en ``base``.
CRON_BACKUP = {
    'name': 'Backup scheduler',
    'model_name': 'auto_backup.DbBackup',
    'method_name': 'schedule_backup',
    'interval_number': 12,
    'interval_type': 'hours',
    'priority': 5,
}

__all__ = ['CRON_BACKUP']
