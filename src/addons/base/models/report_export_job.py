"""Modelo ``ExportJob`` — addon ``base`` (framework de reportes).

Hogar fiel del registro de estado de una exportación asíncrona de reporte.
En Odoo el framework de reportes vive en ``base``/``web``
(``ir.actions.report`` + QWeb); no existe un módulo ``reports`` separado. Este
``ExportJob`` es la contraparte de estado del export asíncrono (rama
``rows>5000`` de UC-REP-05): sin Celery/Redis, la exportación larga corre en un
``threading.Thread`` (mismo patrón sin-Celery que ``base``… y que
``auto_backup.BackupRecord``) y este registro guarda su estado y la ruta del
archivo generado para que el admin consulte el endpoint de status y descargue
vía URL firmada y con expiración.

Identifiers + field names in English per DEC-DOC-005.
"""
from django.conf import settings
from django.db import models

from addons.base.models.timestamped_mixin import TimeStampedModel


class ExportJob(TimeStampedModel):
    """State of one asynchronous report export."""

    STATUS_PENDING = 'PENDING'
    STATUS_RUNNING = 'RUNNING'
    STATUS_DONE    = 'DONE'
    STATUS_ERROR   = 'ERROR'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pendiente'),
        (STATUS_RUNNING, 'En proceso'),
        (STATUS_DONE,    'Completado'),
        (STATUS_ERROR,   'Error'),
    ]

    status       = models.CharField(max_length=10, choices=STATUS_CHOICES,
                                     default=STATUS_PENDING)
    # Absolute path of the generated file on disk (filled by the worker).
    file_path    = models.CharField(max_length=500, blank=True, default='')
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='export_jobs',
    )
    # Export request parameters: {slug, format, days, ...}.
    params       = models.JSONField(default=dict, blank=True)
    error_detail = models.TextField(blank=True, default='')
    # When the generated file/download link should be considered expired.
    expires_at   = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'report_export_job'
        ordering = ['-created_at']
        verbose_name = 'Export job'
        verbose_name_plural = 'Export jobs'

    def __str__(self):
        return f'ExportJob#{self.pk} {self.status}'
