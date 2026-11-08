"""Campo de selección — fiel a ``odoo/orm/fields_selection.py`` (Odoo 19).

``fields.Selection`` es un **despachador** de ``company_dependent`` (tarea
#129). El tipo está en ``COMPANY_DEPENDENT_FIELDS``
(``odoo19c: odoo/orm/fields.py:42-44``) y es el segundo más usado de la
referencia con **7** declaraciones, entre ellas
``analytic/models/analytic_plan.py:77`` (``default_applicability``), que es el
primero cableado aquí.

Sin ``company_dependent`` el despachador construye :class:`SelectionField`,
la clase de la referencia (``odoo19c: odoo/orm/fields_selection.py:20-241``)
sobre ``models.CharField``: la columna sigue siendo ``varchar``. Con
``company_dependent=True`` el campo pasa a ser ``jsonb`` y lo construye
:class:`~orm.fields_company_dependent.CompanyDependent`, que descarta
``choices`` y ``max_length`` porque lo que la columna guarda es el mapa.

Lo que la clase porta, y lo que no
==================================

Porta la firma ``Selection(selection, string)`` —la lista posicional era hasta
ahora ``verbose_name`` de Django y el campo quedaba sin enumeración—, los tres
atributos de clase, la validación de ``convert_to_cache`` y
``convert_to_column``,
``get_values``, ``_description_selection``, ``_default_group_expand``,
``convert_to_export`` y la selección del destino en ``setup_related``.

``choices=`` de Django sigue siendo una forma válida de declarar la lista: es
la de 253 de los 260 sitios de declaración del árbol, y la clase la lee como
``selection``. Ninguna ruta copia la lista a dos sitios: ``selection`` y
``_selection`` se derivan de lo declarado al consultarse.

Divergencias declaradas:

- ``_column_type`` es el de ``CharField`` —``('varchar', pg_varchar(size))``—
  y no ``('varchar', pg_varchar())``: la columna real lleva el ``max_length``
  que cada declaración fija, y declarar otra cosa mentiría sobre la base.
- ``validate`` no es un ``bool`` de clase sino un descriptor: Django ya usa
  ese nombre para el método que ``full_clean`` llama
  (:class:`_ValidateSwitch`).
- ``deconstruct`` devuelve la ruta de ``CharField``. Medido el 2026-11-05: con
  la ruta propia, ``makemigrations --dry-run`` reescribía **254** campos sin
  ningún cambio de columna; con la de ``CharField``, **0**.
- La fusión de ``selection_add`` sobre los campos de las clases base
  (``:93-177``) no vive aquí: este stack no tiene ``_base_fields__`` por
  campo, y la ampliación por herencia la resuelve ``extend_model``
  (``orm/model_classes.py``).
- ``_selection_modules`` (``:179-197``) no recorre redefiniciones: lee la
  declaración base y las ampliaciones que ``extend_model`` anota con su
  addon (:func:`orm.model_classes.calling_module`).
"""

from django.db import models

#: Módulo, no nombre: ``orm.fields`` importa este archivo antes de declarar
#: ``determine``, así que el nombre se resuelve al llamar.
import orm.fields as orm_fields
from orm.fields_company_dependent import make_dispatcher

__all__ = ['Selection', 'SelectionField']

#: La ruta que ``deconstruct`` publica: la columna no cambia de tipo.
_CHARFIELD_PATH = 'django.db.models.CharField'


class _BoundValidate:
    """``field.validate`` leído desde una instancia: bandera y método."""

    __slots__ = ('_field',)

    def __init__(self, field):
        self._field = field

    def __bool__(self):
        return self._field.__dict__.get('_validate_flag', True)

    def __call__(self, value, model_instance):
        return models.CharField.validate(self._field, value, model_instance)


class _ValidateSwitch:
    """``validate`` — dos contratos con el mismo nombre.

    La fuente lo declara bandera de clase (``validate: bool = True``,
    ``odoo19c: fields_selection.py:65``) y lo lee con ``if self.validate``.
    Django lo declara método —``Field.validate(value, model_instance)``— y
    ``full_clean`` lo llama. Un atributo llano rompe a Django (medido: 11
    casos de la suite con ``'bool' object is not callable``); un método deja
    la bandera siempre verdadera. El descriptor devuelve un objeto que responde
    a los dos: su verdad es la bandera y llamarlo es el método de Django.
    Asignar ``field.validate = False`` cambia sólo la bandera.
    """

    def __bool__(self):
        return True

    def __get__(self, field, owner=None):
        if field is None:
            return self
        return _BoundValidate(field)

    def __set__(self, field, value):
        field.__dict__['_validate_flag'] = bool(value)


