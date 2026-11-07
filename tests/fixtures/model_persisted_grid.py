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

``_has_cycle`` (``:5624-5682``) se pide sobre la cadena sin ciclo, sobre un
recordset vacío, con un campo que no existe y con uno que no es relación
sobre el propio modelo; después la rejilla cierra el ciclo con un ``UPDATE``
directo —``_has_cycle`` lee la base, no la caché— y vuelve a preguntar. El
alias deprecado ``_check_recursion`` (``:5684-5686``) responde lo contrario.

``try_lock_for_update`` (``:5592-5622``) bloquea filas en la única conexión
de la rejilla, sin competencia: devuelve lo que puede bloquear, en el orden
de ``self``, con ventana, con un registro nuevo, con un id que no existe y
con el bloqueo que admite referencias.
"""

import warnings

PREFIX = 'grid-persisted-'
DOMAIN = [('name', '=like', f'{PREFIX}%')]
NOTHING = [('name', '=', f'{PREFIX}none')]
FIELDS = ['name', 'parent']
#: Id que ninguna de las dos bases de prueba alcanza.
MISSING_ID = 987654321


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


def _execute(model, query, params):
    """Allá ``env.cr`` es un cursor; aquí es la conexión de Django."""
    cr = model.browse(()).env.cr
    if getattr(cr, 'execute', None) is not None:
        cr.execute(query, params)
        return
    with cr.cursor() as cursor:
        cursor.execute(query, params)


def _close_cycle(model):
    """La raíz pasa a colgar de la nieta: raíz → nieta → hija → raíz."""
    by_name = {record.name: record.id for record in model.search(DOMAIN)}
    _execute(model, f'UPDATE {model._table} SET parent = %s WHERE id = %s',
             [by_name[f'{PREFIX}c-grandchild'], by_name[f'{PREFIX}a-root']])
    return True


def _recursion(records):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        return records._check_recursion()


def _named(names, value):
    if isinstance(value, tuple):
        return (names.get(value[0], value[0]), value[1])
    if type(value) is int:
        return names.get(value, value)
    return value


def _names(records):
    return [record.name for record in records]


def _records(records):
    # un Many2one vacío es allá un conjunto vacío y aquí ``None``
    return [(record.name, record.parent.name if record.parent else False)
            for record in records]


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
    chain = model.search(DOMAIN, order='name desc')
    root = model.search([('name', '=', f'{PREFIX}a-root')])
    steps += [
        ('lock chain', lambda: _names(chain.try_lock_for_update())),
        ('lock limit', lambda: _names(chain.try_lock_for_update(limit=2))),
        ('lock referencing', lambda: _names(chain.try_lock_for_update(
            allow_referencing=True))),
        ('lock missing', lambda: _names(model.browse(
            (MISSING_ID,)).try_lock_for_update())),
        ('lock new', lambda: _names(model.new(
            {'name': 'N'}).try_lock_for_update(limit=1))),
        ('lock chain and new', lambda: _names((chain + model.new(
            {'name': 'N'})).try_lock_for_update())),
        ('lock empty', lambda: _names(model.browse(
            ()).try_lock_for_update())),
    ]
    steps += [
        ('has_cycle chain', lambda: chain._has_cycle()),
        ('has_cycle root', lambda: root._has_cycle('parent')),
        ('has_cycle empty', lambda: model.browse(())._has_cycle()),
        ('has_cycle unknown field', lambda: chain._has_cycle('nope')),
        ('has_cycle not a relation', lambda: chain._has_cycle('name')),
        ('check_recursion chain', lambda: _recursion(chain)),
        ('close cycle', lambda: _close_cycle(model)),
        ('has_cycle after', lambda: chain._has_cycle()),
        ('has_cycle root after', lambda: root._has_cycle()),
        ('check_recursion after', lambda: _recursion(chain)),
    ]
    return [f'{name} {_step(function)}' for name, function in steps]
