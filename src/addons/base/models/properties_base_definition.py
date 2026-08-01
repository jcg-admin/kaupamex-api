"""``properties.base.definition`` — el esquema de las propiedades sin padre.

Adaptación de ``odoo/addons/base/models/properties_base_definition.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 67 líneas).

Qué problema resuelve
=====================

Un campo ``Properties`` guarda pares clave/valor **definidos por el usuario**
sobre un registro. Su esquema —qué propiedades existen, de qué tipo, con qué
valores— normalmente vive en el **padre** del registro: en Odoo, las
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

Qué NO se porta, con su medición
================================

- **``ormcache``** sobre ``_get_definition_id_for_property_field``: es el
  decorador de caché del ORM de Odoo. Aquí se usa un diccionario de módulo con
  su función de limpieza, mismo patrón que ``ir_config_parameter.py`` ya
  aplica con ``_PARAM_CACHE`` / ``_clear_cache`` — así el mecanismo de caché
  del árbol es uno solo y no dos.
- **``_compute_display_name``**: compone ``"<Descripción> Properties"``
  leyendo la descripción del modelo apuntado. Se porta como ``__str__``, con
  el ``verbose_name`` del modelo Django en el papel del ``_description``.
"""
import logging

import fields
import models
from django.core.exceptions import ValidationError

from addons.base.models.ir_model import IrModelFields
from addons.base.models.timestamped_mixin import TimeStampedModel

_logger = logging.getLogger(__name__)

#: ``ttype`` que un campo debe tener para admitir una definición.
PROPERTIES_TTYPE = 'properties'

#: Caché ``(modelo, campo) → id de definición``. Sustituye al ``ormcache`` de
#: la referencia; mismo patrón que ``_PARAM_CACHE`` en
#: ``ir_config_parameter.py``.
_DEFINITION_CACHE = {}


def _clear_definition_cache():
    """Vacía la caché de definiciones. Llamar tras crear o borrar una fila."""
    _DEFINITION_CACHE.clear()


class PropertiesBaseDefinition(TimeStampedModel):
    """``properties.base.definition`` — la definición de un campo ``Properties``."""

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

    def __str__(self):
        """``_compute_display_name`` — ``"<Modelo> Properties"``."""
        model_name = getattr(self.properties_field, 'model', '')
        return f'{model_name} Properties' if model_name else 'Properties'

    def clean(self):
        """``_check_properties_field_id`` — el campo apuntado es ``properties``."""
        super().clean()
        field = self.properties_field
        if field is not None and field.ttype != PROPERTIES_TTYPE:
            raise ValidationError(
                f'La definición debe apuntar a un campo de propiedades; '
                f'{field.name!r} es de tipo {field.ttype!r}.'
            )

    def save(self, *args, **kwargs):
        """``write`` — el campo apuntado no se cambia después de crear.

        Reapuntar la fila dejaría a todos los registros que usan la definición
        vieja describiendo otra cosa. Ver el docstring del módulo.
        """
        if self.pk is not None:
            stored = type(self).objects.filter(pk=self.pk).values_list(
                'properties_field_id', flat=True).first()
            if stored is not None and stored != self.properties_field_id:
                raise ValidationError(
                    'No se puede cambiar el campo de una definición base.')
        super().save(*args, **kwargs)
        _clear_definition_cache()

    @classmethod
    def definition_id_for(cls, model_name, field_name):
        """``_get_definition_id_for_property_field`` — id de la definición.

        La crea si no existe, igual que la fuente: pedir la definición de un
        campo de propiedades **siempre** debe devolver una, o el campo no se
        puede editar. Cacheada por ``(modelo, campo)``.
        """
        key = (model_name, field_name)
        if key in _DEFINITION_CACHE:
            return _DEFINITION_CACHE[key]

        row = cls.objects.filter(
            properties_field__model=model_name,
            properties_field__name=field_name,
        ).first()
        if row is None:
            field = IrModelFields.objects.filter(
                model=model_name, name=field_name).first()
            if field is None:
                raise ValidationError(
                    f'No hay un campo {field_name!r} reflejado en '
                    f'{model_name!r}; refleje el modelo antes de pedir su '
                    f'definición de propiedades.'
                )
            row = cls.objects.create(properties_field=field)
        _DEFINITION_CACHE[key] = row.pk
        return row.pk

    @classmethod
    def definition_for(cls, model_name, field_name):
        """``_get_definition_for_property_field`` — la fila, no el id."""
        return cls.objects.get(pk=cls.definition_id_for(model_name, field_name))
