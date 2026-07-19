"""``RequestLog`` -- telemetria HTTP por request (DEC-LOG-01..08).

Movido desde ``core.models`` al addon net-new ``addons.observability`` en el
slice 3 de ``adoptar-arquitectura-server-service-odoo`` (DEC-08/DEC-12):
``RequestLog`` no tiene analogo en ``odoo/addons/base`` -- es telemetria de
infraestructura propia de este proyecto, no un modelo de dominio Odoo. Ver
``addons/observability/apps.py`` para la justificacion completa de por que
este es el unico addon legitimamente net-new del arbol.

Migracion de datos no destructiva desde ``core.RequestLog`` (tabla
``core_requestlog``) hacia esta tabla (``observability_requestlog``): ver
``addons/observability/migrations/0002_copiar_requestlog_a_observability.py``
y ``core/migrations/0003_eliminar_requestlog.py`` (que depende de la
anterior para garantizar el orden).
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
