"""Rejilla de las piezas de ``models.py`` que no necesitan modelo ni base.

Como las otras rejillas, no importa ni ``odoo`` ni ``orm``: cada lado le pasa
su módulo de modelos —``odoo.orm.models`` en el proceso de referencia,
``orm.models`` aquí—. Cubre ``fix_import_export_id_paths``,
``itemgetter_tuple``, ``ReversibleComparator`` (orden con ``None`` y con
inversión, igualdad, ``hash`` estable sobre enteros, ``repr`` y
``__slots__``), los valores por defecto de los atributos de clase de
``BaseModel`` y sus ganchos base ``_valid_field_parameter``,
``_post_model_setup__``, ``_register_hook`` y ``_unregister_hook``.
"""
import functools

#: Atributos de clase de ``BaseModel`` cuyo valor por defecto es el contrato
#: (``odoo19c: odoo/orm/models.py:370-464``).
CLASS_ATTRIBUTES = (
    '_auto', '_register', '_abstract', '_transient', '_name', '_description',
    '_module', '_custom', '_inherit', '_inherit_children', '_table',
    '_table_query', '_rec_name', '_rec_names_search', '_order',
    '_parent_name', '_parent_store', '_active_name', '_fold_name',
    '_translate', '_check_company_auto', '_allow_sudo_commands',
)
PATHS = ('name', 'partner_id/id', 'partner_id.id', 'partner_id:id',
         'a/b.id', 'a/.id', '.id', ':id', 'a.b.c', 'line_ids/product_id:id')


def _step(function):
    try:
        return repr(function())
    except Exception as error:
        # La clase de la excepción es el resultado del paso: se compara
        # entre los dos procesos, y su mensaje no.
        return f'raises {type(error).__name__}'


def _sorted(module, values, reverse, none_first):
    return sorted(values, key=functools.partial(
        module.ReversibleComparator, reverse=reverse, none_first=none_first))


def trace(module):
    """Los pasos de la rejilla, cada uno como ``nombre resultado``."""
    comparator = module.ReversibleComparator
    steps = [(f'path {path}', functools.partial(
        module.fix_import_export_id_paths, path)) for path in PATHS]
    steps += [
        ('itemgetter none', lambda: module.itemgetter_tuple([])({'a': 1})),
        ('itemgetter one', lambda: module.itemgetter_tuple(['a'])(
            {'a': 1, 'b': 2})),
        ('itemgetter two', lambda: module.itemgetter_tuple(['b', 'a'])(
            {'a': 1, 'b': 2})),
        ('itemgetter index', lambda: module.itemgetter_tuple([1])('xyz')),
        ('itemgetter missing', lambda: module.itemgetter_tuple(['z'])({})),
    ]
    values = [3, None, 1, 2, None]
    for reverse in (False, True):
        for none_first in (False, True):
            steps.append((
                f'sorted reverse={reverse} none_first={none_first}',
                functools.partial(_sorted, module, values, reverse,
                                  none_first)))
    steps += [
        ('lt equal', lambda: comparator(1, False, False)
         < comparator(1, False, False)),
        ('eq', lambda: comparator(1, False, False)
         == comparator(1, True, True)),
        ('ne', lambda: comparator(1, False, False)
         == comparator(2, False, False)),
        ('hash', lambda: hash(comparator(7, False, False)) == hash(7)),
        ('repr', lambda: repr(comparator('x', False, False))),
        ('repr reverse', lambda: repr(comparator('x', True, False))),
        ('slots', lambda: comparator.__slots__),
        ('lt mixed types', lambda: comparator(1, False, False)
         < comparator('a', False, False)),
    ]
    steps += [(f'attribute {name}', functools.partial(
        getattr, module.BaseModel, name)) for name in CLASS_ATTRIBUTES]
    # Los dos ganchos base de la configuración de un modelo (``:479-486``):
    # se invocan sin instancia, porque ninguno lee ``self``.
    steps += [(f'valid field parameter {name}',
               lambda name=name: module.BaseModel._valid_field_parameter(
                   None, None, name))
              for name in ('related_sudo', 'related', 'config_parameter', '')]
    steps.append(('post model setup',
                  lambda: module.BaseModel._post_model_setup__(None)))
    steps += [(f'{hook} base', lambda hook=hook: getattr(
        module.BaseModel, hook)(None))
        for hook in ('_register_hook', '_unregister_hook')]
    return [f'{name} {_step(function)}' for name, function in steps]
