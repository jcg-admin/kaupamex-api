"""SystemParameter (L2) — config runtime global key/value (app ``addons.base``).

Portación **fiel** de Odoo ``ir.config_parameter``
(``scratchpad/odoo19x/odoo/addons/base/models/ir_config_parameter.py`` y
``scratchpad/odoo18/extracted/odoo/addons/base/models/ir_config_parameter.py`` —
arquitectura idéntica en v19 y v18). Diseño: capa L2 de
``analisis-estrategia-configuracion-capas``. Hallazgos de la portación:
``hallazgos-implementar-systemparameter-l2``.

Correspondencia Odoo -> Django (adaptación sin azúcar sintáctica):

- ``_name='ir.config_parameter'`` / ``_description='System Parameter'`` ->
  modelo ``SystemParameter`` (``verbose_name='System Parameter'``).
- ``key = Char(required=True)`` + ``unique (key)`` -> ``CharField(unique=True)``.
  Odoo ``Char`` no fija longitud; en MariaDB un índice único requiere longitud,
  así que se fija ``max_length=255`` (adaptación de motor, H-CFG-IMPL-05).
- ``value = Text(required=True)`` -> ``TextField``.
- ``_order='key'`` -> ``Meta.ordering=['key']``; ``_rec_name='key'`` ->
  ``__str__`` devuelve ``key``.
- ``_default_parameters`` (dict clave->callable) -> ``_DEFAULT_PARAMETERS``
  módulo-nivel. **Fuente de verdad de la protección**: NO existe una columna
  ``is_system`` en Odoo (H-CFG-IMPL-01 corrige el análisis, que la había
  especulado). Una clave está protegida ssi pertenece a este dict.
- ``get_param``/``set_param``/``init`` (``@api.model``) -> ``classmethod`` s
  (``seed`` == ``init``).
- ``@ormcache('key', cache='stable')`` + ``clear_cache('stable')`` -> caché
  módulo-nivel ``_PARAM_CACHE`` invalidada en toda mutación (H-CFG-IMPL-02).
- ``write`` rechaza renombrar una clave protegida; ``unlink_default_parameters``
  (``@api.ondelete``) rechaza borrar una clave protegida -> guards en ``save``
  y ``delete``.
"""
import uuid

from django.core.exceptions import ValidationError
from django.db import DEFAULT_DB_ALIAS, models

# Parámetros sembrados al inicializar la instancia (Odoo ``_default_parameters``,
# líneas 18-25 de ir_config_parameter.py, v19/v18 idénticas). Pertenecer a este
# dict == estar protegido contra borrado y renombrado. El valor es un callable
# perezoso (se evalúa al sembrar), fiel a Odoo.
_DEFAULT_PARAMETERS = {
    'database.uuid': lambda: str(uuid.uuid1()),
    'database.secret': lambda: str(uuid.uuid4()),
}

# Caché por-proceso, equivalente a ``ormcache('key', cache='stable')`` de Odoo.
# Clave: ``(using, key)`` -> value (o ``None`` para "clave ausente", igual que
# Odoo cachea el resultado del SELECT incluyendo la ausencia). Invalidación
# global en cada mutación (Odoo ``clear_cache('stable')``). H-CFG-IMPL-02: como
# ormcache, es per-proceso; la invalidación cross-worker (registry signaling de
# Odoo) queda fuera de scope de esta slice.
_PARAM_CACHE = {}


def _clear_cache():
    """Invalida toda la caché (Odoo ``clear_cache('stable')`` — namespace entero)."""
    _PARAM_CACHE.clear()


