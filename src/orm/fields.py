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
from decimal import Decimal

from django.db import models

from tools.sql import SQL

from orm.fields_binary import Binary, Image                    # noqa: F401
from orm.fields_misc import Boolean, Json                      # noqa: F401
from orm.fields_numeric import Float, Integer, Monetary        # noqa: F401
from orm.fields_properties import (                            # noqa: F401
    Properties,
    PropertiesDefinition,
)
from orm.fields_reference import Many2oneReference, Reference  # noqa: F401
from orm.fields_relational import Many2many, Many2one, One2many  # noqa: F401
from orm.fields_selection import Selection                     # noqa: F401
from orm.fields_temporal import Date, Datetime                 # noqa: F401
from orm.fields_textual import Char, Html, Text                # noqa: F401

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
# El orden de la tabla importa poco pero no es arbitrario: en Django
# ``AutoField`` hereda de ``IntegerField`` (falsy 0, ≙ el ``Id`` de la fuente) y
# ``EmailField``/``SlugField``/``URLField`` heredan de ``CharField`` (falsy '').

_FALSY_VALUE_BY_FIELD_CLASS = (
    (models.BooleanField, False),
    (models.IntegerField, 0),
    (models.FloatField, 0.0),
    (models.DecimalField, Decimal('0')),
    (models.CharField, ''),
    (models.TextField, ''),
)


def falsy_value(field):
    """El valor que cuenta como *no establecido* — ≙ ``Field.falsy_value``.

    Devuelve ``None`` cuando el campo no tiene ninguno, que es el defecto de la
    fuente y también lo que se responde ante un campo desconocido: es la
    hipótesis conservadora, porque ``falsy_value is None`` es lo que hace que
    ``_negate`` añada la rama ``OR campo IS NULL``.
    """
    if field is None:
        return None
    for field_class, value in _FALSY_VALUE_BY_FIELD_CLASS:
        if isinstance(field, field_class):
            return value
    return None


# El subconjunto de ``NEGATIVE_CONDITION_OPERATORS`` que la familia ``like``
# usa. La fuente lo lee de ``Domain.NEGATIVE_OPERATORS`` (``:1331``), pero
# importarlo aquí cierra un ciclo —``domains`` ya importa de este módulo—, y un
# import dentro de la función está prohibido (``no-lazy-imports.md``). Unificar
# los dos en un hogar compartido es la tarea **#380**.
_NEGATIVE_LIKE_OPERATORS = frozenset([
    'not like', 'not ilike', 'not =like', 'not =ilike',
])

_INEQUALITY_LOOKUP = {'<': 'lt', '>': 'gt', '<=': 'lte', '>=': 'gte'}

_COLLECTION_TYPES = (list, tuple, set, frozenset)


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
    """
    can_be_null = True if field is None else bool(field.null)
    null_value = falsy_value(field)

    # --- in / not in (igualdad) --------------------------------------------
    if operator in ('in', 'not in'):
        values = list(value) if isinstance(value, _COLLECTION_TYPES) else [value]
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

    La rama ``company_dependent`` de la fuente no tiene contraparte todavía:
    ese mecanismo es la tarea **#111**, y hasta que exista no hay campo que
    entre por ella.
    """
    if not getattr(self, 'concrete', False) or not getattr(self, 'column', None):
        raise ValueError(f"Cannot convert {self} to SQL because it is not stored")
    return SQL.identifier(alias, self.column, to_flush=self)


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
