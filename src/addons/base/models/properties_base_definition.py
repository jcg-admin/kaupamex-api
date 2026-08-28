"""``properties.base.definition`` — el esquema de las propiedades sin padre.

Adaptación de ``odoo/addons/base/models/properties_base_definition.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 67 líneas).

Qué problema resuelve
=====================

Un campo ``Properties`` guarda pares clave/valor **definidos por el usuario**
sobre un registro. Su esquema —qué propiedades existen, de qué tipo, con qué
valores— normalmente vive en el **padre** del registro: en la referencia, las
propiedades de una tarea las define su proyecto.

Este modelo cubre el caso en que **no hay padre**: guarda una única fila con
la definición para un campo ``Properties`` concreto de un modelo concreto. De
ahí la restricción ``UNIQUE(properties_field_id)`` — un campo, una definición.

La FK **sí** es real, y eso es nuevo
====================================

``properties_field_id`` apunta a ``ir.model.fields``. Medido:
``grep -rn "^class IrModelFields\\b" src/`` → **1** clase [PROVEN], portada en
``api@b618a6b``. Es de los pocos archivos de ``base`` cuya FK principal se
porta **como FK real** en vez de degradarse a ``Char`` — porque su destino ya
existe y no hay una tabla previa que migrar.

Dos invariantes que se conservan y por qué
==========================================

1. **El campo apuntado tiene que ser de tipo ``properties``**
   (``_check_properties_field_id``). Una definición colgada de un ``Char`` no
   define nada; el error se emite al validar, no cuando alguien intente leer
   una propiedad que no existe.
2. **``properties_field_id`` no se puede cambiar** después de creado
   (``write`` levanta ``AccessError``). La razón está en el modelo: la fila
   *es* la definición **de ese campo**; reapuntarla dejaría a todos los
   registros que usan la definición vieja apuntando a un esquema que ya
   describe otra cosa. Se porta como error, no como aviso.

Primer adoptante de ``FieldSqlMixin``
=====================================

``orm.models.FieldSqlMixin`` porta ``_field_to_sql`` y sus tres dependencias
(tarea #127). Allá cuelgan de ``BaseModel``, así que **todo** modelo los tiene;
aquí ``models.Model`` es el de Django y el mecanismo se adopta, como
``objects = AccessManager()`` y ``OriginMixin`` — la divergencia que
``orm/models.py`` declara.

Este modelo es el primero que lo adopta, y no por casualidad: su mixin hermano
``properties_base_definition_mixin.py`` es quien llama a
``super()._field_to_sql``, y este modelo tiene las dos formas que el mecanismo
resuelve — una FK real (``properties_field``) y un campo JSON
(``properties_definition``) del que se extrae una propiedad con ``->``. Qué
modelos más lo adoptan es la tarea **#96**.

Los cinco símbolos y su enganche de Django
==========================================

Los cinco métodos de la referencia se portan **con su nombre y su firma**, y
los enganches de Django delegan en ellos — el mismo patrón que
``ir_config_parameter.py``: así la guarda protege también a quien escriba por
la vía del ORM de Django.

.. list-table::
   :header-rows: 1

   * - Referencia
     - Aquí
     - Enganche que delega
   * - ``_compute_display_name``
     - ``_compute_display_name``
     - ``__str__``
   * - ``_check_properties_field_id``
     - ``_check_properties_field_id``
     - ``clean``
   * - ``write``
     - ``write``
     - ``save``
   * - ``_get_definition_for_property_field``
     - ídem
     - —
   * - ``_get_definition_id_for_property_field``
     - ídem, con ``@ormcache``
     - —

``ormcache`` adoptado — la razón anterior caducó
================================================

Hasta ``api@c3e6396a`` este archivo construía un ``_DEFINITION_CACHE`` de
módulo con su ``_clear_definition_cache()``, y lo justificaba citando a
``ir_config_parameter.py``. Esa cita ya no vale: aquel archivo adoptó el
decorador real (H-API-865), y el mecanismo —``tools/cache.py``,
``tools/lru.py`` y los contenedores de ``orm/registry.py``— existe desde
``api@c636e68c`` (H-API-864). Se adopta
``@ormcache("model_name", "field_name", cache='stable')`` y la invalidación
deja de ser global para ser la de la familia ``stable``.

DIVERGENCIA DE CLAVE, declarada (la misma que ``ir_config_parameter.py``): la
referencia no nombra la base porque su ``Registry`` es por base de datos y esa
dimensión va implícita en él. Aquí el registry es el módulo —divergencia de
enlace declarada en ``tools/cache.py``—, así que el alias entra en la clave:
``@ormcache('model_name', 'field_name', 'using', ...)``. Sin él dos bases
compartirían entrada, que es un defecto que la fuente no tiene.
"""
import logging

import fields
import models
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DEFAULT_DB_ALIAS

from addons.base.models.ir_model import IrModelFields
from addons.base.models.timestamped_mixin import TimeStampedModel
from orm import registry
from orm.models import FieldSqlMixin
from tools.cache import ormcache

_logger = logging.getLogger(__name__)

#: ``ttype`` que un campo debe tener para admitir una definición.
PROPERTIES_TTYPE = 'properties'


