"""Campos del ORM — agregador, fiel a ``odoo/orm/fields.py`` (Odoo 19).

En Odoo 19 los campos se definen por **categoría** en
``odoo/orm/fields_{textual,numeric,temporal,selection,relational,binary,misc,
reference,properties}.py`` y se agregan hacia la superficie pública. Aquí se
replica el split (monolito modular: un archivo por categoría) y este módulo los
**agrega**; ``src/fields/__init__.py`` (≙ ``odoo/fields/__init__.py``) re-exporta
de aquí + ``Command``.

Cada nombre mapea el *nombre* de campo de Odoo → la clase de Django; la *firma*
difiere (alias de lectura con parámetros Django).

Además: ``falsy_value`` y ``condition_to_q``
============================================

La fuente declara en **este mismo archivo** dos piezas que no son un campo sino
el contrato de un campo frente a un dominio:

- ``Field.falsy_value`` (``odoo19c: odoo/orm/fields.py:254``) — el valor que
  cuenta como *no establecido* para las comparaciones.
- ``Field.condition_to_sql`` (``:1249``) — cómo un ``(campo, operador, valor)``
  se convierte en la cláusula que va al ``WHERE``.

Aquí se portan como **funciones sobre el campo de Django**, no como atributos y
métodos de clase. La divergencia es forzada y se declara: nuestros campos NO son
clases propias sino **alias de las de Django** (``Integer = models.IntegerField``,
``fields_numeric.py:11``), así que no hay clase donde colgar ni el atributo ni el
método sin subclasar los veinte campos de Django — un cambio con impacto en
migraciones que ninguna necesidad de hoy justifica.

El **sitio** sí es el de la fuente: los dos símbolos viven donde la referencia
los declara, que es lo que ``atributos-de-clase-de-modelo.md`` exige en su
segunda cláusula.

El campo no persistido es otra categoría del mismo split
========================================================

``orm/fields_nonstored.py`` construye el ``store=False`` de la referencia: un
campo que se calcula al leerlo y nunca escribe columna. Medido: **66**
ocurrencias de ``store`` en ``odoo19c: odoo/orm/fields.py`` — el mecanismo vive
allá **dentro de este mismo archivo**, sin archivo propio.

Aquí es un archivo aparte por la misma razón que las nueve categorías de
arriba: este módulo **agrega**, no define. No se re-exporta desde este
agregador porque no es una clase de campo de Django y no puede aparecer en
``_meta.get_fields()``; se importa por su nombre. Ver :ref:`h-api-855`.
"""
import collections
import itertools
import logging
import operator as operator_module
import re
import warnings
import weakref
from decimal import Decimal
from operator import attrgetter
from typing import TypeVar

from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.utils.timezone import localtime

from orm.environments import (env as get_environment, get_current_company,
                             get_transaction, sudo as elevate_privileges)
from tools.misc import OrderedSet, remove_accents
from tools.translate import _
from orm.registry import (field_computed as registry_field_computed,
                         field_depends_context, is_not_null)
from tools.sql import SQL, pg_varchar, sql_order_by_type

from orm.fields_binary import Binary, Image                    # noqa: F401
from orm.fields_misc import Boolean, Json                      # noqa: F401
from orm.fields_numeric import Float, Integer, Monetary        # noqa: F401
from orm.fields_nonstored import (                          # noqa: F401
    NonStored,
    annotate_related,
    apply_source_defaults,
)
from orm.fields_properties import (                            # noqa: F401
    Properties,
    PropertiesDefinition,
)
from orm.fields_reference import Many2oneReference, Reference  # noqa: F401
from orm.fields_relational import Many2many, Many2one, One2many  # noqa: F401
from orm.fields_selection import Selection                     # noqa: F401
from orm.fields_temporal import Date, Datetime                 # noqa: F401
from orm.fields_textual import Char, Html, Text                # noqa: F401
from orm.utils import COLLECTION_TYPES, record_ids

#: El **registro de tipos de campo**, no la lista de exportables del módulo.
#:
#: ``base.models.ir_model`` lo consume literalmente: deriva ``FIELD_TYPES`` de
#: esta secuencia (``ir_model.py:147,164``) y con ella puebla las opciones de
#: ``IrModelFields.ttype``. Un nombre que no sea una clase de campo entra al
#: vocabulario de ``ttype`` y ensucia el modelo — y lo hace **en silencio**,
#: porque la única señal es una migración inesperada.
#:
#: Por eso ``falsy_value``, ``condition_to_q``, ``SqlLike`` y ``SqlILike`` NO
#: están aquí: son funciones y ``Lookup``, no tipos de campo. Siguen siendo
#: importables por nombre —que es como los consume ``orm.domains``— porque
#: ``__all__`` sólo gobierna ``from orm.fields import *``. Ver
#: :ref:`h-api-616`.
__all__ = [
    'Char', 'Text', 'Html', 'Integer', 'Float', 'Monetary', 'Date', 'Datetime',
    'Selection', 'Many2one', 'One2many', 'Many2many', 'Binary', 'Image',
    'Boolean', 'Json', 'Reference', 'Many2oneReference', 'Properties',
    'PropertiesDefinition',
]


# === El LIKE crudo que Django no expone ====================================
#
# La referencia emite el patrón **tal cual lo escribió el dominio**:
# ``need_wildcard = '=' not in operator`` y, si hace falta, ``f"%{value}%"``
# (``odoo19c: odoo/orm/fields.py:1319-1325``). Los cuatro operadores ``=like``
# / ``not =like`` / ``=ilike`` / ``not =ilike`` existen justamente para NO
# añadir comodines: el patrón lo pone quien escribe el dominio.
#
# Django no tiene con qué expresarlo. ``__contains`` envuelve en ``%…%`` y
# **escapa** ``%`` y ``_`` del valor (``django/db/models/lookups.py``), así que
# un ``=like`` con comodín propio saldría literal. Por eso se construyen los dos
# lookups —el camino 1 de ``porte-completo-no-parcial.md``: API pública del
# stack antes que rodeo.
#
# El ``::text`` replica el ``sql_left = sql_field if self.is_text else
# SQL("%s::text", sql_field)`` de la fuente (``:1317``): un ``LIKE`` sobre una
# columna no textual necesita el cast en PostgreSQL.


class SqlLike(models.Lookup):
    """``LIKE`` sin envoltura ni escape — el patrón lo pone el dominio."""

    lookup_name = 'sql_like'

    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        return f'{lhs}::text LIKE {rhs}', (*lhs_params, *rhs_params)


class SqlILike(models.Lookup):
    """``ILIKE`` sin envoltura ni escape — hermano insensible a mayúsculas.

    **Divergencia declarada:** la fuente envuelve los dos lados con
    ``registry.unaccent`` (``:1327-1329``), así que su ``ilike`` es además
    insensible a acentos. Aquí no: el ``unaccent`` real es la tarea **#98**
    (T-012 de la migración de motor), y hasta que exista este lookup compara
    sin normalizar acentos.
    """

    lookup_name = 'sql_ilike'

    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        return f'{lhs}::text ILIKE {rhs}', (*lhs_params, *rhs_params)


models.Field.register_lookup(SqlLike)
models.Field.register_lookup(SqlILike)


# === falsy_value ============================================================
#
# La fuente lo declara por clase de campo. Medido en ``odoo19c``:
#
#   Boolean.falsy_value = False   (fields_misc.py:26)
#   Integer.falsy_value = 0       (fields_numeric.py:21)
#   Float.falsy_value = 0.0       (fields_numeric.py:111)
#   Monetary.falsy_value = 0.0    (fields_numeric.py:197)
#   BaseString.falsy_value = ''   (fields_textual.py:38 — Char, Text, Html)
#
# El resto lo hereda de ``Field.falsy_value = None`` (``fields.py:254``), que
# significa «este campo no tiene valor falsy: sólo NULL cuenta como no
# establecido». ``Json`` entra ahí, y es correcto: la fuente no le asigna
# ninguno.
#
# La clave primaria es la fila que NO se deduce de la tabla de arriba: en
# Django ``BigAutoField`` hereda de ``IntegerField``, así que sin declararla
# valdría ``0``. La fuente dice lo contrario — ``class Id(Field)``
# (``odoo19c: fields_misc.py:89``) **no** es subclase de ``Integer``, y por
# tanto hereda ``Field.falsy_value = None``. Ahí descansa una conducta
# observable: ``_optimize_in_required`` sólo retira el ``False`` de un ``in``
# cuando el campo no tiene valor falsy, y en la fuente
# ``('id', 'in', [1, False])`` sí lo retira.
#
# ``EmailField``/``SlugField``/``URLField`` heredan de ``CharField`` (falsy
# ``''``) por MRO, así que no hace falta nombrarlas.

#: La correspondencia entre la clase de campo de la FUENTE y la de Django.
#:
#: Es conocimiento de **porte**, no un detalle de ``falsy_value``: dice que el
#: ``Boolean`` de allá es ``BooleanField`` aquí, y que su ``Id`` son las tres
#: clases concretas de clave primaria. Vive aquí —y no en el gate que lo
#: consume— porque una segunda copia sería la segunda fuente de verdad que
#: `calibration-verified-numbers.md` prohíbe: el día que se porte un tipo
#: nuevo, el mapa se actualiza en un sitio.
#:
#: Lo consume :data:`_FALSY_VALUE_TARGET_CLASSES` y el gate
#: ``scripts/check_field_class_attributes.py``, que compara lo que cada clase
#: de la fuente declara contra lo que la de Django responde.
#:
#: ``AutoField`` **no** basta: en Django ``BigAutoField`` y ``SmallAutoField``
#: no lo tienen en su MRO —su cadena es ``BigAutoField → AutoFieldMixin →
#: BigIntegerField → IntegerField``— y ``AutoFieldMixin`` no se exporta en
#: ``django.db.models``. Lo que los hace pasar por ``AutoField`` es el
#: ``__subclasscheck__`` de su metaclase, que gobierna ``isinstance`` y **no**
#: la búsqueda de atributos. Medido: con ``IntegerField.x = 0`` y
#: ``AutoField.x = None``, ``BigAutoField.x`` vale ``0``.
#:
#: Por eso las tres clases concretas de clave primaria se nombran una a una.
REFERENCE_CLASS_TO_DJANGO = {
    'Boolean': (models.BooleanField,),
    'Integer': (models.IntegerField,),
    'Float': (models.FloatField,),
    'Monetary': (models.DecimalField,),
    'BaseString': (models.CharField, models.TextField),
    'Id': (models.AutoField, models.BigAutoField, models.SmallAutoField),
    'Json': (models.JSONField,),
    'Binary': (models.BinaryField,),
    'Date': (models.DateField,),
    'Datetime': (models.DateTimeField,),
    'Selection': (models.CharField,),
    'Char': (models.CharField,),
    'Text': (models.TextField,),
    'Html': (Html,),
    '_Relational': (models.ForeignKey, models.ManyToManyField),
    'Many2one': (models.ForeignKey,),
    'Many2many': (models.ManyToManyField,),
    'One2many': (One2many,),
    'Properties': (Properties,),
    'PropertiesDefinition': (PropertiesDefinition,),
    'Many2oneReference': (Many2oneReference,),
}

