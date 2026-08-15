"""Dominios del ORM — fiel a ``odoo/orm/domains.py`` (Odoo 19).

Un dominio es una expresión lógica de primer orden sobre un modelo. La fuente
la representa como un **AST** —constantes booleanas, negación, n-arios AND/OR y
condiciones ``(campo, operador, valor)``— y conserva la notación polaca
histórica (``['&', '!', cond1, '|', cond2, cond3]``) sólo como forma de entrada
y salida.

Aquí, con el prefijo ``odoo.`` eliminado (``orm`` ≙ ``odoo/orm``), esta es la
**definición**; ``src/osv/expression.py`` (≙ ``odoo/osv/expression.py``) la
re-exporta.

Adaptado de Odoo Community ``odoo/orm/domains.py`` (LGPL-3) — atribución y
aviso de licencia preservados (DEC-KX-03).

Por qué el AST y no el mapa de operadores que había
====================================================

Hasta ``api@103a4c1f`` este archivo tenía 119 líneas y compilaba **cada hoja a
un** ``Q`` **en el acto**. Eso perdía la estructura que la fuente necesita para
empujar la negación hasta las hojas, y con ella se perdían estas cosas:

1. **El leaf FALSO** ``(0, '=', 1)`` reventaba con ``FieldError``: el mapa
   atendía el verdadero y olvidaba el falso (:ref:`h-api-613`).
2. **Cuatro de los catorce** ``STANDARD_CONDITION_OPERATORS`` no existían
   (``=like``, ``not =like``, ``=ilike``, ``not =ilike``) — mismo hallazgo.
3. **La ruta con punto no llegaba a ninguna parte.**
   ``[('picking_id.picking_type_id', '=', v)]``, que ``stock_move_line.py:503``
   construye, se pasaba tal cual a ``Q(**{'a.b__exact': v})`` y Django no
   resuelve el punto: es ``__`` lo que atraviesa la relación
   (:ref:`h-api-614`).
4. **``not in`` con ``False`` incluía la fila sin valor**, y la fuente la
   excluye. Es la divergencia real ante NULL, y va en dirección contraria a la
   que la premisa de esta iniciativa afirmaba — ver abajo.

La premisa sobre NULL estaba invertida
=======================================

El ``alcance`` abrió declarando que Django emite ``NOT (cond)`` y pierde la
fila sin valor. **Medido, es falso.** El compilador de Django añade la guarda
él mismo::

    ~Q(user_type__sql_like='%a%')   # columna nulable
    -> NOT ("user_type"::text LIKE %a% AND "user_type" IS NOT NULL)

que es la regla de la fuente con otra forma: la fila sin valor **entra**. La
premisa se midió con ``psql`` sobre ``NOT (NULL LIKE 'X')`` —cifra correcta— y
se concluyó sobre lo que Django emite, que el instrumento no podía ver. El
episodio queda en :ref:`h-api-614`; el detalle de qué sí diverge está en el
docstring de ``fields.condition_to_q``.

Qué se porta y qué no
=====================

Se portan las **nueve clases** del AST con sus 84 símbolos, el parseo de la
notación polaca, el álgebra booleana, el empuje de la negación a las hojas y la
compilación. Quedan fuera, declarados:

- **Los 39 optimizadores de módulo** (``_operator_equal_as_in``,
  ``_optimize_in_set``, ``_optimize_like_str``, la jerarquía ``child_of``…).
  Su veredicto por función es la tarea **#373**. Consecuencia visible: la
  normalización de ``=``/``!=`` a ``in``/``not in`` que allá hace
  ``_operator_equal_as_in`` aquí ocurre en ``DomainCondition._to_q``, en el
  paso de compilación, porque sin ella el compilador de hoja no recibiría el
  operador que la fuente le promete.
- **Los seis** ``_as_predicate`` y ``DomainCondition._optimize_field_search_method``
  — siete símbolos. Su consumidor en la fuente es ``Model.filtered_domain``
  (filtrar en memoria en vez de en SQL), que **no existe en este árbol**:
  ``grep -rn "filtered_domain" src/ addons/`` da 0. Portarlos exigiría antes
  ``Field.filter_function`` y ``Field.expression_getter``, también ausentes.
  Sucesor: tarea **#373** los cubre junto al resto de la capa.

La adaptación de forma, declarada
==================================

``_to_sql(model, alias, query) -> SQL`` es ``_to_q(model) -> Q``. La fuente
compone el ``WHERE`` a mano y arrastra el alias de tabla y la ``Query``; aquí lo
compone el ORM a partir del ``Q``, así que ni el alias ni la query viajan por
esta capa. El nombre cambia porque el tipo de retorno cambia — llamarlo
``_to_sql`` y devolver un ``Q`` sería peor que renombrarlo.
"""
import enum
import functools
import itertools
import operator as operator_module

