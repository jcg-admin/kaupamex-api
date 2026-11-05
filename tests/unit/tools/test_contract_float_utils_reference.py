"""``tools.float_utils`` medido contra la fuente ejecutada.

Se carga ``odoo19c: odoo/tools/float_utils.py`` por ruta —sólo importa la
biblioteca estándar— y se compara cada función con la nuestra sobre una
rejilla de valores elegida en los bordes que el redondeo decimal tiene que
resolver: empates exactos, empates que el binario representa por debajo
(``2.675``), negativos, ceros con signo y magnitudes grandes.

Además de la conducta se compara la superficie: ``__all__`` y el ``round``
de módulo que la fuente declara —su *shim* de redondeo con empate alejado de
cero—, que es un símbolo con nombre propio y no un detalle interno.

*Métrica:* el valor devuelto —o el nombre de la excepción— de cada función
pública sobre su rejilla, comparando ``float`` por su ``repr`` para no
confundir ``-0.0`` con ``0.0``.
*Ciega a:* valores fuera de la rejilla, y a toda divergencia que la fuente
comparta con nosotros, porque el oráculo es ella.
"""
import builtins
import importlib.util
import itertools
import pathlib

import pytest

from tools import float_utils as ported

pytestmark = pytest.mark.unit

_REPO = pathlib.Path(__file__).resolve().parents[3]
_SPEC = importlib.util.spec_from_file_location(
    'reference_roots_for_float_utils',
    _REPO / 'scripts' / 'reference_roots.py')
reference_roots = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(reference_roots)

VALUES = (
    0.0, -0.0, 0.5, -0.5, 1.5, 2.5, -2.5, 2.675, -2.675, 1.005, 0.125,
    0.3, 1e-10, -1e-10, 12.00000000000047, 123456789.125, 0.0049999,
    0.005, -0.005, 99.995, 7, -3, 1e15 + 0.3,
)
METHODS = ('UP', 'DOWN', 'HALF-UP', 'HALF-DOWN', 'HALF-EVEN', 'SIDEWAYS')
DIGITS = (0, 1, 2, 3, 5)
ROUNDINGS = (0.01, 0.05, 0.5, 1.0, 0.001, 0.25)


def reference_module():
    try:
        root = pathlib.Path(reference_roots.tree('odoo19c'))
    except Exception:
        return None
    path = root / 'odoo' / 'tools' / 'float_utils.py'
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location(
        'reference_float_utils', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='module')
def reference():
    module = reference_module()
    if module is None:
        pytest.skip('la referencia no está montada en esta sesión')
    return module


def normalize(value):
    if isinstance(value, float):
        return ('float', repr(value))
    if isinstance(value, tuple):
        return tuple(normalize(item) for item in value)
    return (type(value).__name__, value)


def outcome(call):
    try:
        return ('value', normalize(call()))
    except Exception as error:
        return ('raises', type(error).__name__)


def calls(module):
    grid = []
    for value in VALUES:
        grid += [
            (f'round({value})', lambda v=value: module.round(v)),
            (f'float_invert({value})', lambda v=value: module.float_invert(v)),
        ]
        for digits, method in itertools.product(DIGITS, METHODS):
            grid.append((
                f'float_round({value}, {digits}, {method})',
                lambda v=value, d=digits, m=method: module.float_round(
                    v, precision_digits=d, rounding_method=m)))
        for rounding in ROUNDINGS:
            grid += [
                (f'float_round({value}, rounding={rounding})',
                 lambda v=value, r=rounding: module.float_round(
                     v, precision_rounding=r)),
                (f'float_is_zero({value}, rounding={rounding})',
                 lambda v=value, r=rounding: module.float_is_zero(
                     v, precision_rounding=r)),
            ]
        for digits in DIGITS:
            grid += [
                (f'float_is_zero({value}, {digits})',
                 lambda v=value, d=digits: module.float_is_zero(
                     v, precision_digits=d)),
                (f'float_repr({value}, {digits})',
                 lambda v=value, d=digits: module.float_repr(v, d)),
                (f'float_split_str({value}, {digits})',
                 lambda v=value, d=digits: module.float_split_str(v, d)),
                (f'float_split({value}, {digits})',
                 lambda v=value, d=digits: module.float_split(v, d)),
                (f'json_float_round({value}, {digits})',
                 lambda v=value, d=digits: module.json_float_round(v, d)),
            ]
        for other in (value, value + 0.004, value - 0.006, 0.0):
            grid.append((
                f'float_compare({value}, {other}, 2)',
                lambda v=value, o=other: module.float_compare(
                    v, o, precision_digits=2)))
            grid.append((
                f'float_compare({value}, {other}, rounding=0.05)',
                lambda v=value, o=other: module.float_compare(
                    v, o, precision_rounding=0.05)))
    grid += [
        ('both precisions', lambda: module.float_round(
            1.0, precision_digits=2, precision_rounding=0.01)),
        ('no precision', lambda: module.float_is_zero(1.0)),
        ('negative rounding', lambda: module.float_round(
            1.0, precision_rounding=-0.01)),
        ('json HALF-DOWN', lambda: module.json_float_round(
            2.675, 2, rounding_method='HALF-DOWN')),
        ('check precision digits',
         lambda: module._float_check_precision(precision_digits=3)),
        ('check precision rounding',
         lambda: module._float_check_precision(precision_rounding=0.25)),
    ]
    return grid


class TestTheSurfaceMatchesTheReference:

    def test_the_exports_are_the_reference_exports(self, reference):
        assert ported.__all__ == reference.__all__

    def test_round_is_declared_by_its_reference_name(self, reference):
        assert callable(getattr(ported, 'round', None))
        assert ported.round is not builtins.round


class TestTheFunctionsMatchTheReference:

    def test_every_call_returns_what_the_reference_returns(self, reference):
        theirs, ours = calls(reference), calls(ported)
        divergences = []
        for (label, their_call), (_label, our_call) in zip(theirs, ours):
            expected, actual = outcome(their_call), outcome(our_call)
            if expected != actual:
                divergences.append((label, expected, actual))
        assert len(theirs) >= 1700
        assert not divergences, (
            f'{len(divergences)} de {len(theirs)} llamadas divergen; '
            f'las tres primeras: {divergences[:3]}')


class TestFloatUtilsLiterally:
    """Casos escritos a mano: el diferencial no dice cuál se rompió."""

    def test_a_half_rounds_away_from_zero(self):
        assert ported.round(2.5) == 3.0
        assert ported.round(-2.5) == -3.0

    def test_round_keeps_the_sign_of_zero(self):
        assert repr(ported.round(-0.0)) == '-0.0'

    def test_a_binary_tie_still_rounds_up(self):
        assert ported.float_round(2.675, precision_digits=2) == 2.68