#: Lo que cada clase concreta de la fuente declara, y que su clase de Django
#: tiene que responder.
#:
#: Las claves salen de :data:`REFERENCE_CLASS_TO_DJANGO`, no de una segunda
#: lista: si mañana ``BaseString`` gana una tercera clase de destino, ésta la
#: hereda sin que nadie se acuerde. Los **valores** sí se declaran aquí — son
#: la declaración portada, y leerlos de la referencia en tiempo de import
#: convertiría un árbol de consulta en una dependencia de arranque. Quien
#: comprueba que coinciden con la fuente es
#: ``scripts/check_field_class_attributes.py``, que la lee por AST.
#:
#: Cada entrada cita la línea de su declaración allá. Lo que **no** cabe aquí
#: —porque la fuente lo declara como ``property`` y depende de la instancia—
#: se instala más abajo: ``Char._column_type`` y ``Float._column_type``.
_CLASS_ATTRIBUTE_OVERRIDES = {
    #: ``Id`` (``fields_misc.py:89-95``). Es el bloque que más mentía: las tres
    #: clases de clave automática de Django cuelgan del ``Field`` base, así que
    #: heredaban su defecto entero. ``AutoFieldMeta.__subclasscheck__`` hace
    #: que ``issubclass(BigAutoField, AutoField)`` sea cierto sin que
    #: ``AutoField`` esté en el MRO; la **resolución de atributo** sigue el
    #: MRO, no la metaclase, así que hay que colgarlo de las tres.
    #:
    #: ``column_type`` va aquí, no ``_column_type``: la fuente lo declara en el
    #: atributo público, saltándose la ``property`` de ``Field``. Un atributo
    #: de clase en la subclase gana a una ``property`` de la clase base porque
    #: la búsqueda para en la primera clase del MRO que lo tenga.
    'Id': {
        'falsy_value': None,
        #: ``aggregator`` NO lo declara ``Id`` allá: lo hereda de ``Field``, que
        #: dice ``None``. Aquí hay que decirlo **explícitamente** porque las
        #: tres clases de clave automática de Django descienden de
        #: ``IntegerField``, que sí recibe el ``'sum'`` de ``Integer``. La
        #: fuente no tiene ese problema: su ``Id`` cuelga de ``Field``, no de
        #: ``Integer``. Es la misma diferencia de árbol que obligó a declarar
        #: ``falsy_value: None`` aquí arriba, y la destapó el gate.
        'aggregator': None,
        'string': 'ID',
        'store': True,
        'readonly': True,
        'prefetch': False,
        'column_type': ('int4', 'int4'),
        #: ``Field._column_type = None`` (``odoo19c: odoo/orm/fields.py:259``)
        #: y ``Id`` cuelga de ``Field``: la clave primaria NO hereda el
        #: ``('int4','int4')`` de ``Integer``. Aquí sí lo heredaría —
        #: ``AutoField(IntegerField)``—, que es la misma divergencia de árbol
        #: de :ref:`h-api-970`. Quien publica el tipo de la columna de la
        #: clave es ``column_type``, la línea de arriba.
        '_column_type': None,
    },
    'Boolean': {                                   # ``fields_misc.py:24-25``
        'falsy_value': False,
        '_column_type': ('bool', 'bool'),
    },
    'Json': {                                      # ``fields_misc.py:65``
        '_column_type': ('jsonb', 'jsonb'),
    },
    'Integer': {                                   # ``fields_numeric.py:20-21``
        'falsy_value': 0,
        'aggregator': 'sum',
        '_column_type': ('int4', 'int4'),
    },
    #: ``Float`` (``fields_numeric.py:107``, ``:125-133``). El agregado es
    #: literal allá; el tipo de columna es una ``property`` que devuelve
    #: ``('numeric','numeric')`` con dígitos declarados y ``('float8','float8')``
    #: sin ellos. **Divergencia de mecanismo declarada:** en este stack la rama
    #: de dígitos es *otra clase* —``DecimalField``, que recibe la declaración
    #: de ``Monetary``—, así que ``FloatField`` sólo puede ser la otra rama. No
    #: se recorta nada: las dos ramas existen, repartidas en dos clases.
    'Float': {
        'falsy_value': 0.0,
        'aggregator': 'sum',
        '_column_type': ('float8', 'float8'),
    },
    'Monetary': {                                  # ``fields_numeric.py:196-197``
        'falsy_value': Decimal('0'),
        'aggregator': 'sum',
        '_column_type': ('numeric', 'numeric'),
    },
    'BaseString': {                                # ``fields_textual.py:33``
        'falsy_value': '',
    },
    'Text': {                                      # ``fields_textual.py:542``
        '_column_type': ('text', 'text'),
    },
    'Many2one': {                                  # ``fields_relational.py:245``
        '_column_type': ('int4', 'int4'),
    },
    'Binary': {                                    # ``fields_binary.py``
        'prefetch': False,
    },
    'Properties': {                                # ``fields_properties.py:53``
        '_column_type': ('jsonb', 'jsonb'),
        'prefetch': False,
        'readonly': False,
    },
    'PropertiesDefinition': {                      # ``fields_properties.py:850``
        '_column_type': ('jsonb', 'jsonb'),
        'readonly': False,
        'prefetch': True,
    },
    #: ``Many2oneReference`` (``fields_reference.py``) hereda de ``Integer``
    #: allá, así que su ``falsy_value`` es el ``0`` de aquél; su ``aggregator``
    #: sí lo declara propio, anulando el ``'sum'`` que heredaría. Aquí no
    #: desciende de ``IntegerField``, de modo que las dos cosas hay que
    #: decirlas: la heredada y la declarada.
    'Many2oneReference': {
        'falsy_value': 0,
        'aggregator': None,
        #: ``Many2oneReference(Integer)`` guarda el id crudo del registro
        #: apuntado, así que hereda la columna del entero. Aquí
        #: ``GenericForeignKey`` no desciende de ``IntegerField``, y sin
        #: declararlo respondía ``None``: la columna que la fuente declara
        #: desaparecía.
        '_column_type': ('int4', 'int4'),
    },
}


def install_class_attribute_overrides():
    """Instala por clase lo que la fuente declara por clase.

    El bucle de :data:`_FIELD_CLASS_ATTRIBUTES` pone el defecto de ``Field`` en
    ``models.Field`` y nada más, así que **toda** clase concreta respondía ese
    defecto. Medido antes de esta función: un ``IntegerField`` decía
    ``falsy_value=None`` donde la fuente dice ``0``; un ``AutoField`` decía
    ``readonly=False`` donde dice ``True``, y su lector ``is_editable``
    declaraba editable la clave primaria de todo modelo.

    Se llama **después** del bucle: el bucle pone el defecto y esto lo pisa
    donde la fuente lo pisa. Invertir el orden no cambia nada —son clases
    distintas— pero leerlo así deja claro cuál es el defecto y cuál la
    excepción.
    """
    for reference_name, overrides in _CLASS_ATTRIBUTE_OVERRIDES.items():
        for field_class in REFERENCE_CLASS_TO_DJANGO[reference_name]:
            for attribute, value in overrides.items():
                setattr(field_class, attribute, value)


def falsy_value(field):
    """El valor que cuenta como *no establecido* — ≙ ``Field.falsy_value``.

    Lee el **atributo**, que es donde la fuente lo declara; la función existe
    para dos cosas que el atributo no da: tolerar ``field is None`` (el caso
    del campo desconocido) y ser el punto único que el resto del ORM importa.

    Devuelve ``None`` cuando el campo no tiene ninguno, que es el defecto de la
    fuente y también lo que se responde ante un campo desconocido: es la
    hipótesis conservadora, porque ``falsy_value is None`` es lo que hace que
    ``_negate`` añada la rama ``OR campo IS NULL``.
    """
    if field is None:
        return None
    return getattr(field, 'falsy_value', None)


# El subconjunto de ``NEGATIVE_CONDITION_OPERATORS`` que la familia ``like``
# usa. La fuente lo lee de ``Domain.NEGATIVE_OPERATORS`` (``:1331``), pero
# importarlo aquí cierra un ciclo —``domains`` ya importa de este módulo—, y un
# import dentro de la función está prohibido (``no-lazy-imports.md``). Unificar
# los dos en un hogar compartido es la tarea **#380**.
_NEGATIVE_LIKE_OPERATORS = frozenset([
    'not like', 'not ilike', 'not =like', 'not =ilike',
])

#: Los nueve operadores de semántica negativa — ≙ ``NEGATIVE_CONDITION_OPERATORS``
#: (``odoo19c: odoo/orm/domains.py``). Es la misma segunda copia que
#: ``_NEGATIVE_LIKE_OPERATORS`` declara arriba y por el mismo motivo: el hogar
#: de la fuente es ``domains``, que ya importa de aquí, y un import dentro de
#: la función está prohibido. Unificar los dos en un hogar compartido es la
#: tarea **#380**; hasta entonces la copia se prueba contra la original en
#: ``tests/unit/orm/test_domains.py`` para que no puedan divergir en silencio.
NEGATIVE_CONDITION_OPERATORS = frozenset([
    'not any', 'not any!', 'not in',
    'not like', 'not ilike', 'not =like', 'not =ilike',
    '!=', '<>',
])

#: ¿El ``ilike`` ignora los acentos? — ≙ ``Registry.unaccent_python``
#: (``odoo19c: odoo/orm/registry.py:290``), que es ``remove_accents`` cuando la
#: extensión ``unaccent`` está instalada y la identidad cuando no.
#:
#: **Aquí es falso, y es una medición, no una preferencia.** El lookup
#: ``sql_ilike`` emite un ``ILIKE`` pelado (ver su docstring: el ``unaccent``
#: real es la tarea **#98**), y la extensión no está instalada — medido sobre
#: ``pg_extension``: ``pg_trgm`` y ``plpgsql``, nada más.
#:
#: La bandera existe para que las **dos** vías de compilación decidan lo mismo.
#: Sin ella el predicado en memoria encontraría «Ácme» buscando «acme» y el
#: motor no, sobre el mismo dominio — y eso lo destapó el test que las contrasta,
#: no una relectura. Cuando #98 instale la extensión, esto y ``SqlILike`` se
#: encienden juntos: son una decisión, no dos.
UNACCENT_ENABLED = False


def convert_to_display_name(field, value, record):
    """El valor de un campo, como etiqueta — ≙ ``Field.convert_to_display_name``.

    ≙ ``odoo19c: odoo/orm/fields.py:1080`` y sus cinco sobrecargas
    (``fields_reference.py:55``, ``fields_relational.py:397`` y ``:715``,
    ``fields_temporal.py:187`` y ``:291``). Es lo que ``_compute_display_name``
    aplica al campo que ``_rec_name`` nombra.

    **Divergencia de forma, declarada y heredada:** allá es un método de la
    clase del campo; aquí es una **función sobre el campo de Django**, por la
    misma razón que ``falsy_value`` y ``condition_to_q``, que ya viven en este
    archivo — nuestros campos son alias de los de Django
    (``Integer = models.IntegerField``), así que no hay clase propia donde
    colgar el método sin subclasar los veinte campos de Django. El **sitio** sí
    es el de la fuente.

    Las cinco sobrecargas se portan como despacho por clase:

    - **relacional a uno** (``Many2one``, ``Reference``) → el ``display_name``
      del registro apuntado. La fuente lo escribe igual en las dos.
    - **relacional a muchos** (``Many2many``, ``One2many``) → la fuente lanza
      ``NotImplementedError`` (``fields_relational.py:715``), y se porta
      verbatim: un ``_rec_name`` que nombre una colección no tiene etiqueta
      única, y devolver algo inventado ahí escondería el error de declaración.
    - **fecha y fecha-hora** → su representación en texto. La fuente pasa la
      fecha-hora a la zona del registro
      (``Datetime.context_timestamp``); aquí lo hace ``localtime``, que lee la
      zona activa del hilo — el mismo mecanismo que el resto del árbol usa.
    - **el resto** → ``str(value) if value else False``, el default de la
      fuente, con su ``False`` y no ``None``: es el valor que la fuente
      devuelve para un campo vacío, y ``_compute_display_name`` lo distingue.
    """
    if field is None:
        return str(value) if value else False
    if isinstance(field, (models.ManyToManyField, models.ManyToOneRel,
                          models.ManyToManyRel)):
        raise NotImplementedError(
            f'convert_to_display_name no aplica a {field!r}: una colección no '
            f'tiene etiqueta única')
    if isinstance(field, (models.ForeignKey, models.OneToOneField)):
        return display_name_of(value) if value else False
    if isinstance(field, models.DateTimeField):
        return localtime(value).strftime('%Y-%m-%d %H:%M:%S') if value else False
    if isinstance(field, models.DateField):
        return value.strftime('%Y-%m-%d') if value else False
    return str(value) if value else False


def display_name_of(record):
    """La etiqueta de un registro — ≙ ``record.display_name``.

    Existe para que :func:`convert_to_display_name` no tenga que importar
    ``orm.models``: ese módulo importa ``orm.environments``, que toca el
    registro de apps, y este archivo se carga al definir los campos. Es la
    misma causa que documenta ``adopt_access_manager``.

    Un modelo que aún no adoptó el ``display_name`` universal —los de terceros
    lo son por decisión— cae a ``str(record)``, que es el ``__str__`` de
    Django.
    """
    etiqueta = getattr(record, 'display_name', None)
    return etiqueta if etiqueta else str(record)

_INEQUALITY_LOOKUP = {'<': 'lt', '>': 'gt', '<=': 'lte', '>=': 'gte'}



