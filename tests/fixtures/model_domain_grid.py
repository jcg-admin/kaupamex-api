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


TEMPORAL_OPERATORS = ('=', '!=', 'in', 'not in', '<', '>=')
DATE_VALUES = ('2024-03-10', '2024-03-10 23:30:00', False, ['2024-03-10'],
               'not a date', 'today', 3)
DATETIME_VALUES = ('2024-03-10', '2024-03-10 23:30:00', False,
                   ['2024-03-10', '2024-11-03 01:30:00'], 'not a date',
                   'today', 3)
BINARY_OPERATORS = ('=', '!=', 'in', 'not in', 'like')
BINARY_VALUES = (False, True, 'abc', [False])

#: Campos con el mismo nombre y tipo en los dos árboles, por modelo.
MODEL_FIELDS = {
    'ir.rule': FIELDS,
    'ir.cron': (
        ('nextcall', TEMPORAL_OPERATORS, DATETIME_VALUES),
        ('first_failure_date', TEMPORAL_OPERATORS, DATETIME_VALUES),
        ('interval_number', INTEGER_OPERATORS, INTEGER_VALUES),
        ('active', BOOLEAN_OPERATORS, BOOLEAN_VALUES),
    ),
    'res.currency.rate': (
        ('name', TEMPORAL_OPERATORS, DATE_VALUES),
    ),
    'res.partner': (
        ('image_1920', BINARY_OPERATORS, BINARY_VALUES),
        ('parent_id', RELATIONAL_OPERATORS, RELATIONAL_VALUES),
        ('name', TEXT_OPERATORS, TEXT_VALUES),
    ),
}


def conditions(model_name='ir.rule'):
    """Las condiciones de la rejilla de ``model_name``, en orden estable."""
    return [(field, operator, value)
            for field, operators, values in MODEL_FIELDS[model_name]
            for operator in operators for value in values]


#: Pares de valores para combinar dos condiciones sobre el mismo campo: los
#: optimizadores de n-arios fusionan ``in``/``not in``/``any``/``not any``.
PAIR_OPERATORS = ('=', '!=', 'in', 'not in', 'any', 'not any')
PAIR_FIELDS = (
    ('name', ('a', ['b', 'a'], False)),
    ('active', (True, [False])),
    ('groups', ([1, 2], [2, 3], False)),
    ('id', ([1, 2], 3)),
)


#: Pares por modelo; sólo ``ir.rule`` los ejerce.
MODEL_PAIR_FIELDS = {'ir.rule': PAIR_FIELDS}


def pairs(model_name='ir.rule'):
    """Pares de condiciones sobre un mismo campo, con operadores de fusión."""
    result = []
    for field, values in MODEL_PAIR_FIELDS.get(model_name, ()):
        operators = (PAIR_OPERATORS if field == 'groups'
                     else PAIR_OPERATORS[:4])
        atoms = [(field, operator, value) for operator in operators
                 for value in values]
        result.extend((first, second) for first in atoms for second in atoms)
    return result


def _step(function):
    try:
        return repr(function())
    except Exception as error:
        # La clase de la excepción es el resultado del paso: se compara
        # entre los dos procesos, y su mensaje no.
        return f'raises {type(error).__name__}'


def trace(domain_class, model, model_name='ir.rule'):
    """``optimize``, ``optimize_full`` y ``validate`` sobre ``model``.

    Cada condición sola, y la misma negada con ``'!'``, para que el empuje de
    la negación pase por los optimizadores del campo; después, los pares de
    ``pairs()`` unidos con ``'&'`` y con ``'|'``, para los de fusión.
    """
    lines = []
    for condition in conditions(model_name):
        for prefix in ((), ('!',)):
            source = [*prefix, condition]
            lines.append(
                f'{source!r} optimize '
                + _step(lambda: domain_class(source).optimize(model)))
            lines.append(
                f'{source!r} optimize_full '
                + _step(lambda: domain_class(source).optimize_full(model)))
        validated = _step(lambda: domain_class([condition]).validate(model))
        lines.append(f'{condition!r} validate {validated}')
    for operator in ('&', '|'):
        for first, second in pairs(model_name):
            source = [operator, first, second]
            lines.append(
                f'{source!r} optimize '
                + _step(lambda: domain_class(source).optimize(model)))
            lines.append(
                f'{source!r} optimize_full '
                + _step(lambda: domain_class(source).optimize_full(model)))
    return lines
