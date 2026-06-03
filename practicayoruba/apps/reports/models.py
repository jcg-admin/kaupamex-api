"""
Models — apps.reports.

The aggregation endpoints are read-only over existing tables. The only
persistent model is ExportJob, which tracks an asynchronous report export
(D-19, UC-REP-05 rows>5000 branch). There is no Celery/Redis in the project,
so the long export runs in a threading.Thread worker (same no-Celery pattern
as apps.backups.BackupRecord) and this record stores its state and the path
of the generated file so the admin can poll the status endpoint and download
the file via a signed, time-limited URL.
"""
from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


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