def condition_to_q(field_expr, operator, value, field=None):
    """Un ``(campo, operador, valor)`` a ``Q`` — ≙ ``Field._condition_to_sql``.

    Réplica de ``odoo19c: odoo/orm/fields.py:1262-1366`` **en semántica**, no en
    forma emitida. La diferencia de forma la impone algo que hubo que medir
    antes de escribir esta función, y que corrige la premisa con la que se abrió
    la iniciativa (:ref:`h-api-614`).

    Lo que Django ya hace, medido
    ------------------------------

    La fuente construye el ``WHERE`` a mano y por eso añade la rama de nulos
    explícitamente (``(cond) OR campo IS NULL``). El compilador de Django **ya
    la añade**, con otra forma y el mismo resultado::

        ~Q(user_type__sql_like='%a%')
        -> NOT ("user_type"::text LIKE %a% AND "user_type" IS NOT NULL)

        ~Q(name__sql_like='%a%')      # name es NOT NULL
        -> NOT ("name"::text LIKE %a%)

    Es exactamente la regla de la fuente: con columna nulable la fila sin valor
    **entra**; con columna no nulable no hay nulos que considerar. Así que
    replicar el ``OR campo IS NULL`` encima sería redundante — produciría un
    ``WHERE`` más largo con idéntico conjunto de filas.

    Dónde SÍ diverge, y es al revés de lo que se creía
    --------------------------------------------------

    Dos casos, los dos porque Django es **más** incluyente que la fuente:

    1. ``not in`` con ``False`` en la colección. La fuente emite un
       ``NOT IN`` pelado, y ``NULL NOT IN (x)`` es ``NULL``: la fila sin valor
       **se descarta**, que es lo que «tiene valor y no es x» significa. El
       ``~Q`` de Django la incluiría. Se fuerza con ``isnull=False``.
    2. Las desigualdades. ``Q(campo__lt=v)`` no incluye nulos, y la fuente sí
       cuando el valor *falsy* del campo satisface la comparación
       (``accept_null_value``, ``:1341-1346``). Ahí la rama se añade a mano.

    :param field_expr: ruta de campo ya en notación Django (``a__b``).
    :param field: la instancia de campo de Django, o ``None`` si no se conoce
        el modelo. Sin campo se asume ``can_be_null=True`` y
        ``falsy_value=None``, que son los defectos de la fuente
        (``Field.falsy_value = None``; un campo está en ``not_null_fields``
        sólo si algo lo declara).

    Cómo se pregunta la nulabilidad
    --------------------------------

    ``self not in model.env.registry.not_null_fields`` allá (``:1281``), y aquí
    :func:`~orm.registry.is_not_null`, que es el mismo criterio: columna real
    de un modelo con tabla, y clave primaria o ``null=False``.

    **Decía ``bool(field.null)``**, que es el atajo que :ref:`h-api-971`
    desmontó en el otro consumidor y que aquí seguía vivo. Medido sobre el
    registro entero: **120 de 5170** campos responden distinto, y los 120 en la
    dirección peligrosa —el atajo dice «no puede ser nula» cuando sí puede—,
    de modo que la rama ``IS NULL`` se retiraba y la fila sin valor
    desaparecía del resultado.

    Las 120 son dos familias: **87** ``ManyToManyField``, que declara
    ``null=False`` sin efecto porque la nulabilidad vive en la tabla
    intermedia; y **33** en modelos ``managed=False``, donde este ORM no emite
    el DDL y por tanto no puede afirmar NOT NULL.
    """
    can_be_null = True if field is None else not is_not_null(field)
    null_value = falsy_value(field)

    # --- in / not in (igualdad) --------------------------------------------
    if operator in ('in', 'not in'):
        values = list(value) if isinstance(value, COLLECTION_TYPES) else [value]
        params = [v for v in values if v is not False and v is not None]
        null_in_condition = len(params) < len(values)
        if null_value is not None:
            if null_value in params:
                null_in_condition = True
            elif null_in_condition:
                params = [*params, null_value]

        q = None
        if params:
            q = models.Q(**{f'{field_expr}__in': params})
            if operator == 'not in':
                q = ~q

        if (operator == 'in') == null_in_condition:
            # La fuente quiere aquí la rama de nulos:
            #   campo in {val, False}  => IN vals     OR campo IS NULL
            #   campo not in {val}     => NOT IN vals OR campo IS NULL
            if operator == 'not in':
                # el ``~Q`` de Django ya la trae; con columna no nulable no
                # hace falta y tampoco la pone
                return q if q is not None else models.Q()
            if not can_be_null:
                return q if q is not None else models.Q(pk__in=[])
            q_null = models.Q(**{f'{field_expr}__isnull': True})
            return (q | q_null) if q is not None else q_null

        if operator == 'not in' and null_in_condition:
            # «tiene valor y no está entre estos» — la fila sin valor NO entra
            if not can_be_null:
                return q if q is not None else models.Q()
            q_set = models.Q(**{f'{field_expr}__isnull': False})
            return (q & q_set) if q is not None else q_set

        assert q is not None, f'falta el Q para {operator} {value!r}'
        return q

    # --- like / ilike / =like / =ilike -------------------------------------
    if operator.endswith('like'):
        need_wildcard = '=' not in operator
        pattern = f'%{value}%' if need_wildcard else str(value)
        lookup = 'sql_ilike' if operator.endswith('ilike') else 'sql_like'
        q = models.Q(**{f'{field_expr}__{lookup}': pattern})
        if operator in _NEGATIVE_LIKE_OPERATORS:
            # ``~Q`` ya emite ``NOT (cond AND campo IS NOT NULL)``, que es la
            # regla de ``:1331-1333`` con otra forma
            q = ~q
        return q

    # --- desigualdades ------------------------------------------------------
    if operator in _INEQUALITY_LOOKUP:
        accept_null_value = False
        if null_value is not None and can_be_null:
            # ≙ ``:1341-1346``: la fila sin valor entra si el propio valor
            # falsy satisface la comparación.
            accept_null_value = (
                null_value < value if operator == '<' else
                null_value > value if operator == '>' else
                null_value <= value if operator == '<=' else
                null_value >= value
            )
        q = models.Q(**{f'{field_expr}__{_INEQUALITY_LOOKUP[operator]}': value})
        if accept_null_value:
            q |= models.Q(**{f'{field_expr}__isnull': True})
        return q

    # --- any / not any ------------------------------------------------------
    if operator in ('any', 'not any', 'any!', 'not any!'):
        # La fuente resuelve el subdominio contra el comodelo y lo inyecta como
        # subselect (``:1352-1365``). Aquí el ORM hace el join por la ruta, así
        # que el caso de ruta con punto lo resuelve ``DomainCondition._to_q``
        # traduciendo ``a.b`` a ``a__b`` antes de llegar aquí. Lo que queda es
        # el ``any`` explícito sobre un Queryset o una lista de ids.
        q = models.Q(**{f'{field_expr}__in': value})
        return ~q if operator.startswith('not ') else q

    raise NotImplementedError(
        f'Operador de dominio no soportado: {(field_expr, operator, value)!r}')


# --- Generación de SQL — ≙ "SQL generation methods" de la fuente ------------
#
# ``odoo19c: odoo/orm/fields.py:1205-1247`` agrupa bajo ese encabezado los dos
# métodos con que un campo se convierte en fragmento ``SQL``. Los consume
# ``BaseModel._field_to_sql`` (``orm/models.py``), la puerta del motor de
# consultas: ``sql = field.to_sql(self, alias)``.
#
# LA DIVERGENCIA, Y ES DE FORMA — la misma que ``orm/models.py`` ya declara
# dos veces (permisos y ``_origin``): allá cuelgan de la clase ``Field``, que
# es de la referencia; aquí la clase base de todo campo es
# ``django.db.models.Field``, que **no es nuestra para declararla**. Se le
# adjuntan al importar este módulo, que es el equivalente exacto de declarar
# el método en la clase: todo campo los tiene, como allá, y el sitio de la
# llamada queda **idéntico al de la fuente**.
#
# La alternativa era una función suelta ``to_sql(field, model, alias)``, que
# obliga a reescribir cada llamada y rompe el despacho por tipo de campo —
# ``Properties`` sobreescribe ``property_to_sql``, y una función no se
# sobreescribe.
#
# Medido antes de adjuntar: ``to_sql`` y ``property_to_sql`` dan ``False`` en
# ``hasattr(models.Field, ...)``, así que no pisan nada de Django.


def _field_to_sql_expression(self, model, alias):
    """``to_sql`` — el valor de este campo desde el alias de tabla dado.

    ≙ ``Field.to_sql`` (``odoo19c: odoo/orm/fields.py:1209-1238``).

    Un campo sin columna no se puede convertir, y la fuente lo dice con el
    mismo error: ``store``/``column_type`` allá, ``concrete``/``column`` aquí
    —un ``models.Field`` es concreto cuando tiene columna propia, y las
    relaciones inversas y los ``ManyToMany`` no la tienen—. El ``NonStored``
    de ``orm/fields_nonstored.py`` ni siquiera llega: no es un campo de
    Django, así que ``_field_to_sql`` lo descarta antes.

    La fuente entrecomilla ``self.name`` porque allá el nombre del campo **es**
    el de la columna. Aquí no siempre: un ``db_column`` explícito o una FK
    —cuyo nombre de columna lleva el sufijo ``_id``— los separan. Lo que va en
    SQL es la **columna**, así que es ``self.column`` lo que se entrecomilla.

    La rama ``company_dependent`` (``odoo19c: :1217-1237``) **sí** tiene
    contraparte desde la tarea #111: la columna es ``jsonb`` con
    ``{empresa: valor}``, así que el SQL extrae la entrada de la empresa
    activa y cae al default de ``ir.default`` cuando no la hay. Es el
    ``COALESCE(col->empresa, to_jsonb(fallback::tipo))`` de la fuente.
    """
    if not getattr(self, 'concrete', False) or not getattr(self, 'column', None):
        raise ValueError(f"Cannot convert {self} to SQL because it is not stored")

    sql_field = SQL.identifier(alias, self.column, to_flush=self)
    if not getattr(self, 'company_dependent', False):
        return sql_field

    # ≙ ``:1218-1237``. El `->>` devuelve texto y el CAST lo lleva al tipo del
    # campo base; la fuente hace lo mismo y explica por qué no basta `->`: un
    # `'null'::jsonb` castea a la cadena 'null' en vez de a NULL.
    company_id = get_current_company()
    fallback = self.get_company_dependent_fallback_sql(model)
    return SQL(
        "COALESCE((%(column)s->>%(company_id)s)::%(cast)s, %(fallback)s)",
        column=sql_field,
        company_id=str(company_id) if company_id is not None else None,
        cast=SQL(self.sql_cast_type),
        fallback=fallback,
    )


def _field_property_to_sql(self, field_sql, property_name, model, alias, query):
    """``property_to_sql`` — el valor de una propiedad dentro del campo.

    ≙ ``Field.property_to_sql`` (``odoo19c: odoo/orm/fields.py:1241-1247``).
    El caso base **rechaza**: sólo un campo que contenga sub-campos sabe
    extraer uno, y quien lo sabe lo sobreescribe — ``Properties`` en
    ``orm/fields_properties.py``, igual que allá.
    """
    raise ValueError(f"Invalid field property {property_name!r} on {self}")


models.Field.to_sql = _field_to_sql_expression
models.Field.property_to_sql = _field_property_to_sql


# === expression_getter / filter_function ====================================
#
# El par que evalúa un dominio **en memoria**, sin ir al motor. La fuente los
# declara como métodos de ``Field``
# (``odoo19c: odoo/orm/fields.py:1384-1477``); aquí se cuelgan de
# ``models.Field`` al final del módulo, igual que ``to_sql`` y
# ``property_to_sql`` — un campo de Django no es nuestro para subclasificar,
# pero el nombre y la firma se conservan.
#
# Su consumidor es ``BaseModel.filtered_domain``, y quien lo necesita es
# ``ir.default._evaluate_condition_with_fallback``: preguntar si el valor de
# respaldo de un campo dependiente de empresa satisface una condición no se
# puede resolver en SQL, porque ese valor **no está en ninguna fila** — es el
# que responde el campo cuando la empresa no tiene el suyo.

#: Los cuatro operadores de desigualdad, a su función de Python.
_PYTHON_INEQUALITY_OPERATOR = {
    '<': operator_module.lt,
    '>': operator_module.gt,
    '<=': operator_module.le,
    '>=': operator_module.ge,
}


def _expression_getter(self, field_expr):
    """Un ``field_expr`` de dominio a la función que lo lee de un registro.

    ≙ ``Field.expression_getter`` (``odoo19c: odoo/orm/fields.py:1384-1394``).
    El caso base sólo sabe leer **el campo entero**; cualquier otra expresión
    la resuelve quien la entienda, sobreescribiendo este método.

    La divergencia de forma: allá el getter es ``self.__get__`` —el descriptor
    del campo—; aquí un campo de Django no es descriptor de lectura, así que
    es ``getattr(record, self.name)``. Mismo contrato: dado un registro,
    devuelve el valor.
    """
    if field_expr == self.name:
        return lambda record: getattr(record, self.name)
    raise ValueError(f'Expression not supported on {self}: {field_expr!r}')


def _filter_function(self, records, field_expr, operator, value):
    """Un ``(campo, operador, valor)`` a un predicado de un registro.

    ≙ ``Field.filter_function`` (``odoo19c: odoo/orm/fields.py:1396-1477``).
    Es el gemelo en memoria de :func:`condition_to_q`: aquella compila la
    condición a ``Q`` para que la resuelva PostgreSQL, ésta la compila a una
    función de Python para resolverla sobre registros que ya están en mano.

    **Sólo operadores positivos** — la negación la aplica quien llama, igual
    que allá, para no duplicar cada rama.
    """
    if operator in NEGATIVE_CONDITION_OPERATORS:
        raise ValueError(
            f'filter_function espera un operador positivo, no {operator!r}')
    getter = self.expression_getter(field_expr)

    # --- in (igualdad) ------------------------------------------------------
    if operator == 'in':
        if not isinstance(value, COLLECTION_TYPES) or not value:
            raise ValueError(
                f"filter_function con 'in' espera una colección no vacía, "
                f'no {type(value)}')
        values = value if isinstance(value, (set, frozenset)) else set(value)
        if False in values or falsy_value(self) in values:
            # Un campo sin valor cuenta como que lo tiene, si el conjunto
            # incluye el valor *falsy* — la misma regla que ``condition_to_q``
            # aplica al lado SQL.
            if len(values) == 1:
                return lambda record: not getter(record)
            return lambda record: (
                (val := getter(record)) in values or not val)
        return lambda record: getter(record) in values

    # --- familia like -------------------------------------------------------
    if operator.endswith('like'):
        if operator.endswith('ilike'):
            def normalize(x):
                # ``ilike`` compara en minúsculas, y **sin quitar acentos**
                # mientras ``UNACCENT_ENABLED`` sea falso. Ver su declaración:
                # tiene que decidir lo mismo que el lookup ``sql_ilike``, y ése
                # emite un ``ILIKE`` pelado.
                if not x:
                    return ''
                text = str(x).lower()
                return remove_accents(text) if UNACCENT_ENABLED else text
        else:
            def normalize(x):
                return str(x) if x else ''

        pattern = re.compile(
            ''.join(_like_regex_parts(normalize(value), '=' in operator)),
            flags=re.DOTALL)
        return lambda record: bool(pattern.match(normalize(getter(record))))

    # --- desigualdades ------------------------------------------------------
    if python_operator := _PYTHON_INEQUALITY_OPERATOR.get(operator):
        can_be_null = False
        if (null_value := falsy_value(self)) is not None:
            value = value or null_value
            can_be_null = (
                null_value < value if operator == '<' else
                null_value > value if operator == '>' else
                null_value <= value if operator == '<=' else
                null_value >= value)

        def check_inequality(record):
            record_value = getter(record)
            try:
                if record_value is False or record_value is None:
                    return can_be_null
                return python_operator(record_value, value)
            except (ValueError, TypeError):
                # Tipos que no se comparan: la fila no entra, no revienta.
                return False

        return check_inequality

    raise NotImplementedError(f'Operador simple inválido {operator!r}')


