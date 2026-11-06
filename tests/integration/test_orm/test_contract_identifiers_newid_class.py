"""Contrato de ``NewId`` — ``odoo19c: odoo/orm/identifiers.py``.

Dos oráculos independientes del código bajo prueba:

1. **Diferencial**: se ejecuta el ``NewId`` de la propia referencia (Python
   puro: sólo ``functools`` y ``typing``) y se compara con el nuestro sobre una
   matriz de ``origin``/``ref`` y de operaciones. El módulo se compila desde su
   texto, sin importarlo, para no escribir ``__pycache__`` en ``odoo-tools``.
2. **Literal**: valores leídos del cuerpo de la referencia (``:12-50``), que
   discriminan aunque el árbol no esté montado.

Mutaciones que lo hacen caer: ``__bool__`` que devuelve ``True``; ``__eq__``
que compara sólo ``origin``; ``__lt__`` que trata un ``NewId`` sin origen como
menor; ``__hash__`` sin ``ref``; ``__str__`` con otro prefijo.
"""
import itertools
import pathlib
import types

import pytest

import reference_roots
from orm.identifiers import NewId

pytestmark = pytest.mark.integration

REFERENCE_FILE = (reference_roots.tree('odoo19c')
                  / 'odoo' / 'orm' / 'identifiers.py')

ORIGINS = (None, 0, 5, 7)
REFS = (None, '', 'r', 'x')
PAIRS = list(itertools.product(ORIGINS, REFS))


def _reference_newid():
    source = pathlib.Path(REFERENCE_FILE).read_text()
    module = types.ModuleType('reference_identifiers')
    exec(compile(source, str(REFERENCE_FILE), 'exec'), module.__dict__)
    return module.NewId


def _outcome(call):
    try:
        return ('ok', call())
    except Exception as error:
        return ('raise', type(error).__name__)


def _normalised(text, instance):
    """``repr``/``str`` llevan ``id(self)`` cuando no hay origen ni ref."""
    return text.replace(f'{id(instance):x}', 'ID')


def _behaviour(cls):
    rows = []
    for origin, ref in PAIRS:
        left = cls(origin, ref)
        rows.append(('bool', origin, ref, bool(left)))
        rows.append(('repr', origin, ref, _normalised(repr(left), left)))
        rows.append(('str', origin, ref, _normalised(str(left), left)))
        for other_origin, other_ref in PAIRS:
            right = cls(other_origin, other_ref)
            key = (origin, ref, other_origin, other_ref)
            rows.append(('eq', key, left == right))
            if left == right:
                rows.append(('hash', key, hash(left) == hash(right)))
            for name, operation in (('lt', lambda a, b: a < b),
                                    ('le', lambda a, b: a <= b),
                                    ('gt', lambda a, b: a > b)):
                rows.append((name, key, _outcome(
                    lambda: operation(left, right))))
        for number in (0, 3, 6):
            rows.append(('lt_int', origin, ref, number,
                         _outcome(lambda: left < number)))
    return rows


@pytest.mark.reference
@pytest.mark.skipif(
    not REFERENCE_FILE.is_file(),
    reason=f'referencia ausente: {REFERENCE_FILE} no existe (odoo-tools no '
           'montado; ver referencia-odoo-gobierna-las-decisiones.md)')
class TestNewIdBehavesLikeTheReference:

    def test_every_operation_matches_the_reference_class(self):
        expected = _behaviour(_reference_newid())
        observed = _behaviour(NewId)
        mismatches = [(e, o) for e, o in zip(expected, observed) if e != o]
        assert len(expected) == len(observed)
        assert not mismatches, mismatches[:5]


class TestNewIdLiteralContract:

    def test_it_is_always_falsy(self):
        assert not NewId(origin=5)
        assert not NewId(ref='r')

    def test_equality_by_origin_or_by_ref_only(self):
        assert NewId(origin=5) == NewId(origin=5, ref='a')
        assert NewId(ref='r') == NewId(origin=None, ref='r')
        assert NewId() != NewId()
        assert NewId(origin=5) != 5

    def test_the_hash_follows_origin_then_ref(self):
        assert hash(NewId(ref='r')) == hash('r')
        assert hash(NewId(origin=5, ref='r')) == hash(5)

    def test_ordering_against_ints_uses_the_origin(self):
        assert NewId(origin=5) < 7
        assert not NewId() < 7

    def test_an_origin_against_a_newid_without_origin_raises(self):
        """``:33`` evalúa ``other > self.origin`` con ``other = None``."""
        with pytest.raises(TypeError):
            NewId(origin=5) < NewId()
        assert not NewId() < NewId()

    def test_text_forms(self):
        assert repr(NewId(origin=5)) == '<NewId origin=5>'
        assert repr(NewId(ref='r')) == "<NewId ref='r'>"
        assert str(NewId(origin=5)) == 'NewId_5'
        assert str(NewId(ref='r')) == "NewId_'r'"

    def test_slots_reject_new_attributes(self):
        with pytest.raises(AttributeError):
            NewId().extra = 1
