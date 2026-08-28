"""Campos de propiedades dinámicas — fiel a ``odoo/orm/fields_properties.py``.

Odoo ``Properties``/``PropertiesDefinition`` = propiedades dinámicas por registro
(esquema definido en un padre). En Django el equivalente natural es
``JSONField`` (esquema validado en el serializer/clean). Alias de lectura.

``property_to_sql`` — extraer UNA propiedad del JSON
====================================================

``Field.property_to_sql`` (``orm/fields.py``) rechaza por defecto: sólo un
campo que contenga sub-campos sabe sacar uno. ``Properties`` es ese campo, y
allá lo sobreescribe (``odoo19c: odoo/orm/fields_properties.py:674-676``) con
tres líneas: valida el nombre y emite ``(campo -> 'nombre')``.

Aquí ``Properties`` **es** ``models.JSONField``, así que el método se adjunta a
esa clase — misma divergencia de forma que ``orm/fields.py`` declara para
``to_sql``: la clase es de Django y no es nuestra para declararla.

Consecuencia que conviene saber, y es una diferencia real con la fuente: allá
sólo ``Properties`` lo tiene; aquí el método se adjunta a ``JSONField``, así que
un ``fields.Json`` también responde a ``property_to_sql``. Es un
ensanchamiento, no un defecto: el operador ``->`` de PostgreSQL funciona igual
sobre cualquier ``jsonb``, y ``_field_to_sql`` sólo lo invoca cuando la
expresión trae un punto.

``Properties`` ya NO es un alias
================================

Desde el porte del cargador de datos (tarea #115) es una **clase** con la
tríada de definición de la fuente; ``PropertiesDefinition`` sigue siendo el
alias, porque su papel —guardar el esquema en el contenedor— no necesita
todavía nada más que la columna. Ver el docstring de la clase.
"""
import copy
import json
import uuid

from django.db import models

from orm.environments import sudo
from orm.utils import regex_alphanumeric
from tools.misc import has_list_types, is_list_of
from tools.sql import SQL

__all__ = ['Properties', 'PropertiesDefinition', 'check_property_field_value_name']

#: ``NoneType`` — la fuente lo importa de ``types``; aquí se deriva, que es lo
#: mismo y no añade un import por una sola cita.
_NONE_TYPE = type(None)

PropertiesDefinition = models.JSONField


