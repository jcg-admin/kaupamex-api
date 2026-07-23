"""Mixins abstractos de base de modelo — addon ``base`` (fundacional).

Bases abstractas Django consumidas por los ``addons/**`` del proyecto. Viven en
``addons/base`` (el addon fundacional del que todos dependen) porque son
comportamiento de **base de modelo** compartido, no de un dominio concreto —
DEC-09 de ``adoptar-arquitectura-server-service-odoo``.

En Odoo el ORM auto-inyecta ``create_date``/``write_date``/``create_uid``/
``write_uid`` (``LOG_ACCESS_COLUMNS``, ``odoo/orm/models.py:296`` en 19) y el
archivado es el campo ``active`` — no hay un mixin de app equivalente. Aquí se
adaptan al patrón Django (mixin abstracto). El end-state totalmente fiel
(auto-inyección en la capa ``orm/``, sin mixin) queda registrado como
alternativa diferida en DEC-09.

- ``TimeStampedModel`` — ``created_at``/``updated_at`` (≙ log-access de Odoo).
- ``AppendOnlyModel`` — inmutabilidad a nivel de modelo para logs (SOL-011).
- ``SoftDeleteModel`` (+ ``SoftDeleteQuerySet``/``SoftDeleteManager``/
  ``AllObjectsManager``) — borrado lógico (DEC-DOC-007; ≙ ``active`` de Odoo).

Decisiones de diseño originales:
  gestion/herencia-modelos-django/decisiones-herencia-modelos-django.rst
  gestion/decisiones/index.rst  (DEC-DOC-007)
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
