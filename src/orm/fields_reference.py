"""Campos de referencia — fiel a ``odoo/orm/fields_reference.py`` (Odoo 19).

Los dos son **pseudo-relacionales**: no hay clave foránea en la base.

- :class:`Reference` (``odoo19c: :13-55``) es una ``Selection`` de nombres de
  modelo cuyo valor se guarda como ``"modelo,id"`` en una columna ``varchar``.
  Aquí es una subclase de :class:`~orm.fields_selection.SelectionField`, y por
  la misma razón medida que ella ``deconstruct`` publica la ruta de
  ``CharField``: la columna no cambia de tipo.
- :class:`Many2oneReference` (``:58-118``) guarda sólo el id en un entero; el
  modelo lo dice otro campo del registro, cuyo nombre lleva ``model_field``.
  Aquí es una subclase de ``models.IntegerField``.

Hasta TASK-API-0485 los dos eran alias de ``GenericForeignKey``, que es otro
mecanismo —un par ``content_type`` + ``object_id`` y no una columna—, y ningún
addon del árbol los declaraba.

**El entorno.** La fuente lee ``record.env``; aquí una fila de Django no lleva
entorno, así que las conversiones toman el del registro si lo tiene y, si no,
el entorno en curso (``orm.environments.env``).

Pendiente, con su condición de cierre: ``Many2oneReference._update_inverses``
y ``_record_ids_per_res_model`` (``:89-118``) añaden los registros a la caché
de los ``One2many`` que tienen a este campo por inverso. Ningún modelo del
árbol declara hoy ese inverso, así que no hay consumidor contra el que
medirlos; se portan cuando el primero lo declare.
"""

from django.db import models

import orm.utils as orm_utils
from orm.environments import env as current_environment
from orm.fields_selection import SelectionField

__all__ = ['Reference', 'Many2oneReference']


def _environment_of(record):
    """El entorno del registro, o el que esté en curso."""
    return getattr(record, 'env', None) or current_environment()


def _model_name_of(value):
    """El nombre de la referencia de una fila, o su etiqueta de Django."""
    return getattr(type(value), '_name', None) or value._meta.label


class Reference(SelectionField):
    """≙ ``class Reference(Selection)`` (``odoo19c: fields_reference.py:13``).

    *"Pseudo-relational field (no FK in database). The field value is stored
    as a string following the pattern ``"res_model,res_id"`` in database."*
    """

    type = 'reference'

    def convert_to_column(self, value, record, values=None, validate=True):
        """≙ ``:24-25``: el de ``Field``, sin validar contra la selección."""
        return models.Field.convert_to_column(
            self, value, record, values, validate)

    def convert_to_cache(self, value, record, validate=True):
        """≙ ``:27-40``. Formato de caché: ``"modelo,id"`` o ``None``."""
        if isinstance(value, models.Model):
            if not validate or _model_name_of(value) in self.get_values(
                    _environment_of(record)):
                return f'{_model_name_of(value)},{value.pk}' if value else None
        elif isinstance(value, str) and value:
            res_model, res_id = value.split(',')
            if not validate or res_model in self.get_values(
                    _environment_of(record)):
                model = _environment_of(record)[res_model]
                if model._base_manager.filter(pk=int(res_id)).exists():
                    return value
                return None
        elif not value:
            return None
        raise ValueError(f'Wrong value for {self}: {value!r}')

    def convert_to_record(self, value, record):
        """≙ ``:42-46``: la fila a la que apunta el valor."""
        if value:
            res_model, res_id = value.split(',')
            model = _environment_of(record)[res_model]
            return orm_utils.browse(model, int(res_id)).first()
        return None

    def convert_to_read(self, value, record, use_display_name=True):
        """≙ ``:48-49``."""
        return f'{_model_name_of(value)},{value.pk}' if value else False

    def convert_to_export(self, value, record):
        """≙ ``:51-52``."""
        return value.display_name if value else ''

    def convert_to_display_name(self, value, record):
        """≙ ``:54-55``."""
        return value.display_name if value else False


class Many2oneReference(models.IntegerField):
    """≙ ``class Many2oneReference(Integer)`` (``fields_reference.py:58``).

    *"Contrary to Reference fields, the model has to be specified in a Char
    field, whose name has to be specified in the ``model_field`` attribute
    for the current Many2oneReference field."*
    """

    type = 'many2one_reference'
    #: El campo ``Char`` que guarda el nombre del modelo (``:73``).
    model_field = None
    aggregator = None

    def __init__(self, *args, model_field=None, **kwargs):
        super().__init__(*args, **kwargs)
        if model_field is not None:
            self.model_field = model_field

    @property
    def _related_model_field(self):
        """≙ ``property(attrgetter('model_field'))`` (``:77``)."""
        return self.model_field

    @property
    def _description_model_field(self):
        """≙ ``:79``."""
        return self.model_field

    def deconstruct(self):
        """La ruta de ``IntegerField``: la columna es un entero, sin más."""
        name, _path, args, kwargs = super().deconstruct()
        return name, 'django.db.models.IntegerField', args, kwargs

    def convert_to_cache(self, value, record, validate=True):
        """≙ ``:83-87``. Formato de caché: el id o ``None``."""
        if isinstance(value, models.Model):
            value = value.pk
        return super().convert_to_cache(value, record, validate)
