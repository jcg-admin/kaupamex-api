"""``tools.parse_version`` medido contra la fuente ejecutada.

Se carga ``odoo19c: odoo/tools/parse_version.py`` por ruta —sólo importa
``re``— y se comparan ``_parse_version_parts`` y ``parse_version`` sobre una
rejilla de versiones con cada pieza que el tokenizador distingue: números,
letras, puntos, guiones, guion bajo, los alias ``pre``/``preview``/``rc``/
``dev``/``saas``/``~`` y la cadena vacía. También se compara el ORDEN que
induce ``parse_version`` sobre la rejilla entera.

*Métrica:* la secuencia de partes, la tupla y el orden resultante.
*Ciega a:* versiones fuera de la rejilla y a toda divergencia que la fuente
comparta con nosotros.
"""
import importlib.util
import pathlib

import pytest

from tools import parse_version as ported

pytestmark = pytest.mark.unit

_REPO = pathlib.Path(__file__).resolve().parents[3]
_SPEC = importlib.util.spec_from_file_location(
    'reference_roots_for_parse_version',
    _REPO / 'scripts' / 'reference_roots.py')
reference_roots = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(reference_roots)

VERSIONS = (
    '', '0', '1', '1.0', '1.0.0', '2.4', '2.4.0', '2.4.1', '2.4-1', '2.4a1',
    '2.4b2', '2.4rc1', '2.4c1', '2.4pre1', '2.4preview', '2.4dev', '2.4.dev3',
    'saas~17.1', 'saas-17.2', '17.0', '17.0.1.0.0', '19.0.1.2', '19.0_1',
    '1.0-final', '1.0.final', '1.0z', '1.0-2', 'v1.2', 'ALPHA', '0.1',
    '10.0', '9.0', '1..2', '1-', '-1', '~1', '1.0~rc2',
)


def reference_module():
    try:
        root = pathlib.Path(reference_roots.tree('odoo19c'))
    except Exception:
        return None
    path = root / 'odoo' / 'tools' / 'parse_version.py'
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location(
        'reference_parse_version', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='module')
def reference():
    module = reference_module()
    if module is None:
        pytest.skip('la referencia no está montada en esta sesión')
    return module


class TestParseVersionMatchesTheReference:

    @pytest.mark.parametrize('version', VERSIONS)
    def test_the_parts_and_the_key_match(self, reference, version):
        assert list(ported._parse_version_parts(version)) == \
            list(reference._parse_version_parts(version))
        assert ported.parse_version(version) == \
            reference.parse_version(version)

    def test_the_induced_order_matches(self, reference):
        assert sorted(VERSIONS, key=ported.parse_version) == \
            sorted(VERSIONS, key=reference.parse_version)


class TestParseVersionLiterally:
    """Casos escritos a mano: el diferencial no dice cuál se rompió."""

    def test_a_trailing_zero_does_not_count(self):
        assert ported.parse_version('2.4.0') == ported.parse_version('2.4')

    def test_a_release_candidate_comes_before_the_release(self):
        assert ported.parse_version('2.4rc1') < ported.parse_version('2.4')

    def test_numbers_compare_numerically(self):
        assert ported.parse_version('10.0') > ported.parse_version('9.0')