class SelectionField(models.CharField):
    """≙ ``class Selection(Field)`` (``odoo19c: fields_selection.py:20``).

    ``selection`` es una lista de pares ``(valor, etiqueta)``, una función que
    recibe el modelo, o el nombre de un método del modelo. Sólo la lista
    permite validar al escribir: con las otras dos formas la enumeración se
    conoce al consultarla.
    """

    type = 'selection'
    #: Si el valor se comprueba contra la lista al escribir (``:65``); ver
    #: :class:`_ValidateSwitch` por qué no es un ``bool`` llano.
    validate = _ValidateSwitch()
    #: ``{valor: política}`` al retirar un valor (``:66``); lo puebla la
    #: ampliación por herencia, nunca la declaración base.
    ondelete = None

    def __init__(self, selection=None, string=None, **kwargs):
        if string is not None:
            kwargs.setdefault('verbose_name', string)
        if isinstance(selection, tuple):
            selection = list(selection)
        if isinstance(selection, list):
            kwargs.setdefault('choices', selection)
        elif selection is not None and not (
                callable(selection) or isinstance(selection, str)):
            raise ValueError(
                f'selection={selection!r} debe ser una lista, un invocable o '
                'el nombre de un método')
        super().__init__(**kwargs)
        self._declared_selection = selection

    @property
    def selection(self):
        """Lo declarado; sin ``selection``, los ``choices`` de Django."""
        if self._declared_selection is not None:
            return self._declared_selection
        if self.choices is not None:
            return list(self.flatchoices)
        return None

    @selection.setter
    def selection(self, value):
        self._declared_selection = value

    @property
    def _selection(self):
        """≙ ``self._selection`` (``:71``): el ``dict`` de la lista, o
        ``None`` cuando la selección se calcula."""
        selection = self.selection
        return dict(selection) if isinstance(selection, list) else None

    def clone(self):
        """``Field.clone`` de Django reconstruye desde ``deconstruct``, que
        no lleva una selección calculada; se le devuelve aquí."""
        field = super().clone()
        field._declared_selection = self._declared_selection
        return field

    def deconstruct(self):
        name, _path, args, kwargs = super().deconstruct()
        return name, _CHARFIELD_PATH, args, kwargs

    def setup_related(self, model):
        """≙ ``:79-84``: la selección de un ``related`` se calcula sobre el
        campo de destino."""
        super().setup_related(model)
        field = self.related_field
        self._declared_selection = (
            lambda model: field._description_selection(model.env))

    def _description_selection(self, env):
        """≙ ``:199-210``: los pares, con la etiqueta traducida al idioma
        del contexto."""
        selection = self.selection
        if isinstance(selection, str) or callable(selection):
            selection = orm_fields.determine(selection, env[self.model_name])
            return [(str(key), str(label)) for key, label in selection]
        translations = dict(env['ir.model.fields'].get_field_selection(
            self.model_name, self.name))
        return [(key, translations.get(key, label))
                for key, label in selection]

    def _default_group_expand(self, records, groups, domain):
        """≙ ``:212-214``: un grupo por opción, en el orden declarado."""
        return self.get_values(records.env)

    def get_values(self, env):
        """≙ ``:216-221``: los valores posibles."""
        selection = self.selection
        if isinstance(selection, str) or callable(selection):
            selection = orm_fields.determine(
                selection, env[self.model_name].with_context(lang=None))
        return [value for value, _label in selection]

    def convert_to_column(self, value, record, values=None, validate=True):
        """≙ ``:223-226``. La base es ``Field.convert_to_column`` y no la de
        ``Char``, que volvería a pasar por ``convert_to_cache``."""
        if validate and self.validate:
            value = self.convert_to_cache(value, record)
        return models.Field.convert_to_column(
            self, value, record, values, validate)

    def convert_to_cache(self, value, record, validate=True):
        """≙ ``:228-236``."""
        if value == '' and not self.null:
            # Divergencia declarada: la fuente guarda el vacío como ``NULL``
            # (``False``); aquí 34 declaraciones (censo AST del 2026-11-05)
            # fijan ``default=''`` sobre una columna ``NOT NULL``, la
            # convención de Django para texto. El vacío se conserva, como ya
            # hacía ``Char`` en este stack.
            return ''
        selection = self._selection
        if not validate or selection is None:
            return value or None
        if value in selection:
            return value
        if not value:
            return None
        raise ValueError(f'Wrong value for {self}: {value!r}')

    def convert_to_export(self, value, record):
        """≙ ``:238-241``: la etiqueta de la opción, o el valor."""
        for item in self._description_selection(record.env):
            if item[0] == value:
                return item[1]
        return value or ''

    def _selection_modules(self, model):
        """≙ ``_selection_modules``.

        Fuente: ``odoo19c: odoo/orm/fields_selection.py:179-197``.

        «Return a mapping from selection values to modules defining each
        value.» La fuente recorre las redefiniciones del campo por la MRO;
        aquí la declaración base es el campo y cada ``selection_add`` es una
        ampliación en sitio que
        :func:`~orm.model_classes.extend_selection_choices` anota con su
        addon. El módulo de la declaración es la aplicación del modelo que la
        contiene, el ``_module`` de su clase allá. Un singleton ``(valor,)``
        sólo ancla el orden y no aporta módulo (``:194-196``).
        """
        if not isinstance(self.selection, list):
            return {}
        value_modules = {}
        declared = vars(self).get('_selection_declared')
        if declared is None:
            declared = [value for value, _label in self.selection]
        module = self.model._meta.app_label
        for value in declared:
            value_modules.setdefault(value, set()).add(module)
        for module, extra in vars(self).get('_selection_extensions', ()):
            for value_label in extra:
                if len(value_label) > 1:
                    value_modules.setdefault(value_label[0], set()).add(module)
        return value_modules


Selection = make_dispatcher('Selection', 'selection', SelectionField)