def _like_regex_parts(value, exact):
    """El patrón SQL ``LIKE`` a expresión regular, trozo a trozo.

    ≙ el ``build_like_regex`` anidado de la fuente
    (``odoo19c: odoo/orm/fields.py:1428-1445``). Se saca a función de módulo
    porque aquí ``filter_function`` no es un método de clase propia y anidarla
    la reconstruiría en cada llamada.

    ``%`` es ``.*``, ``_`` es un carácter, y ``\\`` escapa al siguiente — las
    tres reglas del ``LIKE`` de SQL.
    """
    yield '^' if exact else '.*'
    escaped = False
    for char in value:
        if escaped:
            escaped = False
            yield re.escape(char)
        elif char == '\\':
            escaped = True
        elif char == '%':
            yield '.*'
        elif char == '_':
            yield '.'
        else:
            yield re.escape(char)
    if exact:
        yield '$'


models.Field.expression_getter = _expression_getter
models.Field.filter_function = _filter_function


# --- El atributo ``copy`` — quién viaja en un duplicado ----------------------
#
# ≙ ``copy: bool = True`` (``odoo19c: odoo/orm/fields.py:281``), con su
# docstring verbatim: *"whether the field is copied over by BaseModel.copy()"*.
# Es el discriminador que ``copy_data`` consulta campo a campo (``:5438``), así
# que sin él el duplicado no puede decidir nada y lo copia todo.
#
# Va aquí y no en cada envoltorio de ``orm/fields_*`` por la misma razón que
# ``to_sql`` y ``expression_getter``: un ``Field`` es una pieza interna del ORM
# que nadie hereda, y los envoltorios son **veinte**. Ponerlo en la clase lo da
# a los veinte de una vez, con la ortografía de la fuente.

#: El default de la fuente: un campo se copia salvo que diga lo contrario.
models.Field.copy = True

_DJANGO_FIELD_INIT = models.Field.__init__


def _field_init_with_copy(self, *args, copy=True, **kwargs):
    """Acepta ``copy=`` en la declaración y lo anota en el campo.

    Django no conoce la bandera, así que pasársela a su ``__init__`` sería un
    ``TypeError``. Se saca de los kwargs y se guarda en la instancia; la
    columna no cambia — ``copy`` no es una propiedad del almacenamiento sino
    del duplicado, igual que allá.
    """
    _DJANGO_FIELD_INIT(self, *args, **kwargs)
    self.copy = copy


models.Field.__init__ = _field_init_with_copy

_DJANGO_FIELD_DECONSTRUCT = models.Field.deconstruct


def _field_deconstruct_without_copy(self):
    """``copy`` NO viaja a la migración, y es deliberado.

    El estado de la migración describe la **columna**; ``copy`` describe la
    conducta del duplicado. Emitirlo cambiaría el estado de todos los campos
    del árbol y ``makemigrations --check`` dejaría de estar limpio, sin que
    ninguna columna hubiera cambiado. Mismo criterio que ``Html.deconstruct``,
    que devuelve la ruta de ``TextField`` para no mover las migraciones ya
    generadas.
    """
    name, path, args, kwargs = _DJANGO_FIELD_DECONSTRUCT(self)
    kwargs.pop('copy', None)
    return name, path, args, kwargs


models.Field.deconstruct = _field_deconstruct_without_copy


# === Los seis del censo de ``odoo/orm/fields.py`` (tarea #209) ==============
#
# La referencia declara **9** símbolos de nivel superior; dos ya viven aquí en
# otro archivo (``COMPANY_DEPENDENT_FIELDS`` en ``fields_company_dependent``,
# ``_logger`` en ``environments``). Los seis restantes se portan **en este
# archivo**, que es donde la fuente los declara — segunda cláusula de
# ``atributos-de-clase-de-modelo.md``.
#
# Ninguno cae en EXCLUIDO: los seis son TRAE o CONSTRUYE. El veredicto por
# símbolo, con su consumidor medido, está en
# ``docs: …/analisis-censo-orm-referencia-trae-o-construye.rst``.

#: ≙ ``T = typing.TypeVar("T")`` (``odoo19c: odoo/orm/fields.py:35``) — el
#: parámetro del genérico ``Field[T]``. TRAE: biblioteca estándar.
T = TypeVar('T')

#: ≙ ``IR_MODELS`` (``:37``) — los siete modelos del registro que un
#: ``Many2one`` NO puede proteger con ``on_delete=PROTECT``.
#:
#: Su consumidor en la fuente es ``fields_relational.py:289``:
#: ``if self.ondelete == 'restrict' and self.comodel_name in IR_MODELS``. La
#: razón es que el propio registro se desmonta al desinstalar un módulo, y una
#: FK que lo proteja convierte esa operación en un error.
IR_MODELS = (
    'ir.model', 'ir.model.data', 'ir.model.fields', 'ir.model.fields.selection',
    'ir.model.relation', 'ir.model.constraint', 'ir.module.module',
)

#: ≙ ``PYTHON_INEQUALITY_OPERATOR`` (``:45``) — la comparación **en memoria**.
#:
#: NO es lo mismo que ``_INEQUALITY_LOOKUP``, que traduce el mismo operador al
#: nombre de lookup de Django para que la comparación la haga PostgreSQL. La
#: fuente declara los dos porque tiene los dos caminos, y aquí igual: éste lo
#: consume :func:`condition_matches_in_memory`, aquél :func:`condition_to_q`.
PYTHON_INEQUALITY_OPERATOR = {
    '<': operator_module.lt,
    '>': operator_module.gt,
    '<=': operator_module.le,
    '>=': operator_module.ge,
}

#: ≙ ``_global_seq = itertools.count()`` (``:89``) — el orden de declaración.
#:
#: DIVERGENCIA DE MECANISMO, y es que el stack ya lo TRAE: Django numera cada
#: campo al construirlo con ``models.Field.creation_counter``, con el mismo
#: propósito —ordenar los campos por el orden en que se escribieron— y ya
#: consumido por ``_meta.get_fields()``. Declarar un segundo contador daría dos
#: numeraciones para una sola pregunta. El nombre se conserva como alias para
#: que la lectura contra la fuente no exija traducir.
def global_seq():
    """El siguiente número de orden de declaración — ≙ ``next(_global_seq)``."""
    value = models.Field.creation_counter
    models.Field.creation_counter += 1
    return value


def resolve_mro(model, name, predicate):
    """Los valores sucesivamente sobreescritos de ``name`` en el MRO.

    Docstring de la fuente, verbatim: *"Return the list of successively
    overridden values of attribute ``name`` in mro order on ``model`` that
    satisfy ``predicate``. Model registry classes are ignored."*
    (``odoo19c: odoo/orm/fields.py:50-64``).

    CONSTRUYE: el ``__mro__`` de Python basta. La fuente recorre
    ``model._model_classes__`` —su lista de clases de módulo, que excluye las
    que su registro fabrica— y aquí el equivalente es el ``__mro__`` de la
    clase saltando ``object``: Django no fabrica clases intermedias, así que
    todo lo que hay en el MRO lo escribió alguien.

    Se detiene en el primer valor que **no** cumple ``predicate``, no lo salta.
    Esa diferencia es el contrato: la lista describe una cadena de
    sobreescrituras contigua, y un eslabón de otra naturaleza la corta.

    :param model: la clase (o instancia) cuyo MRO se recorre.
    :param name: el atributo a buscar en cada clase de la cadena.
    :param predicate: qué valores cuentan; el primero que falle corta.
    :returns: los valores en orden de MRO — el más derivado primero.
    """
    cls = model if isinstance(model, type) else type(model)
    result = []
    for klass in cls.__mro__:
        if klass is object:
            continue
        value = klass.__dict__.get(name, _MRO_SENTINEL)
        if value is _MRO_SENTINEL:
            continue
        if not predicate(value):
            break
        result.append(value)
    return result


#: Centinela propio de :func:`resolve_mro`: distingue *"la clase no declara el
#: atributo"* de *"lo declara con valor ``None``"*. La fuente usa su ``SENTINEL``
#: de ``odoo.tools``.
_MRO_SENTINEL = object()


def determine(needle, records, *args):
    """Llama un método dado como cadena o como invocable — ≙ ``determine``.

    Docstring de la fuente, verbatim: *"Simple helper for calling a method
    given as a string or a function."* (``odoo19c: odoo/orm/fields.py:66-87``).

    CONSTRUYE: ``getattr`` y ``callable`` de la estándar.

    DIVERGENCIA DE MECANISMO: la fuente exige que ``records`` sea un recordset
    (``isinstance(records, BaseModel)``) porque allá todo método de modelo
    opera sobre un conjunto. Aquí el sujeto es una **instancia de modelo o un
    queryset**, y la comprobación se relaja a *"no es None"*: exigir una clase
    concreta obligaría a importar ``models`` desde este archivo, que es su
    dependiente.

    :raises TypeError: si ``needle`` no es invocable ni nombra un método.
    """
    if records is None:
        raise TypeError('La determinación necesita un sujeto sobre el que '
                        'llamar; se recibió None.')
    if isinstance(needle, str):
        method = getattr(records, needle, None)
        if method is None:
            raise TypeError(
                f'{type(records).__name__} no declara el método {needle!r}.')
        return method(*args)
    if callable(needle):
        return needle(records, *args)
    raise TypeError('La determinación necesita un invocable o el nombre de un '
                    f'método; se recibió {needle!r}.')


# === El registro de tipos de campo — ``Field._by_type__`` ===================
#
# La fuente lo puebla en ``__init_subclass__``: cada subclase de ``Field`` se
# inscribe con su ``type`` (``odoo19c: odoo/orm/fields.py:312,327``). Aquí las
# subclases son de Django y su ``__init_subclass__`` es de Django, así que el
# registro se **deriva** de ``__all__`` — el mismo criterio con que
# ``ir_model.FIELD_TYPES`` ya se derivaba de él.
#
# Vive aquí y no en ``ir_model.py`` porque aquí es donde la referencia lo
# declara, y porque tenerlo en los dos sitios sería la segunda fuente de
# verdad que ``calibration-verified-numbers.md`` prohíbe: ``ir_model`` lo
# importa de este módulo.

#: Separa el ``CamelCase`` del nombre exportado para reconstruir la clave del
#: tipo: ``Many2oneReference`` → ``many2one_reference``.
_CAMEL_BOUNDARY = re.compile(r'(?<=[a-z0-9])(?=[A-Z])')


def _type_key(exported_name):
    """Nombre de clase exportado → clave de tipo al estilo de la referencia."""
    return _CAMEL_BOUNDARY.sub('_', exported_name).lower()


#: ≙ ``Field._by_type__`` (``odoo19c: odoo/orm/fields.py:312``) — «mapping from
#: type name to field type». Derivado de :data:`__all__`, no declarado: una
#: lista escrita a mano se desincroniza con el módulo en el primer campo nuevo.
_by_type__ = {_type_key(name): globals()[name] for name in __all__}

#: Tipo interno de Django → clave de tipo de la referencia, para el recorrido
#: **inverso**: dado un campo ya construido, qué ``type`` declara.
#:
#: Declarado y no derivado, y la razón es que el mapa de alias es
#: muchos-a-uno: ``Char``, ``Text`` y ``Html`` comparten familia en Django, así
#: que ``_by_type__`` no se puede invertir sin perder información. ``html``
#: no se recupera nunca —colapsa en ``text``—; ``selection`` sí, porque
#: ``choices`` lo delata.
DJANGO_TYPE_TO_TTYPE = {
    'AutoField': 'integer',
    'BigAutoField': 'integer',
    'BigIntegerField': 'integer',
    'BinaryField': 'binary',
    'BooleanField': 'boolean',
    'CharField': 'char',
    'DateField': 'date',
    'DateTimeField': 'datetime',
    'DecimalField': 'monetary',
    'EmailField': 'char',
    'FileField': 'binary',
    'FloatField': 'float',
    'ForeignKey': 'many2one',
    'ImageField': 'image',
    'IntegerField': 'integer',
    'JSONField': 'json',
    'ManyToManyField': 'many2many',
    'OneToOneField': 'many2one',
    'PositiveIntegerField': 'integer',
    'PositiveSmallIntegerField': 'integer',
    'SlugField': 'char',
    'SmallIntegerField': 'integer',
    'TextField': 'text',
    'URLField': 'char',
    'UUIDField': 'char',
}


def type_for(field):
    """El ``type`` de la referencia que le corresponde a un campo de Django.

    Es la función que puebla :attr:`Field.type`. ``ir.model.fields.ttype_for``
    delega aquí desde el 2026-08-30: el mapa tenía dos dueños y el de la
    referencia es éste.
    """
    internal = field.get_internal_type()
    if internal == 'CharField' and getattr(field, 'choices', None):
        return 'selection'
    return DJANGO_TYPE_TO_TTYPE.get(internal, 'char')