from django.core.exceptions import FieldDoesNotExist
from django.db.models import Q

from orm.fields import condition_to_q, falsy_value
from tools.func import classproperty

__all__ = [
    'Domain', 'DomainBool', 'DomainNot', 'DomainNary', 'DomainAnd', 'DomainOr',
    'DomainCustom', 'DomainCondition', 'OptimizationLevel',
    'AND', 'OR', 'NOT', 'TRUE_DOMAIN', 'FALSE_DOMAIN', 'to_q',
]

STANDARD_CONDITION_OPERATORS = frozenset([
    'any', 'not any',
    'any!', 'not any!',
    'in', 'not in',
    '<', '>', '<=', '>=',
    'like', 'not like',
    'ilike', 'not ilike',
    '=like', 'not =like',
    '=ilike', 'not =ilike',
])
"""Los catorce operadores estándar de condición — ≙ ``domains.py:81-90``."""

CONDITION_OPERATORS = set(STANDARD_CONDITION_OPERATORS) | {'=', '!=', '<>', '=='}
"""Los aceptados al construir. Los cuatro extra los normaliza la compilación.

La fuente los admite igual y los reduce con optimizadores de módulo
(``_operator_equal_as_in``, ``_operator_different``, ``_operator_equals``);
mientras esa capa no exista (tarea **#373**) la reducción vive en
``DomainCondition._to_q``.
"""

INTERNAL_CONDITION_OPERATORS = frozenset(('any!', 'not any!'))

NEGATIVE_CONDITION_OPERATORS = {
    'not any': 'any',
    'not any!': 'any!',
    'not in': 'in',
    'not like': 'like',
    'not ilike': 'ilike',
    'not =like': '=like',
    'not =ilike': '=ilike',
    '!=': '=',
    '<>': '=',
}
"""Los operadores de semántica negativa, mapeados a su positivo."""

_INVERSE_OPERATOR = {
    # desde NEGATIVE_CONDITION_OPERATORS
    'not any': 'any',
    'not any!': 'any!',
    'not in': 'in',
    'not like': 'like',
    'not ilike': 'ilike',
    'not =like': '=like',
    'not =ilike': '=ilike',
    '!=': '=',
    '<>': '=',
    # de positivo a negativo
    'any': 'not any',
    'any!': 'not any!',
    'in': 'not in',
    'like': 'not like',
    'ilike': 'not ilike',
    '=like': 'not =like',
    '=ilike': 'not =ilike',
    '=': '!=',
}
"""Inversos de los operadores."""

_INVERSE_INEQUALITY = {
    '<': '>=',
    '>': '<=',
    '>=': '<',
    '<=': '>',
}
"""Inversos de las desigualdades. Van aparte por los valores nulos."""

_TRUE_LEAF = (1, '=', 1)
_FALSE_LEAF = (0, '=', 1)

_COLLECTION_TYPES = (list, tuple, set, frozenset)

MAX_OPTIMIZE_ITERATIONS = 1000


def _django_path(field_expr):
    """``a.b.c`` → ``a__b__c`` — la travesía de relación de Django.

    La fuente descompone la ruta en un ``any`` sobre el comodelo
    (``_optimize_any_domain``); Django la resuelve con un join en la misma
    consulta usando ``__``. Es la misma semántica para un camino to-one; para
    uno to-many difieren al negar, y por eso ``DomainCondition.__invert__``
    sigue siendo conservador con las rutas (ver su docstring).
    """
    return field_expr.replace('.', '__')


