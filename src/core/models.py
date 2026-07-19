"""
core/models.py — modelos de log (transitorio).

Las bases abstractas (``TimeStampedModel``/``AppendOnlyModel``/``SoftDeleteModel``)
se movieron al addon fundacional ``addons/base`` (DEC-09 de
``adoptar-arquitectura-server-service-odoo``); se importan desde ahí. Este módulo
sólo conservaba los modelos de log concretos (``RequestLog``, ``AppLog``) que
vivían en ``core`` mientras se disuelve la app:

- ``AppLog`` → migrado al modelo fiel ``IrLogging`` (``ir.logging``) en
  ``addons/base`` (DEC-08, slice 2 de ``adoptar-arquitectura-server-service-odoo``).
  Ver ``addons/base/models/ir_logging_log.py`` para el mapeo de campos y
  ``addons/base/migrations/0007_copiar_applog_a_irlogging.py`` +
  ``core/migrations/0002_eliminar_applog.py`` para la migración de datos/esquema
  (no destructiva). Ya no se define aquí.
- ``RequestLog`` → pendiente de mover a ``addons/observability`` (DEC-08, slice 3).

``RequestLog`` permanece aquí sobre ``AppendOnlyModel`` de ``addons.base``
hasta que ese slice corra.
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
