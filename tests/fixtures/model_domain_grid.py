"""Rejilla de dominios con modelo, compartida por la referencia y el puerto.

Este módulo no importa ni ``odoo`` ni ``orm``: se ejecuta tal cual en los
dos procesos, el de referencia (``reference_process``) y el de la prueba.
Cada lado le pasa su clase ``Domain`` y su modelo, y la traza resultante se
compara cadena a cadena.

Los campos son los que ``ir.rule`` declara con el mismo tipo en los dos
árboles: ``name`` (char), ``domain_force`` (text), ``active`` y
``perm_read`` (boolean), ``groups`` (many2many) e ``id`` (integer).
``model_id`` (many2one en la referencia, ``model_name`` char aquí) queda
fuera porque no es el mismo campo.
"""

TEXT_OPERATORS = ('=', '!=', 'in', 'not in', 'like', 'ilike', 'not like',
                  'not ilike', '=like', '=ilike')
TEXT_VALUES = ('a', '', False, True, ['a', 'a', False], [], ['b', 'a'])
BOOLEAN_OPERATORS = ('=', '!=', 'in', 'not in')
BOOLEAN_VALUES = (True, False, 'True', 'False', ['False'], [], [True, False],
                  1, 0, [None])
RELATIONAL_OPERATORS = ('=', '!=', 'in', 'not in', 'any', 'not any')
RELATIONAL_VALUES = (False, [], [1, 2], 1, [1, 1, False])
INTEGER_OPERATORS = ('=', '!=', 'in', 'not in', '<', '>=')
INTEGER_VALUES = (1, [1, 1, 2], [], False, '3', [False])

FIELDS = (
    ('name', TEXT_OPERATORS, TEXT_VALUES),
    ('domain_force', TEXT_OPERATORS, TEXT_VALUES),
    ('active', BOOLEAN_OPERATORS, BOOLEAN_VALUES),
    ('perm_read', BOOLEAN_OPERATORS, BOOLEAN_VALUES),
    ('groups', RELATIONAL_OPERATORS, RELATIONAL_VALUES),
    ('id', INTEGER_OPERATORS, INTEGER_VALUES),
)


def conditions():
    """Las condiciones de la rejilla, en orden estable."""
    return [(field, operator, value)
            for field, operators, values in FIELDS
            for operator in operators for value in values]


def _step(function):
    try:
        return repr(function())
    except Exception as error:
        # La clase de la excepción es el resultado del paso: se compara
        # entre los dos procesos, y su mensaje no.
        return f'raises {type(error).__name__}'


def trace(domain_class, model):
    """Para cada condición: ``optimize`` y ``optimize_full`` sobre ``model``.

    Una condición sola, y la misma negada con ``'!'``, para que el empuje de
    la negación pase por los optimizadores del campo.
    """
    lines = []
    for condition in conditions():
        for prefix in ((), ('!',)):
            source = [*prefix, condition]
            lines.append(
                f'{source!r} optimize '
                + _step(lambda: domain_class(source).optimize(model)))
            lines.append(
                f'{source!r} optimize_full '
                + _step(lambda: domain_class(source).optimize_full(model)))
    return lines