class OptimizationLevel(enum.IntEnum):
    """Hasta dónde se optimizó el dominio — ≙ ``domains.py:176-186``."""

    NONE = 0
    BASIC = enum.auto()
    DYNAMIC_VALUES = enum.auto()
    FULL = enum.auto()

    @functools.cached_property
    def next_level(self):
        assert self is not OptimizationLevel.FULL, 'FULL es el último nivel'
        return OptimizationLevel(int(self) + 1)


# --------------------------------------------------
# Definición del dominio y su manipulación
# --------------------------------------------------

class Domain:
    """El dominio como AST — ≙ ``domains.py:196``.

    Es abstracta, pero no se marca como tal: se sobreescribe ``__new__`` para
    que la clase sirva a la vez de fábrica de los distintos tipos y de tipo
    para ``isinstance``, igual que en la fuente.
    """

    __slots__ = ('_opt_level',)

    def __new__(cls, *args, internal=False):
        """Construye el AST — ≙ ``domains.py:206-275``.

        Con más de un argumento son tres: campo, operador y valor. Con uno solo
        es un ``Domain``, un booleano, o la lista en notación polaca.
        """
        if len(args) > 1:
            if isinstance(args[0], str):
                return DomainCondition(*args).checked()
            if args == _TRUE_LEAF:
                return _TRUE_DOMAIN
            if args == _FALSE_LEAF:
                return _FALSE_DOMAIN
            raise TypeError(f'Domain() argumentos inválidos: {args!r}')

        arg = args[0]
        if isinstance(arg, Domain):
            return arg
        if arg is True or arg == []:
            return _TRUE_DOMAIN
        if arg is False:
            return _FALSE_DOMAIN
        if arg is NotImplemented:
            raise NotImplementedError

        if not isinstance(arg, (list, tuple)):
            raise TypeError(f'Domain() tipo inválido de dominio: {arg!r}')
        stack = []
        try:
            for item in reversed(arg):
                if isinstance(item, (tuple, list)) and len(item) == 3:
                    op = item[1].lower() if isinstance(item[1], str) else item[1]
                    if internal:
                        if (op in ('any', 'any!', 'not any', 'not any!')
                                and isinstance(item[2], (list, tuple))):
                            item = (item[0], item[1], Domain(item[2], internal=True))
                    elif op in INTERNAL_CONDITION_OPERATORS:
                        raise ValueError(f'Domain() item inválido: {item!r}')
                    stack.append(Domain(*item))
                elif item == DomainAnd.OPERATOR:
                    stack.append(stack.pop() & stack.pop())
                elif item == DomainOr.OPERATOR:
                    stack.append(stack.pop() | stack.pop())
                elif item == DomainNot.OPERATOR:
                    stack.append(~stack.pop())
                elif isinstance(item, Domain):
                    stack.append(item)
                else:
                    raise ValueError(f'Domain() item inválido: {item!r}')
            if len(stack) == 1:
                return stack[0]
            return Domain.AND(reversed(stack))
        except IndexError:
            raise ValueError(f'Domain() dominio malformado {arg!r}') from None

    @classproperty
    def TRUE(cls):
        return _TRUE_DOMAIN

    @classproperty
    def FALSE(cls):
        return _FALSE_DOMAIN

    NEGATIVE_OPERATORS = NEGATIVE_CONDITION_OPERATORS

    @staticmethod
    def custom(*, to_q, predicate=None):
        """Un dominio a medida — ≙ ``Domain.custom`` (``:289``).

        :param to_q: invocable ``(model) -> Q`` que implementa ``_to_q``.
        :param predicate: invocable ``(record) -> bool``; se conserva el
            parámetro para que la firma se lea contra la de la fuente, pero su
            consumidor (``filtered_domain``) no existe aquí.
        """
        return DomainCustom(to_q, predicate)

    @staticmethod
    def AND(items):
        """Conjunción de dominios — ≙ ``Domain.AND`` (``:303``)."""
        return DomainAnd.apply(Domain(item) for item in items)

    @staticmethod
    def OR(items):
        """Disyunción de dominios — ≙ ``Domain.OR`` (``:308``)."""
        return DomainOr.apply(Domain(item) for item in items)

    def __setattr__(self, name, value):
        raise TypeError('Los objetos Domain son inmutables')

    def __delattr__(self, name):
        raise TypeError('Los objetos Domain son inmutables')

    def __and__(self, other):
        if isinstance(other, Domain):
            return DomainAnd.apply([self, other])
        return NotImplemented

    def __or__(self, other):
        if isinstance(other, Domain):
            return DomainOr.apply([self, other])
        return NotImplemented

    def __invert__(self):
        return DomainNot(self)

    def _negate(self, model):
        """Propaga la negación sobre este dominio — ≙ ``:334``."""
        return ~self

    def __add__(self, other):
        """``Domain + [...]`` — concatena como listas, por compatibilidad."""
        if isinstance(other, Domain):
            return self & other
        if not isinstance(other, list):
            raise TypeError('Domain() sólo concatena listas')
        return list(self) + other

    def __radd__(self, other):
        return other + list(self)

    def __bool__(self):
        """Sólo el dominio ``[]`` era falso; se conserva esa semántica."""
        return not self.is_true()

    def __eq__(self, other):
        raise NotImplementedError

    def __hash__(self):
        raise NotImplementedError

    def __iter__(self):
        """Devuelve la lista en notación polaca."""
        yield from ()
        raise NotImplementedError

    def __reversed__(self):
        return reversed(list(self))

    def __repr__(self):
        return repr(list(self))

    def is_true(self):
        return False

    def is_false(self):
        return False

    def iter_conditions(self):
        """Recorre las condiciones simples del dominio."""
        yield from ()

    def map_conditions(self, function):
        """Aplica una función a cada condición y combina el resultado."""
        return self

    def validate(self, model):
        """Valida el dominio contra el modelo, o levanta — ≙ ``:404``."""
        self._optimize(model, OptimizationLevel.FULL)

    def optimize(self, model=None):
        """Optimizaciones básicas — ≙ ``:418``.

        Reescribe el dominio en uno lógicamente equivalente y más canónico. En
        este árbol la única reescritura viva es el **empuje de la negación a
        las hojas** más el aplanado de los n-arios; el resto de la capa es la
        tarea **#373**.
        """
        return self._optimize(model, OptimizationLevel.BASIC)

    def optimize_full(self, model=None):
        """Básicas más avanzadas — ≙ ``:436``."""
        return self._optimize(model, OptimizationLevel.FULL)

    def _optimize(self, model, level):
        """Itera hasta el punto fijo del nivel pedido — ≙ ``:449``."""
        domain, previous, count = self, None, 0
        while domain._opt_level < level:
            count += 1
            if count > MAX_OPTIMIZE_ITERATIONS:
                raise RecursionError('Domain.optimize: demasiadas vueltas')
            next_level = domain._opt_level.next_level
            previous, domain = domain, domain._optimize_step(model, next_level)
            if domain == previous and domain._opt_level < next_level:
                object.__setattr__(domain, '_opt_level', next_level)
        return domain

    def _optimize_step(self, model, level):
        """Un nivel de optimización — ≙ ``:466``."""
        return self

    def _to_q(self, model=None):
        """El filtro ``Q`` de este dominio — ≙ ``_to_sql`` (``:470``)."""
        raise NotImplementedError