# ===========================================================================
# ``Field`` — el contrato del campo, instalado sobre la base de Django
# ===========================================================================
#
# ``odoo19c: odoo/orm/fields.py:92-1932`` declara ``Field`` como la clase base
# de la que cuelga todo campo del ORM: 68 atributos de clase y 72 métodos.
#
# Aquí ``Field`` **es** ``django.db.models.Field``, y no una clase paralela.
# Es la lectura fiel: allá ``Field`` es la base de la que hereda todo campo, y
# aquí la base de la que hereda todo campo es la de Django —``Integer =
# models.IntegerField``, ``fields_numeric.py``—. Un ``Field`` propio dejaría
# ``isinstance(campo, Field)`` en falso para los veinte tipos del árbol, que es
# exactamente lo contrario de lo que la fuente garantiza.
#
# Las cinco mediciones que fijan la forma
# =======================================
#
# Reproducibles con ``uv run python scripts/census_field_contract.py``:
#
# 1. **140 símbolos** declara la fuente (68 atributos + 72 métodos).
# 2. **4 colisionan** con ``django.db.models.Field``: ``__init__``, ``__str__``,
#    ``__repr__`` y ``__init_subclass__``. Los cuatro son de Django y se
#    respetan — instalar los de la fuente encima rompería el ORM anfitrión.
#    Los otros **136** se instalan sin pisar nada.
# 3. **2 de 68** atributos los fija una instancia de Django en su ``__init__``
#    (``default`` y ``name``), así que su default de clase nunca se consulta.
#    Los otros **66** quedan vivos, que es lo que la fuente quiere.
# 4. **13 nombres se ASIGNAN** en este árbol y **5 en Django**. Ésos no pueden
#    portarse como ``property`` de solo lectura —la asignación levantaría
#    ``AttributeError``—, así que van como atributo llano que la instancia
#    pisa. Es la medición que decide, una por una, entre las dos formas.
#
#    Su **raíz importa tanto como su regla**: acotada a ``django/db/models``
#    publicaba 0 asignaciones de ``base_field``, se portó como ``property``, y
#    el arranque de Django reventó — ``ArrayField.__init__`` lo asigna desde
#    ``django/contrib/postgres/fields/array.py:27``. Hoy la raíz es el paquete
#    entero. De ahí sale :class:`_ComputedUnlessAssigned`, el descriptor NO de
#    datos que deja ganar a quien asigne.
# 5. **La conducta** — a qué responde ``models.Field`` con este módulo ya
#    cargado. Es el único eje que no mide el NOMBRE, y hace falta porque la
#    medición 1 busca el nombre en TODO ``src/``: una mención en un docstring
#    de otro archivo la satisface. ``get_description`` figuraba presente por
#    una línea de prosa que decía que NO existía.
#
# El veredicto por grupo — TRAE / CONSTRUYE
# ==========================================
#
# ==================================  ==========  ============================
# Mecanismo                           Veredicto   Con qué
# ==================================  ==========  ============================
# la base de todo campo               **TRAE**    ``models.Field``
# etiqueta, ayuda y edición           **TRAE**    ``verbose_name``,
#                                                 ``help_text``, ``editable``
# la columna y si se almacena         **TRAE**    ``db_column``, ``db_type``,
#                                                 ``concrete``
# la relación y su modelo             **TRAE**    ``is_relation``,
#                                                 ``related_model``
# crear y alterar la columna          **TRAE**    ``SchemaEditor`` — el DDL
#                                                 que las migraciones emiten
# el orden de declaración             **TRAE**    ``creation_counter``
# ligar el campo a su modelo          **TRAE**    ``contribute_to_class``,
#                                                 el ``__set_name__`` de Django
# la caché de campo por transacción   CONSTRUYE   ``orm.environments``
#                                                 :class:`Transaction`
# el orden de columna por tipo        CONSTRUYE   ``tools.sql``
#                                                 ``sql_order_by_type``
# la descripción del campo al cliente CONSTRUYE   los ``_description_*`` sobre
#                                                 lo que ya se deriva
# el campo relacionado (``related=``) CONSTRUYE   recorrido por ``getattr``
# el cómputo diferido y su inversa    CONSTRUYE   :func:`determine` sobre
#                                                 ``tocompute``
# ==================================  ==========  ============================
#
# Ninguno queda EXCLUIDO: los 140 símbolos tienen su desenlace.

_logger = logging.getLogger(__name__)

#: ≙ ``Field`` (``odoo19c: odoo/orm/fields.py:92``). El nombre de la fuente,
#: ligado a la base real de este árbol. ``isinstance(campo, Field)`` es cierto
#: para los veinte tipos exportados, igual que allá.
Field = models.Field


#: Los 66 atributos de clase cuyo default de la fuente queda **vivo** aquí —
#: los dos que faltan del total de 68 son ``default`` y ``name``, que toda
#: instancia de Django fija en su ``__init__`` (medición 3 del censo).
#:
#: Se instalan como atributos llanos y no como ``property`` porque la medición
#: 4 encontró que trece de ellos se asignan en este árbol; distinguir cuáles
#: uno por uno partiría el grupo sin ganancia, y un atributo llano se
#: comporta igual que el default de clase de la fuente: la instancia lo pisa
#: cuando quiere, y cuando no, gobierna el de aquí.
_FIELD_CLASS_ATTRIBUTES = {
    # --- identidad y naturaleza del campo -------------------------------
    'translate': False,             # si el campo se traduce
    'is_text': False,               # si en la base es un tipo textual
    'falsy_value': None,            # el valor que cuenta como no establecido
    'write_sequence': 0,            # orden del campo dentro de un ``write()``
    '_column_type': None,           # (ident, spec) de la columna
    # --- procedencia y montaje ------------------------------------------
    '_args__': None,                # los parámetros que recibió ``__init__``
    '_module': None,                # el módulo que declara el campo
    '_modules': (),                 # los módulos que lo definen
    '_setup_done': True,            # si el montaje del campo terminó
    '_base_fields__': (),           # los campos que definen a éste, en orden
    '_extra_keys__': (),            # los parámetros desconocidos que recibió
    '_direct': False,               # si se puede usar directamente (compartido)
    '_toplevel': False,             # si está en la clase de registro del modelo
    # --- herencia por delegación (``_inherits``) -------------------------
    'inherited': False,             # si el campo es heredado
    'inherited_field': None,        # el campo heredado correspondiente
    # --- nombres ----------------------------------------------------------
    'model_name': '',               # el modelo de este campo
    'comodel_name': None,           # el modelo de los valores, si es relacional
    # --- almacenamiento ---------------------------------------------------
    'store': True,                  # si se almacena en la base
    'index': None,                  # cómo se indexa en la base
    'manual': False,                # si es un campo a medida
    'copy': True,                   # si se copia al duplicar el registro
    # --- cómputo, inversa y búsqueda --------------------------------------
    '_depends': None,               # las dependencias declaradas
    '_depends_context': None,       # las claves de contexto de las que depende
    'recursive': False,             # si el campo depende de sí mismo
    'compute': None,                # compute(recs) calcula el campo
    'compute_sudo': False,          # si el cómputo corre elevado
    'precompute': False,            # si se calcula antes de crear la fila
    'inverse': None,                # inverse(recs) invierte el campo
    'search': None,                 # search(recs, operador, valor)
    'related': None,                # la ruta de campos, si es relacionado
    'related_field': None,          # el campo relacionado correspondiente
    'company_dependent': False,     # si el valor depende de la empresa activa
    # --- presentación -----------------------------------------------------
    'string': None,                 # la etiqueta del campo
    'export_string_translation': True,  # si su etiqueta se exporta traducida
    'help': None,                   # el texto de ayuda
    'readonly': False,              # si es de solo lectura en la interfaz
    'required': False,              # si el valor es obligatorio
    'groups': None,                 # los grupos que pueden verlo
    'change_default': False,        # si puede disparar un "user-onchange"
    'aggregator': None,             # el operador con que se agrega
    'group_expand': None,           # el método que expande los grupos
    'falsy_value_label': None,      # qué mostrar cuando no está establecido
    'prefetch': True,               # el grupo de prelectura
    'default_export_compatible': False,  # si se exporta por defecto
    'exportable': True,             # si el campo es exportable
}

for _name_attr, _default_value in _FIELD_CLASS_ATTRIBUTES.items():
    if not hasattr(models.Field, _name_attr):
        setattr(models.Field, _name_attr, _default_value)

#: El mismo contrato sobre :class:`~orm.fields_nonstored.NonStored`, con UNA
#: excepción: ``store``.
#:
#: En la fuente no hay dos clases. Un campo sin columna **es** un ``Field`` con
#: ``store=False`` (``odoo19c: odoo/orm/fields.py:455``), así que responde a
#: los mismos cuarenta y tantos atributos que cualquier otro. Aquí la jerarquía
#: del stack los separa —``NonStored`` no desciende de ``models.Field``, y no
#: puede: no tiene columna que declarar—, y el bucle de arriba sólo alcanzaba a
#: la clase de Django. El resultado era que un campo sin columna levantaba
#: ``AttributeError`` ante ``_description_searchable``, que es justo lo que
#: ``_field_setup_related`` pregunta a **cada eslabón** de una cadena
#: ``related=`` antes de cablear su búsqueda (:ref:`h-api-1027`).
#:
#: ``store`` va a ``False`` y no al defecto de ``Field``: es lo que la clase
#: significa, y de él depende ``_description_searchable`` —``bool(self.store or
#: self.search)``—, que con ``True`` daría buscable a todos y no discriminaría
#: nada.
for _name_attr, _default_value in _FIELD_CLASS_ATTRIBUTES.items():
    if not hasattr(NonStored, _name_attr):
        setattr(NonStored, _name_attr,
                False if _name_attr == 'store' else _default_value)

#: Las sobrescrituras por clase concreta van DESPUÉS del bucle: el bucle pone
#: el defecto de ``Field`` y éstas lo pisan donde la fuente lo pisa. Invertir
#: el orden no cambia nada —son clases distintas— pero leerlo así deja claro
#: cuál es el defecto y cuál la excepción.
install_class_attribute_overrides()


def _char_column_type(self):
    """≙ ``Char._column_type`` (``odoo19c: odoo/orm/fields_textual.py:494-496``).

    Allá es ``('varchar', pg_varchar(self.size))`` y aquí ``size`` es el
    ``max_length`` de Django. Es una ``property`` y no una entrada de
    :data:`_CLASS_ATTRIBUTE_OVERRIDES` porque **depende de la instancia**: dos
    ``CharField`` de la misma clase declaran columnas distintas.

    La misma ``property`` sirve a ``Selection`` (``fields_selection.py:63``),
    que declara ``('varchar', pg_varchar())`` — el caso de ``size`` ausente.
    Las dos clases de la fuente comparten aquí una sola clase de Django, así
    que compartir el descriptor no es una simplificación: es la única forma en
    que ``CharField`` puede responder por ambas.
    """
    return ('varchar', pg_varchar(self.max_length or 0))


models.CharField._column_type = property(_char_column_type)


#: ``type`` — el vocabulario de la fuente sobre un campo de Django.
#:
#: Es el único de los 68 atributos de clase que **no** puede ser un valor
#: llano: allá cada clase concreta declara el suyo (``Boolean.type =
#: 'boolean'``), y aquí la clase concreta es la de Django, compartida entre
#: tipos que la fuente separa. Un ``CharField`` con ``choices`` **es** la
#: ``Selection`` de la fuente, y sin ``choices`` es su ``Char``: dos
#: instancias de la misma clase con tipos distintos, que ningún atributo de
#: clase puede expresar.
#:
#: Por eso delega en :func:`type_for`, que ya sabía el mapa completo y no
#: estaba cableado a nada: hasta este porte ``type`` valía ``''`` en toda
#: familia salvo ``date`` y ``datetime`` —las dos que ``fields_temporal``
#: declara en su clase concreta, como la fuente—. El despacho por tipo de
#: campo del registro de optimizadores (``orm/domains.py``) buscaba esa cadena
#: vacía y no casaba con ninguna familia registrada.
#:
#: Un atributo llano de la subclase gana sobre esta ``property`` por
#: resolución de atributo, así que las dos declaraciones de
#: ``fields_temporal`` siguen gobernando su clase.
models.Field.type = property(type_for)


#: ``relational`` — hermano de ``type``, y con el mismo defecto de origen.
#:
#: La fuente lo declara **una vez**, en la base abstracta de los tres campos
#: de relación: ``_Relational.relational: typing.Literal[True] = True``
#: (``odoo19c: odoo/orm/fields_relational.py:35``). Aquí esa base es la de
#: Django, que ya publica el mismo predicado con otro nombre —``is_relation``,
#: verdadero para ``ForeignKey``, ``OneToOneField`` y ``ManyToManyField``—.
#:
#: Instalado como valor llano valía ``False`` incluso en un ``ForeignKey``,
#: que es lo contrario de lo que la fuente garantiza. Su consumidor inmediato
#: es ``_optimize_like_str``, que ramifica por él: un campo relacional con un
#: patrón vacío devuelve una condición sobre el campo, y uno escalar devuelve
#: un booleano. Con ``False`` universal el escalar se aplicaba a los dos.
models.Field.relational = property(lambda self: self.is_relation)

#: ≙ ``Field._by_type__`` colgado de la clase, como en la fuente.
models.Field._by_type__ = _by_type__


# ═══════════════════════════════════════════════════════════════════════════
# El protocolo de descripción — ≙ ``odoo19c: odoo/orm/fields.py:872-975``
# ═══════════════════════════════════════════════════════════════════════════
#
# Es el bloque con el que un campo se **describe a su cliente**: qué nombre
# lleva, de qué tipo es, si se puede ordenar, agrupar o agregar por él. La
# fuente lo resuelve con un convenio de nombres —todo atributo que empieza por
# ``_description_`` publica la clave que sigue al prefijo— y una tabla
# ``description_attrs`` que su ``__init_subclass__`` deriva con ``dir(cls)``.
#
# Aquí ``__init_subclass__`` es una de las cuatro colisiones medidas: es de
# Django y se respeta. La derivación se construye con la misma regla y el
# mismo momento efectivo —la primera vez que alguien la pide, por clase— con
# el descriptor :class:`_DerivedFromPrefix`, que cachea el resultado en el
# ``__dict__`` de la clase que lo pidió. La diferencia con la fuente es
# **cuándo** se deriva, no **qué** deriva: allá al crear la subclase, aquí al
# primer acceso. Una subclase que añada su propio ``_description_*`` obtiene
# su tabla igual que allá, porque ``dir()`` la ve.