class PropertiesBaseDefinition(FieldSqlMixin, TimeStampedModel):
    """``properties.base.definition`` — la definición de un campo ``Properties``."""

    _name = 'properties.base.definition'
    _description = 'Properties Base Definition'

    properties_field = fields.Many2one(
        IrModelFields, on_delete=models.CASCADE, unique=True,
        related_name='properties_definition_ids',
        verbose_name='Campo de propiedades',
        help_text='FK real: ir.model.fields está portado. Único — un campo, '
                  'una definición.',
    )
    properties_definition = fields.Json(
        default=list, blank=True, verbose_name='Definición de las propiedades',
        help_text='El esquema: qué propiedades existen, de qué tipo y con qué '
                  'valores posibles.',
    )

    class Meta:
        db_table = 'properties_base_definition'
        verbose_name = 'Definición base de propiedades'
        verbose_name_plural = 'Definiciones base de propiedades'
        constraints = [
            # ``_unique_properties_field_id``.
            models.UniqueConstraint(
                fields=['properties_field'],
                name='properties_base_definition_unique_field'),
        ]

    # -- Presentación --------------------------------------------------------

    def _compute_display_name(self):
        """``_compute_display_name`` — ``"<Descripción del modelo> Properties"``.

        ≙ ``odoo19c: properties_base_definition.py:25-34``. La fuente lee el
        ``_description`` del modelo apuntado; aquí se lee el ``_description``
        portado si el modelo está en el registro por nombre, y si no el
        propio nombre técnico. Sin modelo apuntado devuelve ``False``, igual
        que la fuente.
        """
        if not self.properties_field_id:
            return False
        model_name = getattr(self.properties_field, 'model', '')
        if not model_name:
            return False
        model_cls = registry.MODELS_BY_NAME.get(model_name)
        description = getattr(model_cls, '_description', None) or model_name
        return f'{description} Properties'

    def __str__(self):
        """Enganche de Django — delega en ``_compute_display_name``."""
        return self._compute_display_name() or 'Properties'

    # -- Validación ----------------------------------------------------------

    def _check_properties_field_id(self):
        """``_check_properties_field_id`` — el campo apuntado es ``properties``.

        ≙ ``odoo19c: properties_base_definition.py:36-41``.
        """
        field = self.properties_field
        if field is not None and field.ttype != PROPERTIES_TTYPE:
            raise ValidationError(
                f'La definición debe apuntar a un campo de propiedades; '
                f'{field.name!r} es de tipo {field.ttype!r}.'
            )

    def clean(self):
        """Enganche de Django — delega en ``_check_properties_field_id``."""
        super().clean()
        self._check_properties_field_id()

    # -- Escritura -----------------------------------------------------------

    def write(self, vals, using=None):
        """``write`` — el campo apuntado no se cambia después de crear.

        ≙ ``odoo19c: properties_base_definition.py:43-46``. Reapuntar la fila
        dejaría a todos los registros que usan la definición vieja
        describiendo otra cosa. La fuente levanta ``AccessError``; aquí el
        equivalente del stack es ``PermissionDenied`` — no es una violación de
        forma del dato sino de permiso sobre el campo.
        """
        using = using or self._state.db or DEFAULT_DB_ALIAS
        if 'properties_field' in vals or 'properties_field_id' in vals:
            raise PermissionDenied(
                'No se puede cambiar el campo de una definición base.')
        for field_name, value in vals.items():
            setattr(self, field_name, value)
        # ``save`` es quien vacía la familia; no se duplica aquí ni se bypassa
        # el enganche, para que un mixin futuro siga entrando en la cadena.
        return self.save(using=using)

    def save(self, *args, **kwargs):
        """Enganche de Django — corre la guarda de ``write`` y vacía la familia."""
        if self.pk is not None:
            stored = type(self).objects.filter(pk=self.pk).values_list(
                'properties_field_id', flat=True).first()
            if stored is not None and stored != self.properties_field_id:
                raise PermissionDenied(
                    'No se puede cambiar el campo de una definición base.')
        super().save(*args, **kwargs)
        registry.clear_cache('stable')

    def delete(self, *args, **kwargs):
        """Enganche de Django — vacía la familia tras borrar."""
        result = super().delete(*args, **kwargs)
        registry.clear_cache('stable')
        return result

    # -- Lectura memorizada --------------------------------------------------

    @classmethod
    def _get_definition_for_property_field(cls, model_name, field_name,
                                           using=DEFAULT_DB_ALIAS):
        """``_get_definition_for_property_field`` — la fila, no el id.

        ≙ ``odoo19c: properties_base_definition.py:48-49``.
        """
        return cls.objects.using(using).get(
            pk=cls._get_definition_id_for_property_field(
                model_name, field_name, using=using))

    @classmethod
    @ormcache('model_name', 'field_name', 'using', cache='stable')
    def _get_definition_id_for_property_field(cls, model_name, field_name,
                                              using=DEFAULT_DB_ALIAS):
        """``_get_definition_id_for_property_field`` — id de la definición.

        ≙ ``odoo19c: properties_base_definition.py:51-67``. La crea si no
        existe, igual que la fuente: pedir la definición de un campo de
        propiedades **siempre** debe devolver una, o el campo no se puede
        editar.

        El decorador nombra ``using`` además de los dos de la fuente — ver la
        divergencia de clave declarada en la cabecera del módulo.
        """
        row = cls.objects.using(using).filter(
            properties_field__model=model_name,
            properties_field__name=field_name,
        ).first()
        if row is None:
            field = IrModelFields.objects.using(using).filter(
                model=model_name, name=field_name).first()
            if field is None:
                raise ValidationError(
                    f'No hay un campo {field_name!r} reflejado en '
                    f'{model_name!r}; refleje el modelo antes de pedir su '
                    f'definición de propiedades.'
                )
            row = cls.objects.using(using).create(properties_field=field)
        return row.pk