class DomainBool(Domain):
    """Constante ``True``/``False`` — ≙ ``:475``.

    No cuenta como condición: los n-arios la eliminan al aplanar.
    """

    __slots__ = ('value',)

    def __new__(cls, value):
        self = object.__new__(cls)
        object.__setattr__(self, 'value', value)
        object.__setattr__(self, '_opt_level', OptimizationLevel.FULL)
        return self

    def __eq__(self, other):
        return self is other  # sólo hay dos instancias

    def __hash__(self):
        return hash(self.value)

    def is_true(self):
        return self.value

    def is_false(self):
        return not self.value

    def __invert__(self):
        return _FALSE_DOMAIN if self.value else _TRUE_DOMAIN

    def __and__(self, other):
        if isinstance(other, Domain):
            return other if self.value else self
        return NotImplemented

    def __or__(self, other):
        if isinstance(other, Domain):
            return self if self.value else other
        return NotImplemented

    def __iter__(self):
        yield _TRUE_LEAF if self.value else _FALSE_LEAF

    def _to_q(self, model=None):
        """≙ ``SQL("TRUE")`` / ``SQL("FALSE")`` (``:522``).

        El falso es ``Q(pk__in=[])``, no ``~Q()``: Django levanta
        ``EmptyResultSet`` ante el primero y lo colapsa a «ninguna fila»,
        mientras que negarlo colapsa a «sin cláusula ``WHERE``» — el queryset
        entero. Es el defecto que :ref:`h-api-606` registró.
        """
        return Q() if self.value else Q(pk__in=[])


