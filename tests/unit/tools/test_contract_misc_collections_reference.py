"""Las colecciones y funciones puras de ``tools.misc`` contra la fuente.

Se extraen de ``odoo19c: odoo/tools/misc.py``, por AST y sin modificar su
texto, las definiciones que se comparan (``NAMES``): el módulo completo
importa media plataforma, y estas definiciones sólo usan la biblioteca
estándar, ``freehash`` y los ``TypeVar`` ``K``/``T``, que se extraen con
ellas. El encabezado ``HEADER`` aporta sus importaciones de la biblioteca
estándar; no hay sustitutos.

*Métrica:* el valor —o el nombre de la excepción— de cada operación de la
rejilla, en los dos lados.
*Ciega a:* las definiciones de ``misc`` que dependen de la configuración o
del entorno (``get_lang``, ``format_amount``, ``parse_date``,
``find_in_path``, ``find_pg_tool``, ``get_diff``) y los administradores de
registro (``mute_logger``, ``lower_logging``, ``replace_exceptions``).
"""
import pathlib

import pytest

from tests.fixtures import reference_domains
from tests.fixtures.reference_tree import reference_root
from tools import misc as ported

pytestmark = pytest.mark.unit

NAMES = (
    'K', 'T', 'freehash', 'OrderedSet', 'LastOrderedSet', 'ReadonlyDict',
    'frozendict', 'StackMap', 'Collector', 'Callbacks', 'ConstantMapping',
    'DotDict', 'Reverse', 'ReversedIterable', 'unquote', 'Sentinel',
    'SENTINEL', '_PrintfArgs', 'discardattr', 'has_list_types', 'is_list_of',
    'split_every', 'str2bool', 'remove_accents', 'clean_context',
)
HEADER = (
    # Como la fuente: sus anotaciones nombran tipos que sólo existen bajo
    # ``typing.TYPE_CHECKING`` (``:52-57``) y no se evalúan al cargar.
    'from __future__ import annotations\n'
    'import collections\n'
    'import enum\n'
    'import itertools\n'
    'import typing\n'
    'import unicodedata\n'
    'import warnings\n'
    'from collections.abc import (Iterable, Iterator, Mapping,\n'
    '    MutableMapping, MutableSet, Reversible)\n'
    'from functools import reduce\n'
    'from itertools import islice\n'
)


@pytest.fixture(scope='module')
def reference():
    root = pathlib.Path(reference_root())
    if not (root / 'odoo' / 'tools' / 'misc.py').is_file():
        pytest.skip('la referencia no está montada en esta sesión')
    return reference_domains.load_misc_definitions(root, NAMES, HEADER)


def outcome(call):
    try:
        value = call()
    except Exception as error:
        return ('raises', type(error).__name__)
    return ('value', type(value).__name__, repr(value))