class _DerivedFromPrefix:
    """Deriva una tabla ``(clave, atributo)`` de los nombres con un prefijo.

    ≙ el cuerpo de ``__init_subclass__`` (``odoo19c: :336-344``), que hace lo
    mismo con ``dir(cls)`` al crear cada subclase. Aquí es un descriptor de
    clase porque ``__init_subclass__`` colisiona con el de Django.

    Cachea **por clase**, así que la derivación corre una vez por cada una —
    igual que allá, donde corre una vez por creación de subclase.

    El caché va en un mapa propio y NO con ``setattr`` sobre la clase, y la
    razón se midió: al pedir la tabla sobre ``models.Field`` —la clase que
    aloja el descriptor— el ``setattr`` lo sustituía por la tupla, y a partir
    de ahí toda subclase heredaba la tabla de la base en vez de derivar la
    suya. El caché se comía al mecanismo que cachea.

    El mapa es débil en su clave para no retener una clase que ya nadie usa.
    """

    def __init__(self, prefix, attribute_name):
        self.prefix = prefix
        self.attribute_name = attribute_name
        self._by_class = weakref.WeakKeyDictionary()

    def __get__(self, instance, owner=None):
        owner = owner if owner is not None else type(instance)
        cached = self._by_class.get(owner)
        if cached is not None:
            return cached
        cut = len(self.prefix)
        table = tuple((name[cut:], name) for name in dir(owner)
                      if name.startswith(self.prefix))
        self._by_class[owner] = table
        return table


#: ≙ ``Field.related_attrs`` / ``Field.description_attrs`` (``:336-344``).
models.Field.related_attrs = _DerivedFromPrefix('_related_', 'related_attrs')
models.Field.description_attrs = _DerivedFromPrefix('_description_',
                                                    'description_attrs')


def _field_get_description(self, env, attributes=None):
    """≙ ``Field.get_description`` (``:872``) — «return a dictionary that
    describes the field ``self``».

    El convenio es el de la fuente verbatim: se recorre ``description_attrs``,
    se descarta lo que no empiece por ``_description_``, se llama al valor si
    es invocable —los que necesitan el entorno lo son— y se omite el ``None``.

    Omitir el ``None`` no es cosmético: la clave ausente y la clave con
    ``None`` significan cosas distintas para el cliente, y la fuente elige la
    primera.
    """
    description = {}
    for key, attribute in self.description_attrs:
        if attributes is not None and key not in attributes:
            continue
        if not attribute.startswith('_description_'):
            continue
        value = getattr(self, attribute)
        if callable(value):
            value = value(env)
        if value is not None:
            description[key] = value
    return description


models.Field.get_description = _field_get_description

#: Los doce que la fuente declara como ``property(attrgetter(...))``
#: (``:889-900``): la clave publicada es el nombre del atributo que leen.
#: Se instalan con la misma forma —``property``— porque ninguno de los doce
#: aparece en la medición 4 del censo como asignado.
for _key, _source_attribute in (
        ('name', 'name'),
        ('type', 'type'),
        ('store', 'store'),
        ('manual', 'manual'),
        ('related', 'related'),
        ('company_dependent', 'company_dependent'),
        ('readonly', 'readonly'),
        ('required', 'required'),
        ('groups', 'groups'),
        ('change_default', 'change_default'),
        ('default_export_compatible', 'default_export_compatible'),
        ('exportable', 'exportable'),
):
    setattr(models.Field, f'_description_{_key}', property(attrgetter(_source_attribute)))


def _field_description_depends(self, env):
    """≙ ``Field._description_depends`` (``:902``) — las dependencias que el
    registro tiene anotadas para este campo."""
    return env.registry.field_depends[self]


models.Field._description_depends = _field_description_depends


@property
def _field_description_searchable(self):
    """≙ ``Field._description_searchable`` (``:906``) — ``bool(self.store or
    self.search)``, verbatim.

    Un campo con columna se busca por SQL; uno sin columna se busca sólo si
    declara su ``search=``. La disyunción es la misma que allá porque el
    fenómeno es el mismo: hay o no hay por dónde buscar.
    """
    return bool(self.store or self.search)


models.Field._description_searchable = _field_description_searchable
#: Y sobre el campo sin columna, por la misma razón que ``determine_domain`` se
#: instala en las dos clases: es una ``property``, así que el bucle de
#: :data:`_FIELD_CLASS_ATTRIBUTES` —que copia valores— no la alcanza.
NonStored._description_searchable = _field_description_searchable


def _field_description_sortable(self, env):
    """≙ ``Field._description_sortable`` (``:909``).

    **Divergencia de mecanismo, no de contrato.** La fuente responde
    construyendo la consulta y viendo si revienta: llama a
    ``model._order_field_to_sql(...)`` dentro de un ``try`` y devuelve
    ``False`` ante ``ValueError``/``AccessError``. Es su forma de preguntarle
    al motor, porque allá el motor de consultas es suyo.

    Aquí el motor es el de Django, y la misma pregunta se responde **sin
    construir nada**: un campo es ordenable si tiene columna. ``concrete`` es
    el atributo con que Django lo declara, y es exacto — un campo no concreto
    no tiene por dónde ordenarse en SQL.

    El atajo de la fuente y su herencia se conservan verbatim: el campo
    heredado responde por el suyo para no recomputar.
    """
    if self.column_type and self.store:
        return True
    inherited = self.inherited_field
    if inherited is not None and inherited._description_sortable(env):
        return True
    return bool(getattr(self, 'concrete', False))


models.Field._description_sortable = _field_description_sortable


def _field_description_groupable(self, env):
    """≙ ``Field._description_groupable`` (``:924``).

    Misma divergencia de mecanismo que :func:`_field_description_sortable`, y
    por la misma razón. La fuente distingue el caso temporal —agrupa por
    ``<campo>:month``, no por el valor crudo— y esa distinción se conserva
    porque es de contrato, no de motor: un ``date`` se agrupa por tramo.
    """
    if self.column_type and self.store:
        return True
    inherited = self.inherited_field
    if inherited is not None and inherited._description_groupable(env):
        return True
    return bool(getattr(self, 'concrete', False))


models.Field._description_groupable = _field_description_groupable


def _field_description_aggregator(self, env):
    """≙ ``Field._description_aggregator`` (``:940``).

    Devuelve el operador con que el campo se agrega, o ``None`` si no lo
    admite. La primera guarda es la de la fuente verbatim: sin ``aggregator``
    declarado no hay nada que devolver, y con columna almacenada se devuelve
    sin más comprobación.
    """
    if not self.aggregator or (self.column_type and self.store):
        return self.aggregator
    inherited = self.inherited_field
    if inherited is not None and inherited._description_aggregator(env):
        return inherited.aggregator
    return self.aggregator if getattr(self, 'concrete', False) else None


models.Field._description_aggregator = _field_description_aggregator


def _field_description_string(self, env):
    """≙ ``Field._description_string`` (``:955``) — la etiqueta, traducida al
    idioma del entorno cuando lo hay.

    Delega en ``ir.model.fields.get_field_string``, que es quien guarda el
    mapa. Sin idioma en el entorno devuelve la etiqueta declarada, igual que
    allá: no hay a qué traducir.
    """
    if self.string and env.lang:
        model_name = self.base_field.model_name
        field_string = env['ir.model.fields'].get_field_string(model_name)
        return field_string.get(self.name) or self.string
    return self.string


models.Field._description_string = _field_description_string


def _field_description_help(self, env):
    """≙ ``Field._description_help`` (``:962``) — el hermano de
    :func:`_field_description_string` para el texto de ayuda."""
    if self.help and env.lang:
        model_name = self.base_field.model_name
        field_help = env['ir.model.fields'].get_field_help(model_name)
        return field_help.get(self.name) or self.help
    return self.help


models.Field._description_help = _field_description_help


def _field_description_falsy_value_label(self, env):
    """≙ ``Field._description_falsy_value_label`` (``:969``) — qué mostrar
    cuando el valor no está establecido, traducido."""
    return _(self.falsy_value_label) if self.falsy_value_label else None


models.Field._description_falsy_value_label = _field_description_falsy_value_label


def _field_is_editable(self):
    """≙ ``Field.is_editable`` (``:972``) — «return whether the field can be
    editable in a view». Verbatim: ``not self.readonly``.

    NO es el ``editable`` de Django, aunque suene igual: aquél gobierna si el
    campo aparece en un ``ModelForm``; éste, si la vista lo deja editar. El
    nombre de la fuente se conserva justamente para que los dos no se
    confundan.
    """
    return not self.readonly


models.Field.is_editable = _field_is_editable


# ═══════════════════════════════════════════════════════════════════════════
# El campo relacionado y la columna — ≙ ``odoo19c: :774-792``
# ═══════════════════════════════════════════════════════════════════════════

#: ≙ los cinco ``_related_*`` (``:774-778``). Publican, con el mismo convenio
#: de prefijo que los ``_description_*``, qué atributo hereda un campo
#: ``related=`` de aquél al que apunta. Los lee ``related_attrs``.
for _key, _source_attribute in (
        ('comodel_name', 'comodel_name'),
        ('string', 'string'),
        ('help', 'help'),
        ('groups', 'groups'),
        ('aggregator', 'aggregator'),
):
    setattr(models.Field, f'_related_{_key}', property(attrgetter(_source_attribute)))


@property
def _field_column_type(self):
    """≙ ``Field.column_type`` (``:781``) — «return the actual column type for
    this field, if stored as a column».

    La rama de la fuente se conserva verbatim: un campo dependiente de empresa
    o traducible guarda un mapa, no un escalar, así que su columna es
    ``jsonb`` sea cual sea su tipo declarado. El resto devuelve su
    ``_column_type``.

    Allá es ``functools.cached_property``; aquí es ``property`` sin caché
    porque ``_column_type`` es un atributo de clase que ninguna instancia
    reescribe —medición 4 del censo: **1** asignación en todo el árbol, la de
    ``fields_temporal._attach_base_date``, que corre al declarar la clase—.
    Cachear un valor que no cambia no compra nada y añade una entrada por
    instancia.
    """
    if self.company_dependent or self.translate:
        return ('jsonb', 'jsonb')
    return self._column_type


models.Field.column_type = _field_column_type


class _ComputedUnlessAssigned:
    """Un valor derivado que la instancia puede pisar — descriptor NO de datos.

    Una ``property`` es descriptor **de datos**: define ``__set__``, así que
    gana sobre el ``__dict__`` de la instancia y una asignación revienta con
    ``property of X has no setter``. Un descriptor que declara sólo ``__get__``
    es **no** de datos: Python consulta primero el ``__dict__``, de modo que
    quien asigne el atributo gana y quien no, obtiene el valor derivado.

    Es el mecanismo exacto que el porte de ``base_field`` necesita, y la razón
    está medida, no supuesta: ``ArrayField.__init__`` **asigna**
    ``self.base_field`` (``django/contrib/postgres/fields/array.py:27``) con
    otro significado —el campo de los elementos del arreglo—, y ``ArrayField``
    hereda de ``models.Field``. Instalarlo como ``property`` aborta el
    arranque de Django entero.
    """

    def __init__(self, function):
        self.function = function
        self.__doc__ = function.__doc__

    def __set_name__(self, owner, name):
        self.attribute_name = name

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        return self.function(instance)


def _field_base_field(self):
    """≙ ``Field.base_field`` (``:786``) — «return the base field of an
    inherited field, or ``self``». Verbatim, recursivo por
    ``inherited_field``.
    """
    inherited = self.inherited_field
    return inherited.base_field if inherited is not None else self


#: NO es ``property``: ver :class:`_ComputedUnlessAssigned`. La forma la fija
#: la medición 4 del censo, con la raíz de Django ya ensanchada al paquete
#: entero — con la raíz estrecha publicaba 0 asignaciones y el porte reventó.
models.Field.base_field = _ComputedUnlessAssigned(_field_base_field)


# ═══════════════════════════════════════════════════════════════════════════
# El campo relacionado — ≙ ``odoo19c: :557-772``
# ═══════════════════════════════════════════════════════════════════════════
#
# ``related='partner_id.country_id.name'`` declara un campo cuyo valor no vive
# en su propia fila: se lee recorriendo una cadena punteada hasta el campo del
# extremo. La fuente lo resuelve dándole al campo un ``compute`` y un
# ``inverse`` propios, que son estos métodos.
#
# **Qué desbloqueó este porte, y por qué se hizo en este orden.** El recorrido
# escribe ``record[self.name] = ...`` y lee ``record[name]``: sin el acceso por
# clave (``orm/models.py``, ``api@35012013``) sería código que no puede correr.
# Y ``setup_related`` recorre ``model._fields[name]`` por una cadena que puede
# atravesar un ``One2many``, que no es concreto: con el mapa filtrado por
# ``concrete`` esa cadena no se podía recorrer (``api@b7856a6b``, tarea #215).
# Los dos son primitivas, y las dos se construyeron antes que este bloque.


def _field_prepare_setup(self):
    """≙ ``Field.prepare_setup`` (``:523``) — verbatim."""
    self._setup_done = False


models.Field.prepare_setup = _field_prepare_setup