# singletons, accesibles por Domain.TRUE y Domain.FALSE
_TRUE_DOMAIN = DomainBool(True)
_FALSE_DOMAIN = DomainBool(False)


class DomainNot(Domain):
    """Negación con un único hijo — ≙ ``:531``."""

    OPERATOR = '!'

    __slots__ = ('child',)

    def __new__(cls, child):
        self = object.__new__(cls)
        object.__setattr__(self, 'child', child)
        object.__setattr__(self, '_opt_level', OptimizationLevel.NONE)
        return self

    def __invert__(self):
        return self.child

    def __iter__(self):
        yield self.OPERATOR
        yield from self.child

    def iter_conditions(self):
        yield from self.child.iter_conditions()

    def map_conditions(self, function):
        return ~(self.child.map_conditions(function))

    def _optimize_step(self, model, level):
        """Empuja la negación al hijo — ≙ ``:558``. Es el corazón del porte."""
        return self.child._optimize(model, level)._negate(model)

    def __eq__(self, other):
        return self is other or (isinstance(other, DomainNot) and self.child == other.child)

    def __hash__(self):
        return ~hash(self.child)

    def _to_q(self, model=None):
        """≙ ``(cond) IS NOT TRUE`` (``:571``).

        La fuente envuelve la condición en ``IS NOT TRUE``, que incluye la fila
        cuando la condición evalúa a ``NULL``. El ``~Q`` de Django emite
        ``NOT (cond AND col IS NOT NULL)`` sobre columna nulable, que es la
        misma tabla de verdad: con ``col`` nulo el paréntesis es falso y la
        negación deja pasar la fila. Sobre columna no nulable omite la guarda, y
        también es correcto porque no hay nulos.

        No es un accidente afortunado sino la misma regla escrita por dos
        compiladores distintos; medido en ``api@`` este commit y registrado en
        :ref:`h-api-614`.

        Un ``DomainNot`` llega hasta aquí sólo cuando el hijo no se pudo negar
        —``_optimize_step`` empuja el resto hasta las hojas—: hoy, una condición
        sobre ruta con punto o un ``DomainCustom``.
        """
        return ~self.child._to_q(model)