def collection_trace(module):
    """Lo observable de cada colección, paso a paso."""
    steps = []

    def step(label, call):
        steps.append((label, outcome(call)))

    ordered = module.OrderedSet
    step('OrderedSet order', lambda: list(ordered([3, 1, 3, 2, 1])))
    step('OrderedSet len', lambda: len(ordered('abca')))
    step('OrderedSet contains', lambda: (2 in ordered([1, 2]),
                                         5 in ordered([1, 2])))
    step('OrderedSet repr', lambda: repr(ordered([1, 2])))

    def mutated():
        items = ordered([1, 2, 3])
        items.add(4)
        items.add(1)
        items.discard(2)
        items.discard(9)
        items.update([5, 1, 6])
        return list(items)

    step('OrderedSet mutation', mutated)

    def difference():
        items = ordered([1, 2, 3, 4])
        items.difference_update([2, 4])
        return list(items)

    step('OrderedSet difference_update', difference)
    step('OrderedSet intersection',
         lambda: list(ordered([1, 2, 3, 4]).intersection([4, 2], {2, 4, 9})))
    step('OrderedSet intersection none',
         lambda: list(ordered([1, 2]).intersection()))
    step('OrderedSet copy independent', lambda: (
        lambda items, copy: (copy.add(9), list(items), list(copy))[1:])(
            *(lambda items: (items, items.copy()))(ordered([1]))))
    step('OrderedSet operators', lambda: (
        list(ordered([1, 2]) | ordered([3])),
        list(ordered([1, 2, 3]) & ordered([3, 1])),
        list(ordered([1, 2, 3]) - ordered([2]))))
    step('OrderedSet equality', lambda: (ordered([1, 2]) == {2, 1},
                                         ordered([1, 2]) == ordered([2, 1])))
    step('OrderedSet hash', lambda: hash(ordered([1])))
    step('OrderedSet slots', lambda: ordered.__slots__)

    def last_ordered():
        items = module.LastOrderedSet([1, 2, 3])
        items.add(1)
        copy = items.copy()
        copy.add(2)
        return list(items), list(copy), type(copy).__name__

    step('LastOrderedSet', last_ordered)

    readonly = module.ReadonlyDict({'a': 1, 'b': 2})
    step('ReadonlyDict read', lambda: (readonly['a'], 'b' in readonly,
                                       'z' in readonly, sorted(readonly),
                                       len(readonly)))
    step('ReadonlyDict missing', lambda: readonly['z'])
    step('ReadonlyDict set', lambda: readonly.__setitem__('a', 3))
    step('ReadonlyDict slots', lambda: module.ReadonlyDict.__slots__)

    frozen = module.frozendict({'a': [1, {2}], 'b': 2})
    step('frozendict hash stable',
         lambda: hash(frozen) == hash(module.frozendict(
             {'b': 2, 'a': [1, {2}]})))
    for name, call in (
            ('setitem', lambda: frozen.__setitem__('a', 1)),
            ('delitem', lambda: frozen.__delitem__('a')),
            ('clear', lambda: frozen.clear()),
            ('pop', lambda: frozen.pop('a')),
            ('popitem', lambda: frozen.popitem()),
            ('setdefault', lambda: frozen.setdefault('c', 1)),
            ('update', lambda: frozen.update({'c': 1}))):
        step(f'frozendict {name}', call)
    step('frozendict slots', lambda: module.frozendict.__slots__)

    def stack():
        maps = module.StackMap({'a': 1})
        maps.pushmap({'b': 2})
        maps['c'] = 3
        top = (maps['a'], maps['b'], maps['c'], len(maps), sorted(maps))
        del maps['c']
        popped = maps.popmap()
        return top, popped, str(maps), outcome(lambda: maps['b'])

    step('StackMap', stack)
    step('StackMap delete below', lambda: (
        lambda maps: (maps.pushmap(), maps.__delitem__('a')))(
            module.StackMap({'a': 1})))
    step('StackMap slots', lambda: module.StackMap.__slots__)

    def collector():
        values = module.Collector()
        values.add('a', 1)
        values.add('a', 1)
        values.add('a', 2)
        values['b'] = [3, 3]
        empty = values['z']
        values.discard_keys_and_values(['a', 3])
        return dict(values), empty

    step('Collector', collector)
    step('Collector slots', lambda: module.Collector.__slots__)

    def callbacks():
        calls = []
        hooks = module.Callbacks()
        hooks.add(lambda: calls.append(1))
        hooks.add(lambda: calls.append(2))
        size = len(hooks)
        hooks.run()
        after = len(hooks)
        hooks.add(lambda: calls.append(3))
        hooks.clear()
        hooks.run()
        return calls, size, after, len(hooks), sorted(hooks.data)

    step('Callbacks', callbacks)
    constant = module.ConstantMapping(7)
    step('ConstantMapping', lambda: (constant['any'], constant[None],
                                     len(constant), list(constant)))
    dotted = module.DotDict({'a': {'b': 1}, 'c': [{'d': 2}]})
    step('DotDict nested', lambda: (dotted.a.b, type(dotted.a).__name__,
                                    dotted.c))
    step('DotDict missing', lambda: dotted.missing)
    reverse = module.Reverse
    step('Reverse order', lambda: sorted([3, 1, 2], key=reverse))
    step('Reverse comparisons', lambda: (
        reverse(1) < reverse(2), reverse(1) > reverse(2),
        reverse(1) <= reverse(1), reverse(1) >= reverse(2),
        reverse(1) == reverse(1), reverse(1) != reverse(1)))
    reversed_iterable = module.ReversedIterable([1, 2, 3])
    step('ReversedIterable', lambda: (list(reversed_iterable),
                                      list(reversed(reversed_iterable))))
    step('unquote', lambda: (repr(module.unquote('ref("x")')),
                             str(module.unquote('y'))))
    step('unquote slots', lambda: module.unquote.__slots__)
    step('SENTINEL', lambda: (repr(module.SENTINEL),
                              module.SENTINEL is module.Sentinel.SENTINEL,
                              bool(module.SENTINEL)))
    step('_PrintfArgs', lambda: (
        lambda args: (args['a'], outcome(lambda: args['z'])))(
            module._PrintfArgs({'a': 1})))
    step('_PrintfArgs slots', lambda: module._PrintfArgs.__slots__)
    return steps


