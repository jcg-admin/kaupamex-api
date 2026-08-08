"""Mixin ``AppendOnlyModel`` — inmutabilidad a nivel de modelo para logs.

En la referencia el ORM auto-inyecta ``create_date``/``write_date``/
``create_uid``/``write_uid`` (``LOG_ACCESS_COLUMNS``) y el archivado es el
campo ``active``; no hay mixin de app equivalente. Aquí se adapta al patrón
Django. El end-state totalmente fiel (auto-inyección en la capa ``orm/``, sin
mixin) queda como alternativa diferida en DEC-09 de
``adoptar-arquitectura-server-service-odoo``.

**Un archivo por mixin**, como ``image_mixin.py`` / ``avatar_mixin.py`` /
``properties_base_definition_mixin.py`` en la referencia. Antes los seis
vivían juntos en ``mixins.py``, agrupados por naturaleza ("son mixins") —
agrupación que la referencia no hace.

Sin homólogo en la referencia: allá la inmutabilidad de un log se apoya en
``_log_access = False`` más reglas de acceso. Aquí se impone en el modelo
(SOL-011, DEC-LOG-05).
"""
from addons.base.models.timestamped_mixin import TimeStampedModel


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