class DomainNary(Domain):
    """Operador n-ario: AND u OR con varios hijos — ≙ ``:576``."""

    __slots__ = ('children',)

    OPERATOR = '???'
    ZERO = _FALSE_DOMAIN  # defecto para los checks del linter

    def __new__(cls, children):
        assert len(children) >= 2
        self = object.__new__(cls)
        object.__setattr__(self, 'children', children)
        object.__setattr__(self, '_opt_level', OptimizationLevel.NONE)
        return self

    @classmethod
    def apply(cls, items):
        """Combina AND/OR sobre una colección de dominios — ≙ ``:594``."""
        children = cls._flatten(items)
        if len(children) == 1:
            return children[0]
        return cls(tuple(children))

    @classmethod
    def _flatten(cls, children):
        """Simplifica constantes y aplana los del mismo tipo — ≙ ``:602``."""
        result = []
        for child in children:
            if isinstance(child, DomainBool):
                if child != cls.ZERO:
                    return [child]
            elif isinstance(child, cls):
                result.extend(child.children)
            else:
                result.append(child)
        return result or [cls.ZERO]

    def __iter__(self):
        yield from itertools.repeat(self.OPERATOR, len(self.children) - 1)
        for child in self.children:
            yield from child

    def __eq__(self, other):
        return self is other or (
            isinstance(other, DomainNary)
            and self.OPERATOR == other.OPERATOR
            and self.children == other.children
        )

    def __hash__(self):
        return hash(self.OPERATOR) ^ hash(self.children)

    @classproperty
    def INVERSE(cls):
        """El tipo n-ario inverso, AND/OR."""
        raise NotImplementedError

    def __invert__(self):
        return self.INVERSE(tuple(~child for child in self.children))

    def _negate(self, model):
        """De Morgan: se niega cada hijo y se invierte el operador."""
        return self.INVERSE(tuple(child._negate(model) for child in self.children))

    def iter_conditions(self):
        for child in self.children:
            yield from child.iter_conditions()

    def map_conditions(self, function):
        return self.apply(child.map_conditions(function) for child in self.children)

    def _optimize_step(self, model, level):
        """Optimiza los hijos y aplana — ≙ ``:652``.

        La fuente además ordena los hijos y corre ``_MERGE_OPTIMIZATIONS`` para
        fusionar condiciones del mismo campo. Esa capa es la tarea **#373**; sin
        ella el aplanado sigue siendo correcto, sólo menos compacto.
        """
        children = self._flatten(child._optimize(model, level) for child in self.children)
        if (len(self.children) == len(children)
                and all(map(operator_module.is_, self.children, children))):
            return self
        return self.apply(children)

    def _to_q(self, model=None):
        """≙ ``(a AND b AND ...)`` / ``(a OR b OR ...)`` (``:671``)."""
        parts = [child._to_q(model) for child in self.children]
        return functools.reduce(self.Q_OPERATOR, parts)


class DomainAnd(DomainNary):
    """AND con varios hijos — ≙ ``:678``."""

    __slots__ = ()
    OPERATOR = '&'
    Q_OPERATOR = operator_module.and_
    ZERO = _TRUE_DOMAIN

    @classproperty
    def INVERSE(cls):
        return DomainOr

    def __and__(self, other):
        if isinstance(other, DomainAnd):
            return DomainAnd(self.children + other.children)
        return super().__and__(other)


class DomainOr(DomainNary):
    """OR con varios hijos — ≙ ``:708``."""

    __slots__ = ()
    OPERATOR = '|'
    Q_OPERATOR = operator_module.or_
    ZERO = _FALSE_DOMAIN

    @classproperty
    def INVERSE(cls):
        return DomainAnd

    def __or__(self, other):
        if isinstance(other, DomainOr):
            return DomainOr(self.children + other.children)
        return super().__or__(other)


class DomainCustom(Domain):
    """Condición que genera su filtro directamente — ≙ ``:738``."""

    __slots__ = ('_filtered', '_q')

    def __new__(cls, to_q, filtered=None):
        self = object.__new__(cls)
        object.__setattr__(self, '_q', to_q)
        object.__setattr__(self, '_filtered', filtered)
        object.__setattr__(self, '_opt_level', OptimizationLevel.FULL)
        return self

    def __eq__(self, other):
        return (
            isinstance(other, DomainCustom)
            and self._q == other._q
            and self._filtered == other._filtered
        )

    def __hash__(self):
        return hash(self._q)

    def __iter__(self):
        yield self

    def _to_q(self, model=None):
        return self._q(model)


