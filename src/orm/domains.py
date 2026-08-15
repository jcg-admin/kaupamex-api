"""Dominios del ORM — fiel a ``odoo/orm/domains.py`` (Odoo 19).

En Odoo 19 la lógica de dominios (combinar leaves con ``&``/``|``/``!``) vive en
``odoo/orm/domains.py`` y ``odoo/osv/expression.py`` es un shim de compat que la
re-exporta. Aquí, con el prefijo ``odoo.`` eliminado (``orm`` ≙ ``odoo/orm``),
esta es la **definición**; ``src/osv/expression.py`` (≙ ``odoo/osv/expression.py``)
la re-exporta.

Respaldo Django: los dominios de Odoo (listas polacas ``['&', (a), (b)]``) se
combinan sobre objetos ``Q`` de Django, preservando ``AND``/``OR``/``NOT`` y las
constantes ``TRUE_DOMAIN``/``FALSE_DOMAIN``.
"""
from django.db.models import Q

__all__ = ['AND', 'OR', 'NOT', 'TRUE_DOMAIN', 'FALSE_DOMAIN', 'to_q']

TRUE_DOMAIN = Q()

#: El dominio que no matchea nada — ≙ ``Domain.FALSE``
#: (``odoo19c: odoo/orm/domains.py``).
#:
#: **Corregido 2026-08-15 (H-API-606).** Decía ``~Q(pk__in=[])``, que es su
#: opuesto exacto: ``Q(pk__in=[])`` levanta ``EmptyResultSet`` y Django lo
#: colapsa a «ninguna fila», así que su negación colapsa a «sin cláusula
#: ``WHERE``» — el queryset entero. Medido sobre ``StockQuant``, la consulta
#: salía sin ``WHERE``.
#:
#: La forma correcta ya estaba en este mismo archivo: ``OR([])`` devuelve
#: ``Q(pk__in=[])``. El archivo se contradecía a sí mismo.
FALSE_DOMAIN = Q(pk__in=[])


def AND(domains):
    """Conjunción de dominios (Odoo ``expression.AND`` / ``Domain.AND``)."""
    out = Q()
    for d in domains:
        out &= d
    return out


def OR(domains):
    """Disyunción de dominios (Odoo ``expression.OR`` / ``Domain.OR``)."""
    if not domains:
        return Q(pk__in=[])
    out = domains[0]
    for d in domains[1:]:
        out |= d
    return out


def NOT(domain):
    """Negación de un dominio (Odoo ``expression.NOT``)."""
    return ~domain


# === Dominio de Odoo (lista polaca) → ``Q`` ================================
# El subconjunto de ``STANDARD_CONDITION_OPERATORS`` de la fuente
# (``odoo19c: odoo/orm/domains.py:81``) que las record rules del árbol usan;
# ampliarlo es añadir una fila. ``=``/``!=`` no están en esa lista porque la
# fuente los normaliza a ``in``/``not in`` de un elemento — aquí se aceptan
# directos porque los dominios almacenados los escriben así
# (``base_security.xml``: ``[('user_id','=',user.id)]``).

_LEAF_OPERATORS = {
    '=': '',
    '!=': '',
    'in': '__in',
    'not in': '__in',
    '<': '__lt',
    '<=': '__lte',
    '>': '__gt',
    '>=': '__gte',
    'like': '__contains',
    'ilike': '__icontains',
    'not like': '__contains',
    'not ilike': '__icontains',
}
_NEGATED = frozenset(['!=', 'not in', 'not like', 'not ilike'])


def _leaf_to_q(leaf):
    """Un leaf ``(campo, operador, valor)`` a ``Q``.

    - ``(1, '=', 1)`` es el leaf VERDADERO de la fuente (``[(1,'=',1)]`` en
      ``base_security.xml``) → ``Q()``.
    - ``('campo', '=', False)`` en la fuente empata NULL → ``__isnull=True``.
    """
    field, operator, value = leaf
    if field == 1 and value == 1:
        return TRUE_DOMAIN
    if operator not in _LEAF_OPERATORS:
        raise ValueError('Operador de dominio no soportado: %r' % (operator,))
    if operator in ('=', '!=') and value is False:
        q = Q(**{'%s__isnull' % field: True})
    else:
        q = Q(**{'%s%s' % (field, _LEAF_OPERATORS[operator]): value})
    return ~q if operator in _NEGATED else q


def to_q(domain):
    """Un dominio en notación polaca a ``Q`` — el parse de la fuente.

    Igual que allá: los términos sin operador explícito se combinan con
    ``&`` implícito; ``&``/``|`` consumen dos operandos y ``!`` uno.
    """
    stack = []
    for token in reversed(list(domain)):
        if token == '&':
            stack.append(stack.pop() & stack.pop())
        elif token == '|':
            stack.append(stack.pop() | stack.pop())
        elif token == '!':
            stack.append(~stack.pop())
        else:
            stack.append(_leaf_to_q(tuple(token)))
    result = Q()
    for q in stack:
        result &= q
    return result
