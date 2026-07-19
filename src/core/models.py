"""
core/models.py — modelos de log (transitorio).

Las bases abstractas (``TimeStampedModel``/``AppendOnlyModel``/``SoftDeleteModel``)
se movieron al addon fundacional ``addons/base`` (DEC-09 de
``adoptar-arquitectura-server-service-odoo``); se importan desde ahí. Este módulo
sólo conserva los modelos de log concretos (``RequestLog``, ``AppLog``) que aún
viven en ``core`` mientras se disuelve la app:

- ``AppLog`` → modelo fiel ``ir.logging`` en ``addons/base`` (DEC-08, slice 2).
- ``RequestLog`` → ``addons/observability`` (DEC-08, slice 3).

Hasta que esos slices corran, permanecen aquí sobre ``AppendOnlyModel`` de
``addons.base``.
"""
from django.conf import settings
from django.db import models

from addons.base.models import AppendOnlyModel


class RequestLog(AppendOnlyModel):
    """
    Log universal a nivel request (DEC-LOG-01): una fila por cada request HTTP,
    con cobertura de todos los endpoints via RequestLogMiddleware. PII-safe
    (DEC-LOG-03 nivel 2): el usuario se referencia por FK ``user`` (no se copia
    nombre/email), igual que ``AuthEvent``. La FK usa ``settings.AUTH_USER_MODEL``
    (referencia por string) para no acoplar este modelo a ``addons.users``
    (DEC-LOG-06). ``on_delete=SET_NULL`` conserva el log si el usuario se borra.
    Append-only, alta rotacion (retencion 30 dias, DEC-LOG-05). Se une a
    AppLog/BusinessEvent por ``correlation_id`` (DEC-LOG-07).
    """
    correlation_id = models.CharField(max_length=32, db_index=True)
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=512, db_index=True)
    view_name = models.CharField(max_length=255, blank=True, default='')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    status_code = models.PositiveSmallIntegerField(null=True, blank=True, db_index=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    # Campos de error (nullables), poblados solo en respuestas >=400 (DEC-LOG-01).
    exception_class = models.CharField(max_length=255, blank=True, default='')
    error_detail = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Request Log'
        verbose_name_plural = 'Request Logs'
        indexes = [
            models.Index(fields=['-created_at'], name='requestlog_created_idx'),
        ]

    def __str__(self):
        return f'{self.method} {self.path} -> {self.status_code} ({self.correlation_id})'


class AppLog(AppendOnlyModel):
    """
    Log a nivel handler (DEC-LOG-01): recibe lo que rutea ``LOGGING`` a traves de
    ``DatabaseLogHandler`` — los ``logger.*`` del codigo y ``django.request``
    (5xx). Adaptado de ``StatusLog`` de django-db-logger 0.1.13 (MIT) sobre un
    modelo propio PII-safe (DEC-LOG-06). ``msg`` y ``trace`` ya vienen redactados
    por el ``PIIScrubber`` de Nivel 1 (DEC-LOG-03); no se persiste PII de Nivel 2
    (el usuario se referencia via el ``RequestLog`` de la misma request). Se une a
    ``RequestLog`` / ``BusinessEvent`` por ``correlation_id`` (DEC-LOG-07);
    ``correlation_id`` es vacio fuera de un request (management commands). Alta
    rotacion: retencion 14 d (INFO/DEBUG) / 90 d (WARNING/ERROR) via
    ``purge_logs`` (DEC-LOG-05).
    """
    LEVEL_DEBUG = 'DEBUG'
    LEVEL_INFO = 'INFO'
    LEVEL_WARNING = 'WARNING'
    LEVEL_ERROR = 'ERROR'
    LEVEL_CRITICAL = 'CRITICAL'
    LEVEL_CHOICES = [
        (LEVEL_DEBUG, 'Debug'),
        (LEVEL_INFO, 'Info'),
        (LEVEL_WARNING, 'Warning'),
        (LEVEL_ERROR, 'Error'),
        (LEVEL_CRITICAL, 'Critical'),
    ]

    logger_name = models.CharField(max_length=255, db_index=True)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, db_index=True)
    msg = models.TextField(blank=True, default='')
    trace = models.TextField(blank=True, default='')
    correlation_id = models.CharField(max_length=32, db_index=True, blank=True, default='')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'App Log'
        verbose_name_plural = 'App Logs'
        indexes = [
            models.Index(fields=['-created_at'], name='applog_created_idx'),
        ]

    def __str__(self):
        return f'{self.level} {self.logger_name}: {self.msg[:60]}'