class DomainCondition(Domain):
    """Condición sobre un campo: ``(campo, operador, valor)`` — ≙ ``:787``."""

    __slots__ = ('_field_instance', 'field_expr', 'operator', 'value')

    def __new__(cls, field_expr, operator, value):
        self = object.__new__(cls)
        object.__setattr__(self, 'field_expr', field_expr)
        object.__setattr__(self, 'operator', operator)
        object.__setattr__(self, 'value', value)
        object.__setattr__(self, '_field_instance', None)
        object.__setattr__(self, '_opt_level', OptimizationLevel.NONE)
        return self

    def checked(self):
        """Valida y devuelve ``self``, o levanta — ≙ ``:814``."""
        if not isinstance(self.field_expr, str) or not self.field_expr:
            self._raise('Nombre de campo vacío', error=TypeError)
        operator = self.operator.lower()
        if operator != self.operator:
            return DomainCondition(self.field_expr, operator, self.value).checked()
        if operator not in CONDITION_OPERATORS:
            self._raise('Operador inválido')
        value = self.value
        if value is None:
            value = False
        if value is not self.value:
            return DomainCondition(self.field_expr, operator, value)
        return self

    def __invert__(self):
        """≙ ``:848``. Conservador con las rutas, igual que la fuente.

        Sólo se invierte el operador cuando el campo es simple. Con una ruta
        (``lineas.producto``) la negación de «alguna línea cumple X» **no** es
        «alguna línea cumple no-X», y eso vale igual aquí: Django tiene la misma
        diferencia entre ``exclude(...)`` y ``filter(~Q(...))`` sobre un camino
        to-many. Las desigualdades las trata ``_negate``.
        """
        if '.' not in self.field_expr and (neg_op := _INVERSE_OPERATOR.get(self.operator)):
            return DomainCondition(self.field_expr, neg_op, self.value)
        return super().__invert__()

    def _negate(self, model):
        """≙ ``:855``. La desigualdad negada suma su rama de nulos.

        El inverso de los operadores lo resuelve la construcción; las cuatro
        desigualdades no, porque hace falta saber si el campo tiene un valor
        *falsy*. Sin ese valor, ``NOT (campo < v)`` descarta la fila sin
        valor, y la fuente la incluye añadiendo ``campo in {False}``.
        """
        if neg_op := _INVERSE_INEQUALITY.get(self.operator):
            condition = DomainCondition(self.field_expr, neg_op, self.value)
            if falsy_value(self._field(model)) is None:
                is_null = DomainCondition(self.field_expr, 'in', (False,))
                condition = is_null | condition
            return condition
        return super()._negate(model)

    def __iter__(self):
        field_expr, operator, value = self.field_expr, self.operator, self.value
        if isinstance(value, (*_COLLECTION_TYPES, Domain)):
            value = list(value)
        yield (field_expr, operator, value)

    def __eq__(self, other):
        return self is other or (
            isinstance(other, DomainCondition)
            and self.field_expr == other.field_expr
            and self.operator == other.operator
            and self.value.__class__ is other.value.__class__
            and self.value == other.value
        )

    def __hash__(self):
        return hash(self.field_expr) ^ hash(self.operator) ^ hash(str(self.value))

    def iter_conditions(self):
        yield self

    def map_conditions(self, function):
        result = function(self)
        assert isinstance(result, Domain), 'map_conditions no devolvió un Domain'
        return result

    def _raise(self, message, *args, error=ValueError):
        """Levanta el error nombrando la condición — ≙ ``:899``."""
        message += ' en la condición (%r, %r, %r)'
        raise error(message % (*args, self.field_expr, self.operator, self.value))

    def _field(self, model):
        """El campo de la expresión, memoizado — ≙ ``:904``."""
        field = self._field_instance
        if field is None:
            field = self.__get_field(model)
        return field

    def __get_field(self, model):
        """Resuelve el campo o levanta — ≙ ``__get_field`` (``:911``).

        Devuelve ``None`` cuando no hay modelo: es un **desconocido**, no una
        ausencia. ``condition_to_q`` lo trata con los defectos de la fuente
        (``can_be_null=True``, ``falsy_value=None``), que es la hipótesis
        conservadora.
        """
        if model is None:
            return None
        current, field = model, None
        for part in self.field_expr.split('.'):
            if current is None:
                self._raise('Ruta que atraviesa un campo no relacional')
            try:
                field = current._meta.get_field(part)
            except FieldDoesNotExist:
                self._raise('Campo inválido %s.%s', current._meta.label, part)
            current = field.related_model if field.is_relation else None
        object.__setattr__(self, '_field_instance', field)
        return field

    def _optimize_step(self, model, level):
        """≙ ``:922``, reducido a marcar el nivel.

        La fuente despacha aquí los 39 optimizadores registrados por operador y
        por tipo de campo. Ninguno está portado (tarea **#373**), así que la
        condición se devuelve tal cual y la normalización mínima que la
        compilación necesita la hace ``_to_q``.
        """
        return self

    def _to_q(self, model=None):
        """El filtro ``Q`` de la condición — ≙ ``_to_sql`` (``:1087``).

        Dos cosas ocurren antes de delegar en ``condition_to_q``:

        1. **``=``/``!=`` se normalizan a ``in``/``not in``** de un elemento.
           Allá lo hace el optimizador ``_operator_equal_as_in`` (``:1280``);
           aquí ocurre en el paso de compilación porque esa capa no existe
           todavía (tarea **#373**). Sin esta normalización el compilador de
           hoja recibiría un operador que la fuente le promete ya reducido.
        2. **La colección vacía colapsa a constante** — ``in []`` es FALSO y
           ``not in []`` es VERDADERO. Es ``_optimize_in_set`` (``:1315``), y
           sin ella el compilador de hoja se queda sin nada que emitir: la
           fuente tiene ahí el mismo ``assert`` que nosotros, y nunca lo alcanza
           porque su optimizador ya recortó el caso.
        3. **La ruta con punto pasa a la travesía de Django** (``a.b`` →
           ``a__b``). Es lo que :ref:`h-api-614` registró: el mapa anterior la
           pasaba tal cual y Django no resuelve el punto.
        """
        field_expr, operator, value = self.field_expr, self.operator, self.value

        if operator in ('==', '<>'):
            operator = '=' if operator == '==' else '!='
        if operator in ('=', '!='):
            operator = 'in' if operator == '=' else 'not in'
            if isinstance(value, _COLLECTION_TYPES):
                # una colección vacía compara contra «no establecido»
                value = tuple(value) or (False,)
            else:
                value = (value,)

        if operator in ('in', 'not in') and isinstance(value, _COLLECTION_TYPES) and not value:
            return (_FALSE_DOMAIN if operator == 'in' else _TRUE_DOMAIN)._to_q(model)

        if operator not in STANDARD_CONDITION_OPERATORS:
            self._raise('Operador no soportado al compilar')

        return condition_to_q(
            _django_path(field_expr), operator, value, self._field(model))


