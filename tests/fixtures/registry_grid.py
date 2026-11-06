"""Rejilla de ``TriggerTree``, ``DummyRLock`` y ``_unaccent`` del registro.

Como las otras rejillas, no importa ni ``odoo`` ni ``orm``: cada lado le pasa
su módulo de registro —``odoo.orm.registry`` en el proceso de referencia,
``orm.registry`` aquí— y la traza se compara cadena a cadena. Ninguna de las
tres piezas necesita modelo ni base: los nodos del árbol se rotulan con
cadenas, que es lo único que ``TriggerTree`` exige de un campo (ser
hashable y tener ``repr``).

``_unaccent`` se mide en sus tres ramas: texto, ``SQL`` (código y
parámetros, también anidado y compuesto dos veces) y ``Composable``
(``Identifier``, ``Composed`` y ``Literal``), más dos entradas que no son de
ninguno de esos tipos y caen a la rama de texto.
"""


def _step(function):
    try:
        return repr(function())
    except Exception as error:
        # La clase de la excepción es el resultado del paso: se compara
        # entre los dos procesos, y su mensaje no.
        return f'raises {type(error).__name__}'


def _tree(module):
    """G depende de F, H de X.F, I de W.X.F y J de Y.F (el docstring)."""
    tree = module.TriggerTree(['G'])
    tree.increase('X').root = ['H']
    tree.increase('X').increase('W').root = ['I']
    tree.increase('Y').root = ['J']
    return tree


def _merge(module, select=bool):
    first = _tree(module)
    second = module.TriggerTree(['G', 'K'])
    second.increase('X').root = ['H2']
    second.increase('Z').root = ['']
    return module.TriggerTree.merge([first, second], select)


def _lock(module):
    lock = module.DummyRLock()
    with lock as entered:
        inside = entered
    return (lock.acquire(), lock.release(), inside)


def _wrapped(module, value):
    """El resultado de ``_unaccent``: código y parámetros si es ``SQL``."""
    result = module._unaccent(value)
    if isinstance(result, module.SQL):
        return ('SQL', result.code, result.params)
    return (type(result).__name__, result)


def unaccent_steps(module, composable):
    """Las tres ramas de ``_unaccent`` (``odoo19c: registry.py:76-81``).

    ``composable`` es el módulo ``sql`` del controlador de cada lado:
    ``psycopg2.sql`` en la referencia y ``psycopg.sql`` aquí, que es la
    divergencia de mecanismo que el puerto declara.
    """
    sql = module.SQL
    return [
        ('unaccent sql', lambda: _wrapped(module, sql('%s', 'x'))),
        ('unaccent sql nested', lambda: _wrapped(
            module, sql('lower(%s)', sql.identifier('t', 'c')))),
        ('unaccent sql twice', lambda: _wrapped(
            module, module._unaccent(sql('%s', 'x')))),
        ('unaccent identifier', lambda: _wrapped(
            module, composable.Identifier('name'))),
        ('unaccent composed', lambda: _wrapped(module, composable.SQL(
            'lower({})').format(composable.Identifier('x')))),
        ('unaccent literal', lambda: _wrapped(
            module, composable.Literal('á'))),
        ('unaccent integer', lambda: _wrapped(module, 3)),
        ('unaccent none', lambda: _wrapped(module, None)),
    ]


def trace(module, composable):
    """Los pasos de la rejilla, cada uno como ``nombre resultado``."""
    tree_class = module.TriggerTree
    steps = [
        ('empty', lambda: tree_class()),
        ('empty bool', lambda: bool(tree_class())),
        ('root bool', lambda: bool(tree_class(['F']))),
        ('child bool', lambda: bool(tree_class((), {'X': tree_class()}))),
        ('tree', lambda: _tree(module)),
        ('increase existing', lambda: _tree(module).increase('X')),
        ('increase identity', lambda: (
            lambda tree: tree.increase('X') is tree.increase('X'))(
                _tree(module))),
        ('depth first', lambda: [node.root for node in
                                 _tree(module).depth_first()]),
        ('merge', lambda: _merge(module)),
        ('merge select', lambda: _merge(
            module, lambda field: field not in ('H', 'K'))),
        ('merge drops empty', lambda: 'Z' in _merge(
            module, lambda field: field != '')),
        ('merge none', lambda: tree_class.merge([])),
        ('slots', lambda: tree_class.__slots__),
        ('set attribute', lambda: setattr(tree_class(), 'other', 1)),
        ('lock', lambda: _lock(module)),
        ('unaccent text', lambda: module._unaccent('name')),
        *unaccent_steps(module, composable),
    ]
    return [f'{name} {_step(function)}' for name, function in steps]