class SystemParameter(models.Model):
    """Almacén per-instancia de pares clave/valor de configuración (L2 global).

    Equivalente a ``ir.config_parameter``. Vive en el plano de control
    (``default``); no es per-empresa (eso es L3).
    """

    key = models.CharField(max_length=255, unique=True)
    value = models.TextField()

    class Meta:
        db_table = 'system_parameter'
        ordering = ['key']
        verbose_name = 'System Parameter'
        verbose_name_plural = 'System Parameters'

    def __str__(self):
        return self.key

    # -- Lectura (Odoo get_param / _get_param) ------------------------------

    @classmethod
    def get_param(cls, key, default=None, using=DEFAULT_DB_ALIAS):
        """Devuelve el valor de ``key``, o ``default`` si no existe.

        Fiel a Odoo ``get_param`` (línea 60): ``return self._get_param(key) or
        default``. El ``or default`` implica que un valor almacenado *falsy*
        (cadena vacía) también devuelve ``default`` — quirk heredado de Odoo
        (H-CFG-IMPL-03), documentado y preservado por fidelidad.
        """
        return cls._get_param(key, using=using) or default

    @classmethod
    def _get_param(cls, key, using=DEFAULT_DB_ALIAS):
        """Lee el valor crudo con caché. Odoo bypassa el ORM con SQL directo
        (líneas 73-79) porque ``get_param`` se usa en ``@api.depends`` con el ORM
        a medio inicializar; Django no tiene esa restricción, así que se usa el
        ORM normal (H-CFG-IMPL-04). Cachea también la ausencia (``None``)."""
        ckey = (using, key)
        if ckey in _PARAM_CACHE:
            return _PARAM_CACHE[ckey]
        value = (cls.objects.using(using)
                 .filter(key=key)
                 .values_list('value', flat=True)
                 .first())
        _PARAM_CACHE[ckey] = value
        return value

    # -- Escritura (Odoo set_param) -----------------------------------------

    @classmethod
    def set_param(cls, key, value, using=DEFAULT_DB_ALIAS):
        """Fija el valor de ``key``; devuelve el valor previo (o ``None``).

        Fiel a Odoo ``set_param`` (líneas 82-103): si la clave existe y el valor
        es *None/False* -> borra; si cambió -> actualiza; devuelve el valor
        previo. Si no existe y el valor no es *None/False* -> crea; devuelve
        ``None`` (Odoo devuelve ``False``).
        """
        param = cls.objects.using(using).filter(key=key).first()
        if param is not None:
            old = param.value
            if value is not None and value is not False:
                if str(value) != old:
                    param.value = str(value)
                    param.save(using=using)  # save() invalida la caché
            else:
                param.delete(using=using)    # delete() invalida la caché
            return old
        if value is not None and value is not False:
            cls.objects.using(using).create(key=key, value=str(value))
            _clear_cache()
        return None

    # -- Sembrado (Odoo init) -----------------------------------------------

    @classmethod
    def seed(cls, force=False, using=DEFAULT_DB_ALIAS):
        """Siembra ``_DEFAULT_PARAMETERS`` (Odoo ``init``, líneas 44-57).

        Idempotente: sólo crea las claves ausentes; ``force=True`` sobreescribe
        las existentes.
        """
        for key, func in _DEFAULT_PARAMETERS.items():
            exists = cls.objects.using(using).filter(key=key).exists()
            if force or not exists:
                cls.set_param(key, func(), using=using)

    # -- Guards de protección (Odoo write / unlink_default_parameters) ------

    def save(self, *args, **kwargs):
        """Invalida la caché e impide renombrar una clave protegida.

        Fiel a Odoo ``write`` (líneas 110-116): si se cambia ``key`` a/desde una
        clave de ``_DEFAULT_PARAMETERS``, rechaza. Sólo aplica a updates (pk no
        nulo); las inserciones no renombran nada.
        """
        if self.pk is not None:
            using = kwargs.get('using') or self._state.db or DEFAULT_DB_ALIAS
            old_key = (type(self).objects.using(using)
                       .filter(pk=self.pk)
                       .values_list('key', flat=True)
                       .first())
            if (old_key is not None and old_key != self.key
                    and old_key in _DEFAULT_PARAMETERS):
                raise ValidationError(
                    'No se puede renombrar el parámetro protegido "%s".' % old_key)
        _clear_cache()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Invalida la caché e impide borrar una clave protegida.

        Fiel a Odoo ``unlink_default_parameters`` (``@api.ondelete``, líneas
        122-125): una clave de ``_DEFAULT_PARAMETERS`` no se puede eliminar.
        """
        if self.key in _DEFAULT_PARAMETERS:
            raise ValidationError(
                'No se puede eliminar el parámetro protegido "%s".' % self.key)
        _clear_cache()
        return super().delete(*args, **kwargs)
