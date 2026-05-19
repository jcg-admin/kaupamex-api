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
        self.save(update_fields=['is_deleted', 'deleted_at'])
