"""Rejilla de las piezas de ``environments.py`` que no necesitan cursor.

Como las otras rejillas de módulo, no importa ni ``odoo`` ni ``orm``: cada
lado le pasa su módulo de entornos —``odoo.orm.environments`` en el proceso
de referencia, ``orm.environments`` aquí—. Cubre ``Starred``: su ``repr``
sobre valores de cinco tipos, el atributo ``value``, sus ``__slots__`` y el
rechazo de un atributo que las ranuras no declaran.
"""
VALUES = (7, 'a', None, (1, 2), [3])


def _step(function):
    try:
        return repr(function())
    except Exception as error:
        # La clase de la excepción es el resultado del paso; su mensaje no.
        return f'raises {type(error).__name__}'


def trace(module):
    """Los pasos de la rejilla, cada uno como ``nombre resultado``."""
    starred = module.Starred
    steps = [(f'repr {value!r}', lambda value=value: repr(starred(value)))
             for value in VALUES]
    steps += [
        ('value', lambda: starred(5).value),
        ('slots', lambda: starred.__dict__['__slots__']),
        ('no dict', lambda: hasattr(starred(1), '__dict__')),
        ('setattr other', lambda: setattr(starred(1), 'other', 2)),
    ]
    return [f'{name} {_step(function)}' for name, function in steps]