def _field_setup_nonrelated(self, model):
    """≙ ``Field.setup_nonrelated`` (``:557``) — «determine the dependencies
    and inverse field(s)».

    Verbatim: la fuente no hace nada aquí. Es el gancho que sus subclases
    relacionales sobreescriben, y se porta con su cuerpo vacío porque el
    símbolo ES el contrato — quitarlo obligaría a cada subclase a saber si su
    base lo declara.
    """


models.Field.setup_nonrelated = _field_setup_nonrelated


def _field_traverse_related(self, record):
    """≙ ``Field.traverse_related`` (``:666``) — «traverse the fields of the
    related field ``self`` except for the last one, and return it as a pair
    ``(last_record, last_field)``».

    Verbatim, incluido el ``next(iter(corecord), corecord)``: al atravesar una
    relación de varios se toma el primero, y si no hay ninguno se conserva el
    contenedor vacío para que el llamador distinga «no hay» de «no se
    recorrió».
    """
    for name in self.related.split('.')[:-1]:
        corecord = record[name]
        record = next(iter(corecord), corecord)
    return record, self.related_field


models.Field.traverse_related = _field_traverse_related


def _field_process_related(self, value, env):
    """≙ ``Field._process_related`` (``:720``) — «no transformation by default,
    but allows override».

    Se porta aunque no transforme nada: es el punto de extensión que las
    subclases usan, y el docstring de la fuente lo dice de sí mismo.
    """
    return value


models.Field._process_related = _field_process_related


def _field_compute_related(self, records):
    """≙ ``Field._compute_related`` (``:675``) — «compute the related field
    ``self`` on ``records``».

    **El orden del recorrido es el contrato, no un detalle.** La fuente
    atraviesa TODOS los registros en un campo antes de pasar al siguiente
    campo, no cada registro en todos sus campos, y dedica veinte líneas de
    comentario a explicar por qué: recorrer campo a campo deja que la
    prelectura resuelva el campo para todo el lote de una vez, y recorrer
    registro a registro lo pide de uno en uno. Su comentario lo llama *«a
    major impact on performance»*.

    Se conserva ese orden aunque aquí la prelectura la haga
    ``select_related``/``prefetch_related`` de Django y no el ORM: el orden es
    lo que la deja funcionar, y invertirlo la anularía en silencio — el N+1
    no rompe nada, sólo cuesta.
    """
    values = list(records)
    for name in self.related.split('.')[:-1]:
        values = [next(iter(value := element[name]), value) for element in values]
    for record, value in zip(records, values):
        record[self.name] = self._process_related(
            value[self.related_field.name], get_environment())


models.Field._compute_related = _field_compute_related


def _field_inverse_related(self, records):
    """≙ ``Field._inverse_related`` (``:724``) — «inverse the related field
    ``self`` on ``records``».

    La primera línea guarda los valores antes de tocar nada, y la fuente
    explica por qué en su comentario: *«store record values, otherwise they
    may be lost by cache invalidation»*. Escribir en el extremo de la cadena
    invalida la caché del origen, así que leer después de escribir devolvería
    otra cosa.

    La guarda ``bool(target.id) == bool(record.id)`` también es verbatim: sólo
    se propaga entre dos registros que sean ambos reales o ambos nuevos. Un
    registro sin guardar no puede escribir en uno guardado.
    """
    record_value = {record: record[self.name] for record in records}
    for record in records:
        target, field = self.traverse_related(record)
        if target and bool(target.id) == bool(record.id):
            target[field.name] = record_value[record]


models.Field._inverse_related = _field_inverse_related


# ═══════════════════════════════════════════════════════════════════════════
# ``related=`` — el campo que proyecta el valor del extremo de una cadena
# ═══════════════════════════════════════════════════════════════════════════
#
# ≙ ``Field.setup_related`` (``odoo19c: :604-660``) y ``Field._search_related``
# (``:735-772``), más las cinco properties ``_related_*`` (``:774-778``).
#
# **Por qué se construye y no se declina.** Sobre los 120 addons que este
# árbol porta la referencia declara centenares de campos ``related=``, y la
# inmensa mayoría **sin ``store``**. No es un puñado de casos aislados — es un
# mecanismo. Dos bloques de prosa de este árbol lo declinaban dando como razón
# que un ``related`` es «una copia que puede divergir», y eso describe
# ``store=True``, que casi ninguno lleva.
#
# El reparto **no se transcribe aquí**: crece con la referencia, y una cifra
# copiada a prosa es la segunda fuente de verdad que
# ``calibration-verified-numbers.md`` prohíbe. Lo publica
# ``python3 scripts/census_related_fields.py``; la forma se ejerce en
# ``tests/unit/orm/test_related_shape_in_the_reference.py``.
#
# **Qué diverge, y es de mecanismo.** El ``setup_related`` de la fuente usa su
# registro por base (``model.pool``, ``field._setup_done`` + ``field.setup()``,
# ``field_setup_dependents``) para asegurar que cada eslabón esté listo antes
# de recorrerlo. Aquí quien liga los campos es Django, al construir la clase:
# cuando este código corre, la cadena ya está resuelta. Por eso el recorrido es
# directo y no hay fase de espera que replicar. Los ``_extra_keys__`` y
# ``_modules`` de ``:650-663`` son del cargador de módulos de la fuente, que
# este árbol no tiene: su desenlace es divergencia de mecanismo declarada.


def walk_related_chain(field, model):
    """Los campos que ``field.related`` atraviesa, de origen a destino.

    ≙ el recorrido de ``setup_related`` (``:608-617``), que allá lee
    ``model.pool[model_name]._fields[name]``.

    **La referencia no declara este símbolo**: inlinea el mismo recorrido dos
    veces, en ``setup_related`` (``:608-617``) y en ``_search_related``
    (``:757-762``). Aquí es uno solo, y **público** porque
    :mod:`orm.domains` lo importa — no hay contrato de visibilidad de la
    fuente que preservar, y un ``_nombre`` importado entre módulos sería el
    defecto que PEP 8 nombra.

    **Divergencia de mecanismo, medida:** aquí ``_fields`` es una ``property``
    de **instancia** (``orm/models.py:1355``), y este recorrido corre sobre la
    **clase** — Django liga los campos al construirla, así que no hay fase de
    espera que replicar. El cuerpo de esa property es
    ``{f.name: f for f in self._meta.get_fields()}``, y eso es exactamente lo
    que se consulta: el mismo registro, alcanzado desde la clase.

    Lanza ``KeyError`` nombrando el eslabón que falta, como la fuente
    (``:611-615``).
    """
    field_seq, current = [], model
    for name in field.related.split('.'):
        by_name = {f.name: f for f in current._meta.get_fields()}
        link = by_name.get(name)
        if link is None:
            raise KeyError(
                f'El campo {name} de la definición related de {field.name} '
                f'no existe en {current.__name__}.')
        field_seq.append(link)
        current = getattr(link, 'related_model', None) or current
    return field_seq


def _field_setup_related(self, model):
    """≙ ``Field.setup_related`` (``:604-660``) — «setup the attributes of a
    related field».

    Deja instaladas las tres funciones que hacen del campo una proyección:
    ``compute`` para leerlo, ``inverse`` para escribirlo, y ``search`` para
    **buscarlo** — que es la que se perdía al navegar la cadena por la FK a
    mano.
    """
    if not isinstance(self.related, str):
        raise TypeError(f'related debe ser una ruta punteada, no {self.related!r}')

    field_seq = walk_related_chain(self, model)

    #: ``:622-624`` — el related y su destino son del mismo tipo, o la
    #: proyección miente. Aquí el tipo lo publica la ``property`` ``type``
    #: (``:1327``), que despacha por conducta y no por clase: un ``CharField``
    #: con ``choices`` es ``selection`` y sin ellas ``char``, distinción que
    #: la clase de Django no expresa por sí sola.
    if self.type != field_seq[-1].type:
        raise TypeError(
            f'El tipo del campo related {self.name} ({self.type}) no coincide '
            f'con el de su destino {field_seq[-1].name} '
            f'({field_seq[-1].type}).')

    self.related_field = field_seq[-1]

    self.compute = self._compute_related
    #: ``:632`` — sin inverso si el campo o su destino son de sólo lectura.
    #: ``inherited`` y ``readonly`` se leen directos, sin ``getattr`` con
    #: defecto: los instala :data:`_FIELD_CLASS_ATTRIBUTES` sobre
    #: ``models.Field``, así que existen siempre. Un ``getattr`` defensivo
    #: aquí escondería su desaparición en vez de delatarla.
    if self.inherited or not (self.readonly or field_seq[-1].readonly):
        self.inverse = self._inverse_related
    #: ``:634-636`` — buscable sólo si NO se guarda (con columna propia se
    #: busca por ella) y si cada eslabón lo es. El defecto de ``store`` es
    #: ``True``, así que un campo que quiera la búsqueda por cadena declara
    #: ``store=False`` — que es la forma de casi todos los ``related=`` de la
    #: referencia (reparto: ``python3 scripts/census_related_fields.py``).
    if not self.store and all(f._description_searchable for f in field_seq):
        self.search = self._search_related

    #: ``:640-641`` — un related de sólo lectura y sin inverso no puede
    #: honrar un default: nadie escribiría ese valor. La fuente avisa en vez
    #: de reventar, y aquí igual. El centinela de «sin default» en Django es
    #: ``NOT_PROVIDED``, no ``None``: un ``default=None`` declarado es un
    #: default real.
    if (self.default is not models.NOT_PROVIDED
            and self.readonly and not self.inverse):
        _logger.warning('Default redundante en %s', self.name)

    #: ``:643-647`` — copiar del destino lo que el related no declare por sí.
    for attribute, prop in self.related_attrs:
        if attribute not in self.__dict__ and prop.startswith('_related_'):
            setattr(self, attribute, getattr(field_seq[-1], prop, None))


models.Field.setup_related = _field_setup_related


#: ``_search_related`` (``:735-772``) **se instala desde**
#: :mod:`orm.domains`, no aquí, y la razón es una divergencia medida de
#: **dirección de import**, no una preferencia:
#:
#: ==================  ==========================================
#: La referencia       ``fields`` → ``domains`` (``odoo/orm/fields.py:24``),
#:                     y la vuelta sólo bajo ``TYPE_CHECKING``
#:                     (``odoo/orm/domains.py:73``).
#: Aquí                al revés — ``domains`` importa de ``fields``
#:                     ``condition_to_q``, ``falsy_value`` y
#:                     ``NEGATIVE_CONDITION_OPERATORS``.
#: ==================  ==========================================
#:
#: La inversión la causan esos tres símbolos, que la fuente **no tiene como
#: función de módulo**: allá ``falsy_value`` es un atributo del campo y el
#: compilador de hojas vive en ``Domain._to_q``. Con la dirección invertida,
#: un cuerpo que construya ``Domain`` no cabe en este archivo, y un import
#: dentro de la función está prohibido (``no-lazy-imports.md``).
#:
#: Enderezarla es la tarea **#380**, la misma que ``_NEGATIVE_LIKE_OPERATORS``
#: ya citaba: unificar los tres en un hogar compartido devuelve la dirección
#: de la fuente y trae este cuerpo a su archivo. Hasta entonces la instalación
#: cruzada es la misma vía por la que ``determine_domain`` llega a
#: ``NonStored``. :func:`_field_setup_related` lo referencia por ``self``, así
#: que el orden de instalación no importa: cuando el campo se configura, el
#: método ya está colgado.


#: ``:774-778`` — de dónde copia ``setup_related`` cada atributo. Son
#: properties allá y funciones aquí por la misma razón que el resto del
#: parche: se cuelgan de ``models.Field``, que no se puede reabrir con
#: ``property`` sin pisar lo que Django ya declare con ese nombre.
models.Field._related_comodel_name = property(
    lambda self: getattr(self, 'comodel_name', None))
models.Field._related_string = property(lambda self: self.string)
models.Field._related_help = property(lambda self: getattr(self, 'help', None))
models.Field._related_groups = property(
    lambda self: getattr(self, 'groups', None))
models.Field._related_aggregator = property(lambda self: self.aggregator)


def _field_setup(self, model):
    """≙ ``Field.setup`` (``:526-542``) — el despachador de las dos ramas.

    La fuente valida antes sus ``_extra_keys__`` contra
    ``_valid_field_parameter``; aquí no hay cargador de módulos que los
    aporte, así que esa mitad es divergencia de mecanismo declarada. Lo que sí
    se porta es la bifurcación, que es el contrato: un campo con ``related``
    va por un camino y el resto por el otro.
    """
    if getattr(self, '_setup_done', False):
        return
    if self.related:
        self.setup_related(model)
    else:
        self.setup_nonrelated(model)
    self._setup_done = True


models.Field.setup = _field_setup