def function_trace(module):
    steps = []

    def step(label, call):
        steps.append((label, outcome(call)))

    class Holder:
        value = 1

    def discard():
        holder = Holder()
        holder.value = 2
        module.discardattr(holder, 'value')
        module.discardattr(holder, 'value')
        module.discardattr(holder, 'absent')
        return holder.value

    step('discardattr', discard)
    for value in ([1], [[1]], [(1,)], [1, [2]], [], (1,), 'x',
                  [{'a': 1}]):
        step(f'has_list_types {value!r}',
             lambda v=value: module.has_list_types(v, (list, tuple)))
        step(f'is_list_of {value!r}',
             lambda v=value: module.is_list_of(v, int))
    for size in (1, 2, 3, 5):
        step(f'split_every {size}', lambda n=size: [
            list(chunk) for chunk in module.split_every(n, range(7))])
    step('split_every piece_maker',
         lambda: list(module.split_every(2, 'abcde', ''.join)))
    for text in ('1', 'true', 'True', 'yes', 'on', 'y', 't', '0', 'false',
                 'no', 'off', 'n', 'f', '', 'maybe', ' TRUE ', 1, 0, None):
        step(f'str2bool {text!r}', lambda v=text: module.str2bool(v))
        step(f'str2bool {text!r} default',
             lambda v=text: module.str2bool(v, default='d'))
    for text in ('Ñandú', 'ÉÀÔ', 'ascii', '', 'naïve café'):
        step(f'remove_accents {text!r}',
             lambda v=text: module.remove_accents(v))
    context = {'default_name': 'x', 'search_default_y': 1, 'tz': 'UTC',
               'lang': 'es_MX', 'default_': 2}
    step('clean_context', lambda: sorted(module.clean_context(
        context).items()))
    step('clean_context new', lambda: module.clean_context(context)
         is context)
    return steps


def compare(theirs, ours):
    return [(a[0], a[1], b[1]) for a, b in zip(theirs, ours) if a != b]


#: Los pasos cuyo contrato en la fuente es rehusar. Cualquier otro que rehúse
#: está mal construido: rehusaría igual en los dos lados sin medir nada.
COLLECTION_STEPS_THAT_RAISE = {
    'OrderedSet hash', 'ReadonlyDict missing', 'ReadonlyDict set',
    'frozendict setitem', 'frozendict delitem', 'frozendict clear',
    'frozendict pop', 'frozendict popitem', 'frozendict setdefault',
    'frozendict update', 'StackMap delete below',
}

#: ``str2bool`` sin ``default`` rehúsa todo valor fuera de su vocabulario.
FUNCTION_STEPS_THAT_RAISE = {
    "str2bool ''", "str2bool 'maybe'", "str2bool ' TRUE '", 'str2bool 1',
    'str2bool 0', 'str2bool None',
}


class TestMiscBehavesLikeTheReference:

    def test_only_the_expected_steps_raise_in_the_reference(self, reference):
        raising = {label for label, result in collection_trace(reference)
                   if result[0] == 'raises'}
        assert raising == COLLECTION_STEPS_THAT_RAISE
        raising = {label for label, result in function_trace(reference)
                   if result[0] == 'raises'}
        assert raising == FUNCTION_STEPS_THAT_RAISE

    def test_the_collections_match_the_reference(self, reference):
        theirs, ours = collection_trace(reference), collection_trace(ported)
        assert len(ours) >= 40
        assert not compare(theirs, ours), compare(theirs, ours)[:3]

    def test_the_functions_match_the_reference(self, reference):
        theirs, ours = function_trace(reference), function_trace(ported)
        assert len(ours) >= 60
        assert not compare(theirs, ours), compare(theirs, ours)[:3]
