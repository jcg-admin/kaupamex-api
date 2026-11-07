"""Rejilla de búsqueda con registros persistidos sobre ``test_orm.category``.

Como las otras rejillas de modelo, no importa ni ``odoo`` ni ``orm``. Crea
tres categorías encadenadas por ``parent`` (raíz, hija y nieta) con nombres
propios de la rejilla; el proceso de referencia revierte su cursor al
terminar y la prueba del puerto corre dentro de una transacción, así que
nada queda en ninguna de las dos bases.

``search_fetch`` (``odoo19c: odoo/orm/models.py:1394-1428``) y
``search_read`` (``:6286-6329``) se piden con orden, con ventana y con un
dominio vacío de resultado. Los ids difieren entre las dos bases, así que
cada id se reemplaza por el nombre de su registro antes de comparar.
"""

PREFIX = 'grid-persisted-'
DOMAIN = [('name', '=like', f'{PREFIX}%')]
NOTHING = [('name', '=', f'{PREFIX}none')]
FIELDS = ['name', 'parent']


def _step(function):
    try:
        return repr(function())
    except Exception as error:
        # La clase de la excepción es el resultado del paso; su mensaje no.
        return f'raises {type(error).__name__}'


def _seed(model):
    root = model.create({'name': f'{PREFIX}a-root'})
    child = model.create({'name': f'{PREFIX}b-child', 'parent': root.id})
    model.create({'name': f'{PREFIX}c-grandchild', 'parent': child.id})
    return {record.id: record.name
            for record in model.search(DOMAIN)}


def _named(names, value):
    if isinstance(value, tuple):
        return (names.get(value[0], value[0]), value[1])
    if type(value) is int:
        return names.get(value, value)
    return value


def _records(records):
    return [(record.name, record.parent.name or False) for record in records]


def _rows(names, rows):
    return [sorted((key, _named(names, value)) for key, value in row.items())
            for row in rows]


def trace(Domain, model, model_name):
    """Los pasos de la rejilla, cada uno como ``nombre resultado``."""
    del Domain, model_name
    names = _seed(model)
    steps = [
        ('search_fetch ordered', lambda: _records(model.search_fetch(
            DOMAIN, FIELDS, order='name desc'))),
        ('search_fetch window', lambda: _records(model.search_fetch(
            DOMAIN, FIELDS, offset=1, limit=1))),
        ('search_fetch nothing', lambda: _records(model.search_fetch(
            NOTHING, FIELDS))),
        ('search_read ordered', lambda: _rows(names, model.search_read(
            DOMAIN, FIELDS, order='name'))),
        ('search_read no load', lambda: _rows(names, model.search_read(
            DOMAIN, FIELDS, order='name', load=None))),
        ('search_read window', lambda: _rows(names, model.search_read(
            DOMAIN, ['name'], offset=2, limit=5, order='name'))),
        ('search_read nothing', lambda: _rows(names, model.search_read(
            NOTHING, FIELDS))),
    ]
    return [f'{name} {_step(function)}' for name, function in steps]