def _field_resolve_depends(self, registry_module):
    """≙ ``Field.resolve_depends`` (``:807``) — «return the dependencies of
    ``self`` as a collection of field tuples».

    Cada dependencia declarada es un nombre punteado; esto la resuelve a la
    tupla de campos que la recorre, para que quien invalide sepa qué tocar.

    El parámetro se llama ``registry_module`` y no ``registry`` porque aquí el
    registro es un **módulo** (``orm.registry``) y no la instancia por base de
    la fuente — la divergencia está declarada en la cabecera de ese archivo.

    **Dos vías para llegar al modelo, y la de Django va primero.** La fuente
    resuelve por ``self.model_name``, el nombre punteado que su ORM le pone al
    ligar el campo. Aquí quien liga el campo es Django, y lo que deja es
    ``field.model`` — la clase, directamente. ``model_name`` sólo lo lleva un
    campo cuyo puerto se lo haya declarado, así que preguntar sólo por él
    dejaría fuera a todo campo ligado por Django, que son todos.
    """
    model = getattr(self, 'model', None)
    if model is None:
        model = registry_module.MODELS_BY_NAME.get(self.model_name)
    if model is None:
        return
    for dotnames in registry_module.field_depends[self]:
        field_sequence = []
        current = model
        for fname in dotnames.split('.'):
            # ``_meta.get_field`` y no ``_fields``: aquí se recorren CLASES, y
            # sobre la clase ``_fields`` es el objeto ``property``, no el mapa.
            # Es el mismo registro por la vía que sí funciona sin instancia.
            field = None
            if current is not None:
                try:
                    field = current._meta.get_field(fname)
                except FieldDoesNotExist:
                    field = None
            if field is None:
                break
            field_sequence.append(field)
            related = getattr(field, 'related_model', None)
            if related is None:
                comodel = getattr(field, 'comodel_name', None)
                related = (registry_module.MODELS_BY_NAME.get(comodel)
                           if comodel else None)
            current = related
        else:
            yield tuple(field_sequence)


models.Field.resolve_depends = _field_resolve_depends


# ═══════════════════════════════════════════════════════════════════════════
# ``determine_domain`` — la condición que un campo traduce por sí mismo
# ═══════════════════════════════════════════════════════════════════════════
#
# ≙ ``Field.determine_domain`` (``odoo19c: odoo/orm/fields.py:1926-1928``),
# cuyo cuerpo entero es ``determine(self.search, records, operator, value)``.
#
# Es la puerta del camino ``search=``: un campo que declara ``search`` no se
# compila a SQL, porque puede no tener columna; en su lugar **devuelve un
# dominio** que sustituye a la condición y se compone con el resto igual que
# cualquier otro. Un ``QuerySet`` no puede hacerlo — no se puede meter dentro
# de un ``any`` ni negar sin materializar—, y ésa es la razón por la que la
# forma de retorno importa y no es un detalle de estilo.
#
# Se instala sobre DOS clases, y la duplicación es del stack, no del contrato:
#
# - ``models.Field`` — los campos con columna, que hoy no declaran ``search``
#   pero heredan el protocolo para cuando lo declaren.
# - ``NonStored`` — los campos sin columna, que son quienes lo necesitan hoy
#   (``display_name`` es el primero). No es un ``models.Field``, así que
#   heredar no lo alcanza.
#
# La instalación va aquí y no en ``fields_nonstored`` porque este módulo lo
# importa por la vía de ``fields_numeric``: el import inverso sería un ciclo.
# Es la misma vía por la que ``type`` y ``relational`` llegan a
# ``models.Field``.


def determine_domain(field, records, operator, value):
    """El dominio que sustituye a una condición sobre ``field``.

    Devuelve ``NotImplemented`` cuando el campo no declara ``search``: es la
    misma señal con que la fuente dice *"este operador no lo soporto"* y deja
    al despachador probar sus respaldos, en vez de un error que cortaría la
    escalera antes del primer peldaño.
    """
    search = getattr(field, 'search', None)
    if search is None:
        return NotImplemented
    return determine(search, records, operator, value)


models.Field.determine_domain = determine_domain
NonStored.determine_domain = determine_domain


############################################################################
#
# Cache management methods — ≙ ``odoo19c: odoo/orm/fields.py:1520-1630``
#
# El almacén es ``Transaction.field_data``, que existía desde el porte de
# ``environments.py`` y hasta aquí no tenía **ningún** consumidor: medido,
# 0 lecturas fuera de su propio módulo. Esta sección es quien lo estrena.
#
# Veredicto por el criterio de las dos categorías:
#
# - **el stack lo trae hecho**: ``collections.deque(maxlen=0)`` para drenar
#   un ``map`` en C, ``collections.ChainMap`` para fusionar los cubos de un
#   campo con contexto, y ``defaultdict`` para el mapa por campo. Los tres
#   de ``cpython``; se llaman y ya.
# - **el stack tiene con qué construirlo**: la caché en sí. Django no tiene
#   almacén de valor por campo y por transacción —el suyo es por instancia,
#   en ``_state.fields_cache``, y muere con el objeto—, pero las primitivas
#   están y no hace falta ninguna dependencia de fuera.
#
# La adaptación de firma es UNA y se declara aquí para no repetirla en cada
# método: donde la fuente escribe ``records._ids``, aquí va
# ``record_ids(records)``. No hay recordset en este stack — ver el docstring
# de :func:`~orm.utils.record_ids` —; el resto del cuerpo es el de la fuente.
############################################################################


def _has_context_buckets(field):
    """Si el campo separa su caché por clave de contexto.

    ≙ ``self in env._field_depends_context`` de la fuente. Allá el registro
    guarda el conjunto; aquí lo responde el mismo mapa derivado que ya
    existía, ``registry.field_depends_context``.
    """
    return field in field_depends_context


def _get_cache(self, env):
    """La caché del campo: un mapa mutable de id a valor.

    ≙ ``Field._get_cache`` (``:1525``). Docstring de la fuente: *"Calling
    this function multiple times, always returns the same mapping instance
    for a given environment, unless the transaction was entirely
    invalidated."* Esa promesa sostiene el resto — quien recibe el mapa
    escribe en él y espera que la escritura se vea.
    """
    transaction = env.transaction
    memo_key = (self, env.cache_key(self) if _has_context_buckets(self) else None)
    try:
        return transaction.field_cache_memo[memo_key]
    except KeyError:
        field_cache = self._get_cache_impl(env)
        transaction.field_cache_memo[memo_key] = field_cache
        return field_cache


def _get_cache_impl(self, env):
    """≙ ``Field._get_cache_impl`` (``:1541``) — puede dar una vista del
    almacén real, según lo que el campo necesite."""
    cache = env.transaction.field_data[self]
    if _has_context_buckets(self):
        cache = cache.setdefault(env.cache_key(self), {})
    return cache


def _invalidate_cache(self, env, ids=None):
    """≙ ``Field._invalidate_cache`` (``:1550``) — invalida los ids dados, o
    todos si ``ids`` es ``None``.

    Lee ``field_data.get`` y no el corchete a propósito: sobre un
    ``defaultdict`` el corchete **crea** la entrada, y un campo que nadie ha
    tocado quedaría con un cubo vacío por el mero hecho de invalidarlo.
    """
    cache = env.transaction.field_data.get(self)
    if not cache:
        return

    caches = cache.values() if _has_context_buckets(self) else (cache,)
    for field_cache in caches:
        if ids is None:
            field_cache.clear()
            continue
        for id_ in ids:
            field_cache.pop(id_, None)


def _get_all_cache_ids(self, env):
    """Todos los ids con valor en caché, en cualquier entorno.

    ≙ ``Field._get_all_cache_ids`` (``:1564``). El ``ChainMap`` es el truco
    de la fuente para *"cheaply merge"* las claves de los cubos sin copiar
    ninguno.
    """
    cache = env.transaction.field_data[self]
    if _has_context_buckets(self):
        return collections.ChainMap(*cache.values())
    return cache


def _cache_missing_ids(self, records):
    """≙ ``Field._cache_missing_ids`` (``:1572``) — los ids sin valor en
    caché."""
    field_cache = self._get_cache(get_environment())
    return (id_ for id_ in record_ids(records) if id_ not in field_cache)


def _insert_cache(self, records, values):
    """Rellena la caché SIN pisar lo que ya hay.

    ≙ ``Field._insert_cache`` (``:1595``). El ``setdefault`` no es un
    detalle: la fuente lo explica —*"this enables to keep the pending
    updates of records, and flush them later"*—. Una asignación borraría una
    escritura pendiente y la fila se guardaría con el valor leído de la base.

    El ``deque(maxlen=0)`` es el drenaje en C que la fuente mide un 15 % más
    rápido que el bucle equivalente; se porta igual, porque es el stack quien
    lo trae hecho.
    """
    field_cache = self._get_cache(get_environment())
    collections.deque(
        map(field_cache.setdefault, record_ids(records), values), maxlen=0)


def _update_cache(self, records, cache_value, dirty=False):
    """Escribe el valor en caché y, si se pide, marca el campo sucio.

    ≙ ``Field._update_cache`` (``:1609``). Docstring de la fuente: *"One can
    normally make a clean field dirty but not the other way around. Updating
    a dirty field without ``dirty=True`` is a programming error and logs an
    error."* Se porta el **registro**, no una excepción: la fuente elige no
    lanzar, y lanzar aquí cambiaría el contrato de todo escritor.
    """
    env = get_environment()
    field_cache = self._get_cache(env)
    ids = record_ids(records)
    for id_ in ids:
        field_cache[id_] = cache_value

    # ``dirty`` sólo tiene sentido para un campo con columna y almacenado.
    if self.column_type and self.store:
        if dirty:
            env.transaction.field_dirty[self].update(id_ for id_ in ids if id_)
        else:
            dirty_ids = env.transaction.field_dirty.get(self)
            if dirty_ids and not dirty_ids.isdisjoint(ids):
                _logger.error(
                    "Field._update_cache() updating the value on %s.%s where "
                    "dirty flag is already set",
                    records, self.name, stack_info=True,
                )


############################################################################
#
# Computation of field values — ≙ ``odoo19c: odoo/orm/fields.py:1845-1918``
#
############################################################################


def _as_record_list(records):
    """Las filas de ``records`` como lista.

    La contraparte de :func:`~orm.utils.record_ids` para cuando hace falta el
    objeto y no el id — el cómputo se invoca sobre la fila, no sobre su clave.
    """
    if records is None:
        return []
    if isinstance(records, models.Model):
        return [records]
    return list(records)


def _invoke_compute_method(field, records):
    """Llama al método que ``field.compute`` nombra, sobre cada fila.

    ≙ ``BaseModel._compute_field_value`` (``odoo19c: odoo/orm/models.py``) en
    lo que este stack necesita. La fuente lo invoca sobre el *recordset*
    entero y el método itera por dentro con ``for record in self``; aquí la
    unidad es la instancia, así que el bucle vive de este lado y el método
    recibe una fila. Es la misma adaptación de :func:`~orm.utils.record_ids`,
    vista desde el otro lado.
    """
    for record in _as_record_list(records):
        getattr(record, field.compute)()


def recompute(self, records):
    """Procesa los cómputos pendientes de este campo sobre ``records``.

    ≙ ``Field.recompute`` (``:1850``). Sólo se llama si el campo es calculado
    y almacenado.

    **Dos divergencias de mecanismo, las dos con su motivo medido y su
    sucesor** — ninguna recorta el comportamiento observable del campo:

    1. *Sin lote de prelectura.* La fuente agrupa los pendientes en ventanas
       de ``PREFETCH_MAX`` con ``expand_ids`` y computa la ventana entera de
       una vez. Aquí el cómputo se invoca por fila (ver
       :func:`_invoke_compute_method`), así que la ventana no ahorraría ni
       una consulta: agruparla sería ceremonia. Vuelve a tener sentido el día
       que el cómputo reciba un ``QuerySet``, que es la tarea **#306**.
    2. *Sin reintento por fila ausente.* La fuente envuelve cada cómputo en
       ``apply_except_missing``: ante un ``MissingError`` reintenta sobre
       ``records.exists()`` y desmarca los que ya no existen *"otherwise they
       remain to compute forever, which may lead to an infinite loop"*. Aquí
       no hay ``MissingError`` — una fila borrada no se detecta al tocarla,
       sino al consultarla — y el equivalente exige el lado de lectura del
       motor, que es la capa C. Sucesor: tarea **#307**.
    """
    to_compute_ids = get_environment().transaction.tocompute.get(self)
    if not to_compute_ids:
        return

    pending = [record for record in _as_record_list(records)
               if record.pk in to_compute_ids]
    if not pending:
        return

    if self.recursive:
        # Un calculado recursivo se computa fila a fila, para que sus
        # dependencias internas se resuelvan en orden. Aquí el no-recursivo
        # también va fila a fila (divergencia 1 del docstring), así que las
        # dos ramas coinciden; la condición se conserva porque es donde
        # aterriza el lote cuando #306 lo construya.
        for record in pending:
            self.compute_value(record)
        return

    for record in pending:
        self.compute_value(record)


def compute_value(self, records):
    """Invoca el método de cómputo; el resultado queda en caché.

    ≙ ``Field.compute_value`` (``:1897``).

    El orden importa, y la fuente lo razona: desmarca el cómputo **antes** de
    correrlo *"just in case the compute method does not assign a value"* y
    porque el propio método puede leer el valor viejo, lo que dispararía una
    lectura que volvería a computar el campo — recursión infinita. Si el
    cómputo revienta, se vuelve a marcar y se relanza.

    ``compute_sudo`` no eleva aquí con ``records.sudo()`` —no hay recordset
    que elevar— sino con el alcance de elevación del entorno, que es el
    mecanismo equivalente de este stack (``orm.environments.sudo``).
    """
    env = get_environment()
    ids = record_ids(records)
    fields = registry_field_computed[self]

    for field in fields:
        if field.store:
            env.remove_to_compute(field, ids)

    try:
        with env.protecting(fields, ids):
            if self.compute_sudo:
                with elevate_privileges():
                    _invoke_compute_method(self, records)
            else:
                _invoke_compute_method(self, records)
    except Exception:
        for field in fields:
            if field.store:
                env.add_to_compute(field, ids)
        raise


for _cache_method in (_get_cache, _get_cache_impl, _invalidate_cache,
                      _get_all_cache_ids, _cache_missing_ids, _insert_cache,
                      _update_cache, recompute, compute_value):
    setattr(models.Field, _cache_method.__name__, _cache_method)