class Properties(models.JSONField):
    """``fields.Properties`` — el valor por registro de un esquema del padre.

    ≙ ``odoo19c: odoo/orm/fields_properties.py`` clase ``Properties``, reducida
    a lo que este árbol consume hoy: la **identidad de tipo** y la resolución
    del esquema (``definition`` → ``definition_record`` +
    ``definition_record_field``), que es lo que ``BaseModel._clean_properties``
    necesita para saber qué propiedades siguen existiendo.

    Hasta ``api@0ad922eb`` esto era ``Properties = models.JSONField``, un alias
    pelado. El alias bastaba para la columna —``jsonb`` en los dos— y **no**
    para el cargador de datos: ``_load_records_create`` termina con
    ``records._clean_properties()``, y limpiar exige leer la definición del
    contenedor. Sin la clase, esa mitad del cargador no tenía a quién
    preguntar.

    Qué se porta y qué no
    =====================

    Se porta lo que el cargador ejerce: la tríada de definición, su derivación
    desde ``definition='campo.definicion'``, ``_get_properties_definition``, y
    la conversión de las tres formas de entrada a la forma de almacenamiento
    (``convert_to_cache`` con ``_list_to_dict``, ``_remove_display_name`` y
    ``_add_missing_names``), más su inversa ``_dict_to_list``.

    **NO** se porta todavía el resto del archivo de la fuente —el
    ``compute``/``inverse`` que materializa el campo en lectura, la validación
    de la definición, el saneo HTML por propiedad y la superficie web—. No es
    una divergencia declarada en lugar de portar: es **porte por tramos con
    sucesor registrado**, tarea **#130**, y el tramo que falta no lo toca
    ningún consumidor de este árbol hoy (medido: ninguna de las 11
    declaraciones de ``fields.Properties``/``PropertiesDefinition`` pasa
    ``definition=``, que es la segunda mitad del mismo sucesor).

    El discriminador de tipo es ``isinstance``, no un atributo ``type``
    ====================================================================

    La fuente declara ``type = 'properties'`` y sus consumidores preguntan
    ``field.type != 'properties'``. Aquí el discriminador es
    ``isinstance(field, Properties)``, que es la forma que este árbol ya fijó
    para el mismo problema en ``fields_textual.Html`` (H-API-700): un
    ``models.Field`` de Django no lleva atributo ``type``, y añadírselo
    duplicaría en una cadena lo que la clase ya dice. La clave de tipo que
    ``ir.model.fields`` refleja se sigue derivando del nombre exportado
    (``ir_model._type_key``), no de un atributo — sin cambio.

    La columna no cambia
    ====================

    Como ``Html``, :meth:`deconstruct` devuelve la ruta de
    ``django.db.models.JSONField``: las migraciones generadas cuando esto era
    un alias siguen siendo idénticas y ``makemigrations --check`` queda limpio.
    """

    #: ``'campo_al_contenedor.campo_de_definicion'``, tal cual la fuente.
    definition = None
    #: El campo de ESTE modelo que apunta al contenedor.
    definition_record = None
    #: El campo del contenedor que guarda la definición.
    definition_record_field = None

    #: ≙ ``ALLOWED_TYPES`` (``odoo19c: fields_properties.py``) — los tipos que
    #: una propiedad puede declarar. Se porta verbatim.
    ALLOWED_TYPES = (
        # standard types
        'boolean', 'integer', 'float', 'text', 'char', 'html', 'date',
        'datetime', 'monetary',
        # relational like types
        'many2one', 'many2many', 'selection', 'tags',
        # UI types
        'separator',
    )

    def __init__(self, *args, definition=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.definition = definition
        self._setup_definition_attrs()

    def _setup_definition_attrs(self):
        """≙ ``_setup_definition_attrs`` — parte ``definition`` en sus dos mitades.

        La fuente lo corre desde ``_setup_attrs__``, que su ORM invoca al
        construir la clase de modelo. Aquí no hay esa etapa —Django construye
        el campo en el ``__init__``—, así que se llama desde ahí: el momento es
        distinto, el resultado es el mismo.

        La rama de ``compute``/``_depends`` de la fuente **no** se porta en
        este tramo (tarea #130): aquí el campo es una columna real y su lectura
        no se recalcula desde el contenedor.
        """
        if not self.definition:
            return
        assert self.definition.count('.') == 1, (
            f"definition debe ser 'campo.definicion', no {self.definition!r}")
        self.definition_record, self.definition_record_field = (
            self.definition.rsplit('.', 1))

    def deconstruct(self):
        """Deconstruye como ``django.db.models.JSONField`` — ver el docstring.

        ``definition`` se descarta a propósito: no es un atributo de columna
        sino de resolución en runtime, así que meterlo en la migración pediría
        un ``AlterField`` por cada campo que lo declare sin que la tabla
        cambie.
        """
        name, _path, args, kwargs = super().deconstruct()
        kwargs.pop('definition', None)
        return name, 'django.db.models.JSONField', args, kwargs

    def _get_properties_definition(self, record):
        """≙ ``_get_properties_definition`` (``odoo19c: :401-405``).

        «Return the properties definition of the given record.»

        Devuelve ``None`` cuando el registro no tiene contenedor —igual que la
        fuente, cuyo ``if container:`` deja caer el ``return``— y cuando este
        campo no declara ``definition``, que es el estado de las once
        declaraciones del árbol hoy (tarea #130).

        La elevación de la fuente (``container.sudo()``) se porta con el mismo
        sentido: la definición del contenedor se lee **siempre**, aunque el
        actor no tenga permiso sobre él; lo contrario dejaría a un usuario sin
        acceso al padre viendo propiedades que ya no existen.
        """
        if not self.definition_record:
            return None
        container = getattr(record, self.definition_record, None)
        if not container:
            return None
        with sudo():
            return getattr(container, self.definition_record_field, None)

    # -- Conversión entre las formas del valor -------------------------------

    def convert_to_cache(self, value, record, validate=True):
        """≙ ``convert_to_cache`` (``odoo19c: :140-165``).

        «any format -> cache format {name: value} or None». Las cuatro formas
        de entrada de la fuente se portan: vacío, ``dict`` (copia profunda,
        *"avoid accidental side effects from shared mutable data"*), ``str``
        (JSON) y ``list`` (la definición completa que manda el cliente, que se
        reduce a ``{nombre: valor}``).

        La rama ``Property`` de la fuente **no** aplica: ese envoltorio es de
        su capa de lectura, que es el tramo no portado (tarea #130).

        DIVERGENCIA DECLARADA en ``validate``: la fuente sanea con
        ``html_sanitize`` las propiedades cuyo nombre acaba en ``_html``. Aquí
        el saneo de HTML vive en la capa UI (``dompurify``) —la misma decisión
        que ``fields_textual.Html`` ya declara para el campo entero—, así que
        la bandera se acepta y no dispara saneo. No es un hueco silencioso: es
        la misma frontera, aplicada al mismo tipo de dato.
        """
        if not value:
            return None
        if isinstance(value, dict):
            return copy.deepcopy(value)
        if isinstance(value, str):
            value = json.loads(value)
            if not isinstance(value, dict):
                raise ValueError(f"Wrong property value {value!r}")
            return value
        if isinstance(value, list):
            self._remove_display_name(value)
            return self._list_to_dict(value)
        raise TypeError(f"Wrong property type {type(value)!r}")

    @classmethod
    def _add_missing_names(cls, values_list):
        """≙ ``_add_missing_names`` — «Generate new properties name if needed».

        Modifica ``values_list`` en el sitio, como la fuente. El nombre son los
        primeros 64 bits de un UUID4, verbatim.
        """
        for definition in values_list:
            if definition.get('definition_changed') and not definition.get('name'):
                # keep only the first 64 bits
                definition['name'] = str(uuid.uuid4()).replace('-', '')[:16]

    @classmethod
    def _remove_display_name(cls, values_list, value_key='value'):
        """≙ ``_remove_display_name`` — quita la etiqueta que manda el cliente.

        «- many2one: (35, 'Bob') -> 35 · many2many: [(35, 'Bob'), (36, 'Alice')]
        -> [35, 36]». Modifica ``values_list`` en el sitio.
        """
        for property_definition in values_list:
            if not isinstance(property_definition, dict) or not property_definition.get('name'):
                continue

            property_value = property_definition.get(value_key)
            if not property_value:
                continue

            property_type = property_definition.get('type')

            if property_type == 'many2one' and has_list_types(
                    property_value, [int, (str, _NONE_TYPE)]):
                property_definition[value_key] = property_value[0]

            elif property_type == 'many2many':
                if is_list_of(property_value, (list, tuple)):
                    # [(35, 'Admin'), (36, 'Demo')] -> [35, 36]
                    property_definition[value_key] = [
                        many2many_value[0]
                        for many2many_value in property_value
                    ]

    @classmethod
    def _list_to_dict(cls, values_list):
        """≙ ``_list_to_dict`` — la definición completa reducida a ``{nombre: valor}``.

        «To not repeat data in database, we only store the value of each
        property on the child. The properties definition is stored on the
        container.»

        Las tres comprobaciones de forma de la fuente se portan enteras: la
        lista tiene que ser de diccionarios, un ``many2many`` tiene que traer
        enteros y un ``many2one`` un entero. Son las que impiden que llegue a
        la columna un valor que la lectura no sabrá deshacer.
        """
        if not is_list_of(values_list, dict):
            raise ValueError(f'Wrong properties value {values_list!r}')

        cls._add_missing_names(values_list)

        dict_value = {}
        for property_definition in values_list:
            property_value = property_definition.get('value')
            property_type = property_definition.get('type')
            property_model = property_definition.get('comodel')
            if property_value is None:
                # Do not store None key
                continue

            if property_type not in ('integer', 'float') or property_value != 0:
                property_value = property_value or False
            if property_type in ('many2one', 'many2many') and property_model and property_value:
                # check that value are correct before storing them in database
                if property_type == 'many2many' and property_value and not is_list_of(property_value, int):
                    raise ValueError(f"Wrong many2many value {property_value!r}")

                if property_type == 'many2one' and not isinstance(property_value, int):
                    raise ValueError(f"Wrong many2one value {property_value!r}")

            dict_value[property_definition['name']] = property_value

        return dict_value

    @classmethod
    def _dict_to_list(cls, values_dict, properties_definition):
        """≙ ``_dict_to_list`` — la inversa: el valor del hijo sobre la definición.

        «Ignore every values in the child that is not defined on the
        container» — que es exactamente el criterio con que
        ``_clean_properties`` decide qué sobra.
        """
        if not is_list_of(properties_definition, dict):
            raise ValueError(f'Wrong properties value {properties_definition!r}')

        values_list = copy.deepcopy(properties_definition)
        for property_definition in values_list:
            if property_definition['name'] in values_dict:
                property_definition['value'] = values_dict[property_definition['name']]
            else:
                property_definition.pop('value', None)
        return values_list


def check_property_field_value_name(property_name):
    """≙ ``check_property_field_value_name`` (``odoo19c: :27-29``).

    El nombre de una propiedad va **interpolado en el SQL**, así que se acota
    antes: hasta 512 caracteres y sólo minúsculas, dígitos y guion bajo.
    """
    if not (0 < len(property_name) <= 512) or not regex_alphanumeric.match(property_name):
        raise ValueError(f"Wrong property field value name {property_name!r}.")


def _properties_property_to_sql(self, field_sql, property_name, model, alias, query):
    """``property_to_sql`` — ≙ ``Properties.property_to_sql`` (``:674-676``)."""
    check_property_field_value_name(property_name)
    return SQL("(%s -> %s)", field_sql, property_name)


models.JSONField.property_to_sql = _properties_property_to_sql
