"""
apps/core/models.py

TimeStampedModel — clase base abstracta para todos los modelos del proyecto.
SoftDeleteModel  — clase base abstracta que implementa la politica
                   DEC-DOC-007 (delete logico obligatorio).

Decisiones de diseño documentadas en:
  gestion/herencia-modelos-django/decisiones-herencia-modelos-django.rst
  gestion/decisiones/index.rst  (DEC-DOC-007)

- DEC-001: herencia abstracta (no multi-tabla, no proxy para timestamps)
- DEC-002: una sola clase — CreatedModel descartado (viola DRY y O/C)
- DEC-003: sin db_index en la base — los modelos que lo necesitan lo
           declaran explícitamente (StockMovement, StockAlert, Order)
- DEC-004: sin ordering — cada modelo concreto define el suyo
- DEC-005: User excluido — hereda de AbstractUser de Django
- DEC-007: cualquier modelo que represente historial de negocio
           hereda de SoftDeleteModel. Excepciones: tablas append-only
           (StockMovement, Notification, VoucherChangeLog).
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """
    Clase base abstracta que provee created_at y updated_at a todos
    los modelos que hereden de ella.

    Usar en TODOS los modelos concretos del proyecto excepto User.
    No incluye ordering — cada modelo define el suyo.
    No incluye db_index en created_at — los modelos que requieren
    índice por volumen (inventario, órdenes) lo declaran directamente.
    """
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        abstract      = True
        get_latest_by = 'created_at'


class AppendOnlyModel(TimeStampedModel):
    """
    Base abstracta append-only para logs (SOL-011, DEC-LOG-05). Impone la
    inmutabilidad a nivel de modelo, no solo por docstring o por el endpoint
    read-only (405): permite el INSERT inicial pero prohibe el UPDATE de
    instancia (``save`` sobre una fila ya persistida -> ``PermissionError``) y
    el DELETE de instancia (``obj.delete()`` -> ``PermissionError``).

    La purga por retencion (``purge_logs``) usa ``QuerySet.delete()`` en bulk,
    que NO invoca el ``delete()`` de instancia — por eso la retencion sigue
    funcionando sin excepcion. Precedente adaptado de CNST-009 (otro proyecto):
    un log de auditoria/tecnico que se puede editar o borrar puntualmente no es
    prueba fiable.
    """

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionError(
                f'{type(self).__name__} es append-only: UPDATE no permitido')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError(
            f'{type(self).__name__} es append-only: DELETE de instancia no '
            f'permitido (usar purga bulk por retencion)')


class SoftDeleteQuerySet(models.QuerySet):
    """
    QuerySet con metodo ``delete`` que aplica soft delete:
    marca todas las filas con ``is_deleted=True`` y ``deleted_at=now()``
    en una sola operacion UPDATE.

    Para borrado fisico real (solo migraciones/limpieza), usar
    ``hard_delete()``.
    """

    def delete(self):
        return self.update(is_deleted=True, deleted_at=timezone.now())

    def hard_delete(self):
        return super().delete()

    def alive(self):
        return self.filter(is_deleted=False)

    def dead(self):
        return self.filter(is_deleted=True)


class SoftDeleteManager(models.Manager):
    """
    Manager por defecto: filtra ``is_deleted=False`` automaticamente
    en todas las consultas. Las filas marcadas como borradas son
    invisibles para el codigo de produccion y los endpoints DRF.
    """

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(
            is_deleted=False,
        )


class AllObjectsManager(models.Manager):
    """
    Manager auxiliar que no filtra. Uso: admin, auditoria, exportes
    historicos y tests de contrato soft-delete.
    """

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db)


class SoftDeleteModel(models.Model):
    """
    Mixin abstracto que implementa la politica DEC-DOC-007.

    Provee:
      - ``is_deleted`` (BooleanField, default False, indexado).
      - ``deleted_at`` (DateTimeField, nullable).
      - manager por defecto ``objects`` (filtra ``is_deleted=False``).
      - manager ``all_objects`` (sin filtro) para auditoria.
      - ``delete()`` (override): marca soft-delete en lugar de
        eliminar fisicamente.
      - ``hard_delete()``: borrado real (uso interno).
      - ``restore()``: revierte el soft delete.

    Usar como segunda base junto a ``TimeStampedModel`` cuando el
    modelo represente historial de negocio o pueda referenciarse
    desde otra tabla con CASCADE.
    """
    is_deleted = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='Eliminado (logico)',
        help_text='True si la fila fue borrada via soft delete.',
    )
    deleted_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Fecha de borrado logico',
    )

    objects     = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):  # noqa: D401
        """Override: soft delete por defecto. DEC-DOC-007."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(
            update_fields=['is_deleted', 'deleted_at', 'updated_at']
            if hasattr(self, 'updated_at')
            else ['is_deleted', 'deleted_at'],
            using=using,
        )
        return (1, {self._meta.label: 1})

    def hard_delete(self, using=None, keep_parents=False):
        """Borrado fisico real. Usar solo en migraciones/cleanup."""
        return super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        """Revierte el soft delete."""
        self.is_deleted = False
        self.deleted_at = None
        self.save(
            update_fields=['is_deleted', 'deleted_at', 'updated_at']
            if hasattr(self, 'updated_at')
            else ['is_deleted', 'deleted_at'],
        )


class RequestLog(AppendOnlyModel):
    """
    Log universal a nivel request (DEC-LOG-01): una fila por cada request HTTP,
    con cobertura de todos los endpoints via RequestLogMiddleware. PII-safe
    (DEC-LOG-03 nivel 2): el usuario se referencia por FK ``user`` (no se copia
    nombre/email), igual que ``AuthEvent``. La FK usa ``settings.AUTH_USER_MODEL``
    (referencia por string) para preservar ``apps.core`` como nivel 0 sin import
    de ``apps.users`` (DEC-LOG-06). ``on_delete=SET_NULL`` conserva el log si el
    usuario se borra. Append-only, alta rotacion (retencion 30 dias, DEC-LOG-05).
    Se une a AppLog/BusinessEvent por ``correlation_id`` (DEC-LOG-07).
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
