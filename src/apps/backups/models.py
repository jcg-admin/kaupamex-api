"""
Models — apps.backups (UC-ADM-05).

BackupRecord tracks every backup execution (cron or manual on-demand).
The actual dump is performed by db/scripts/backup_db.sh and
db/scripts/backup_proyectos.sh; this model stores the metadata so
AdminBackupsPage can list history and report status.
"""
from django.db import models
from apps.core.models import TimeStampedModel


class BackupRecord(TimeStampedModel):
    """Metadata for one backup execution."""

    TYPE_AUTO   = 'AUTO'
    TYPE_MANUAL = 'MANUAL'
    TYPE_CHOICES = [
        (TYPE_AUTO,   'Automático'),
        (TYPE_MANUAL, 'Manual'),
    ]

    STATUS_PENDING = 'PENDING'
    STATUS_OK      = 'OK'
    STATUS_ERROR   = 'ERROR'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pendiente'),
        (STATUS_OK,      'Completado'),
        (STATUS_ERROR,   'Error'),
    ]

    type         = models.CharField(max_length=10, choices=TYPE_CHOICES,
                                    default=TYPE_AUTO)
    status       = models.CharField(max_length=10, choices=STATUS_CHOICES,
                                    default=STATUS_PENDING)
    # Human-readable label: filename stem or error message
    filename     = models.CharField(max_length=255, blank=True, default='')
    size_bytes   = models.PositiveBigIntegerField(null=True, blank=True)
    # Optional download URL (e.g. signed S3 URL filled in by cron)
    download_url = models.URLField(max_length=500, blank=True, default='')
    error_detail = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'backup_record'
        ordering = ['-created_at']
        verbose_name = 'Backup'
        verbose_name_plural = 'Backups'

    def __str__(self):
        return f'BackupRecord#{self.pk} {self.type} {self.status}'
