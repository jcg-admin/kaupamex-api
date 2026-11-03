"""Los símbolos puros de ``odoo19c: odoo/tools/misc.py`` que faltaban.

Los valores esperados salen de los docstrings y doctests de la fuente.
"""

import logging
import warnings

import babel
import pytest

from tools import misc


def test_flatten_is_deprecated_and_flattens():
    with pytest.warns(DeprecationWarning, match='deprecated since 18.0'):
        nested = [[['a', 'b'], 'c'], 'd', ['e', [], 'f']]
        assert misc.flatten(nested) == list('abcdef')
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', DeprecationWarning)
        t = (1, 2, (3,), [4, 5, [6, [7], (8, 9), ([10, 11, (12, 13)]),
                                 [14, [], (15,)], []]])
        assert misc.flatten(t) == list(range(1, 16))
        assert misc.flatten('b') == ['b']


def test_reverse_enumerate():
    pairs = list(misc.reverse_enumerate(['a', 'b', 'c']))
    assert pairs == [(2, 'c'), (1, 'b'), (0, 'a')]


def test_topological_sort_lists_dependencies_first():
    graph = {'c': ['b'], 'b': ['a'], 'a': [], 'd': ['z']}
    assert misc.topological_sort(graph) == ['a', 'b', 'c', 'd']


def test_merge_sequences_follows_the_partial_order():
    assert misc.merge_sequences(['A', 'B', 'C']) == ['A', 'B', 'C']
    merged = misc.merge_sequences(['A', 'B', 'C'], ['Z'], ['Y', 'C'],
                                  ['A', 'X', 'Y'])
    assert merged == ['A', 'B', 'X', 'Y', 'C', 'Z']


def test_get_iso_codes():
    assert misc.get_iso_codes('fr_FR') == 'fr'
    assert misc.get_iso_codes('es_MX') == 'es_MX'
    assert misc.get_iso_codes('en') == 'en'


def test_mod10r():
    assert misc.mod10r('1234') == '12347'
    assert misc.mod10r('12 34') == '12 347'


def test_human_size():
    assert misc.human_size(0) is False
    assert misc.human_size(2048) == '2.00 Kb'
    assert misc.human_size('abc') == '3.00 bytes'


def test_get_flag():
    assert misc.get_flag('MX') == '\U0001F1F2\U0001F1FD'


def test_submap_keeps_only_the_given_keys():
    picked = misc.submap({'a': 1, 'b': 2, 'c': 3}, ['a', 'c', 'z'])
    assert picked == {'a': 1, 'c': 3}


def test_constant_mapping():
    mapping = misc.ConstantMapping(7)
    assert mapping['anything'] == 7
    assert len(mapping) == 0 and list(mapping) == []


def test_reverse_inverts_the_ordering():
    assert sorted([1, 3, 2], key=misc.Reverse) == [3, 2, 1]
    assert misc.Reverse(1) == misc.Reverse(1)
    assert misc.Reverse(1) != misc.Reverse(2)


def test_reversed_iterable():
    iterable = misc.ReversedIterable([1, 2, 3])
    assert list(iterable) == [3, 2, 1]
    assert list(reversed(iterable)) == [1, 2, 3]


def test_callbacks_run_in_order_and_clear():
    calls, callbacks = [], misc.Callbacks()
    callbacks.add(lambda: calls.append(1))
    callbacks.add(lambda: calls.append(2))
    callbacks.data['k'] = 'v'
    assert len(callbacks) == 2
    callbacks.run()
    assert calls == [1, 2] and len(callbacks) == 0 and callbacks.data == {}


def test_mute_logger_as_context_and_decorator(caplog):
    logger = logging.getLogger('kaupamex.test.mute')
    with caplog.at_level(logging.WARNING):
        with misc.mute_logger('kaupamex.test.mute'):
            logger.warning('silenciado')

        @misc.mute_logger('kaupamex.test.mute')
        def noisy():
            logger.warning('tambien')
        noisy()
    assert 'silenciado' not in caplog.text and 'tambien' not in caplog.text


def test_lower_logging_lowers_errors_and_munges_tracebacks():
    records = []

    class Collect(logging.Handler):
        def emit(self, record):
            records.append((record.levelname, record.getMessage()))

    root = logging.getLogger()
    collect = Collect(level=logging.DEBUG)
    root.addHandler(collect)
    old_level = root.level
    root.setLevel(logging.DEBUG)
    try:
        with misc.lower_logging(logging.WARNING, logging.INFO) as lowered:
            logging.getLogger('kaupamex.test.lower').error(
                'Traceback (most recent call last): x')
        assert lowered.had_error_log is True
    finally:
        root.removeHandler(collect)
        root.setLevel(old_level)
    assert records == [('_ERROR', '_Traceback_ (most recent call last): x')]


def test_replace_exceptions_copies_the_message():
    with pytest.raises(KeyError, match='oculto'):
        with misc.replace_exceptions(ValueError, by=KeyError):
            raise ValueError('oculto')
    with pytest.raises(ValueError, match='Missing exceptions'):
        misc.replace_exceptions(by=KeyError)
    with pytest.raises(TypeError, match='is not an exception class'):
        misc.replace_exceptions(int, by=KeyError)


def test_posix_to_ldml():
    locale = babel.Locale.parse('en_US')
    assert misc.posix_to_ldml('%d/%m/%Y', locale) == 'dd/MM/yyyy'
    ldml = misc.posix_to_ldml('%-d %B, at %H:%M', locale)
    assert ldml == "d MMMM, 'at' HH:mm"
    short = locale.date_formats['short'].pattern
    assert misc.posix_to_ldml('%x', locale) == short