# ==========================================================================
# Fachada sobre ``Q`` — la superficie que consume el árbol
# ==========================================================================
#
# ``AND``/``OR``/``NOT`` operan sobre objetos ``Q``, no sobre ``Domain``. No es
# un descuido: es el mismo papel que ``odoo/osv/expression.py`` cumple en la
# fuente —re-exportar funciones de módulo para el código que no construye el
# AST— y es el contrato que los archivos del árbol ya consumen
# (``expression.AND([Q(...), Q(...)])``). Cambiarlo rompería esos sitios sin
# ganar nada: dentro de ellos el ``Q`` ya está construido.

TRUE_DOMAIN = Q()

#: El dominio que no matchea nada — ≙ ``Domain.FALSE``.
#:
#: **Corregido 2026-08-15 (H-API-606).** Decía ``~Q(pk__in=[])``, que es su
#: opuesto exacto: ``Q(pk__in=[])`` levanta ``EmptyResultSet`` y Django lo
#: colapsa a «ninguna fila», así que su negación colapsa a «sin cláusula
#: ``WHERE``» — el queryset entero.
FALSE_DOMAIN = Q(pk__in=[])


def AND(domains):
    """Conjunción de filtros ``Q`` — ≙ ``expression.AND``."""
    out = Q()
    for d in domains:
        out &= d
    return out


def OR(domains):
    """Disyunción de filtros ``Q`` — ≙ ``expression.OR``."""
    if not domains:
        return FALSE_DOMAIN
    out = domains[0]
    for d in domains[1:]:
        out |= d
    return out


def NOT(domain):
    """Negación de un filtro ``Q`` — ≙ ``expression.NOT``."""
    return ~domain


def to_q(domain, model=None):
    """Un dominio en notación polaca a ``Q``.

    Construye el AST, empuja la negación a las hojas y compila. El ``model`` es
    opcional y sólo mejora el resultado: con él se resuelven la nulabilidad de
    la columna y el valor *falsy* del campo, que es lo que decide si una
    condición negada suma su rama ``OR campo IS NULL``. Sin él se asumen los
    defectos de la fuente, que son los conservadores.
    """
    return Domain(domain).optimize(model)._to_q(model)
