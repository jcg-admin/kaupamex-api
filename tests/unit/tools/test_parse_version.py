"""``tools.parse_version`` — la key de version ordenable cronologicamente.

La fuente no tiene archivo de prueba para este modulo: lleva su verificacion
dentro de un bloque ``if __name__ == '__main__'``
(``odoo19c: odoo/tools/parse_version.py:65-79``), que nadie ejecuta en la
suite. Aqui esas dos cadenas son el nucleo de la prueba, y el hogar del
control es este archivo — no un bloque que solo corre a mano.

Los casos se escribieron ANTES del modulo: contra un
``src/tools/parse_version.py`` inexistente el archivo entero falla en la
importacion.
"""
import pytest

from tools.parse_version import parse_version


class TestChronologicalOrder:
    """Lo que la fuente afirma en su bloque de auto-verificacion."""

    @pytest.mark.parametrize('series', [
        ('0', '4.2', '4.2.3.4', '5.0.0-alpha', '5.0.0-rc1', '5.0.0-rc1.1',
         '5.0.0_rc2', '5.0.0_rc3', '5.0.0'),
        ('5.0.0-0_rc3', '5.0.0-1dev', '5.0.0-1'),
    ])
    def test_the_series_grows(self, series):
        keys = [parse_version(v) for v in series]
        for before, after in zip(keys, keys[1:]):
            assert before < after, f'{before} < {after}'


class TestDocumentedContract:
    """Cada afirmacion del docstring de la fuente, como un caso medible."""

    def test_the_trailing_zero_does_not_count(self):
        """«2.4.0 se considera lo mismo que 2.4»."""
        assert parse_version('2.4.0') == parse_version('2.4')

    def test_the_dash_is_a_patch_level(self):
        """«2.4.1 es mas nuevo que 2.4-1, que a su vez es mas nuevo que 2.4»."""
        assert parse_version('2.4') < parse_version('2.4-1')
        assert parse_version('2.4-1') < parse_version('2.4.1')

    def test_the_prerelease_comes_before_its_release(self):
        """«2.4 es mas nuevo que 2.4a1»."""
        assert parse_version('2.4a1') < parse_version('2.4')

    @pytest.mark.parametrize('label', ['pre', 'preview', 'rc'])
    def test_the_three_aliases_mean_candidate(self, label):
        """«pre», «preview» y «rc» se tratan como si fueran «c»."""
        assert parse_version(f'2.4{label}1') == parse_version('2.4c1')

    def test_it_lowercases(self):
        assert parse_version('2.4RC1') == parse_version('2.4rc1')

    def test_the_numeric_part_is_padded_to_eight(self):
        """El relleno es lo que hace que 10 sea mayor que 9 como cadena."""
        assert parse_version('9') < parse_version('10')
        assert '00000009' in parse_version('9')

    def test_it_ends_in_the_final_marker(self):
        """El centinela ``*final`` deja alpha/beta/candidate por debajo."""
        assert parse_version('2.4')[-1] == '*final'

    def test_it_returns_a_tuple_of_strings(self):
        key = parse_version('1.2.3')
        assert isinstance(key, tuple)
        assert all(isinstance(p, str) for p in key)


class TestEmptyInput:
    """La fuente sustituye lo empty por ``0.1`` — no levanta."""

    @pytest.mark.parametrize('empty', ['', None])
    def test_the_empty_becomes_the_default(self, empty):
        assert parse_version(empty) == parse_version('0.1')


class TestReferenceOwnDialect:
    """Dos reemplazos que la fuente añade sobre setuptools 0.6c8."""

    def test_saas_disappears(self):
        """El prefijo ``saas`` de sus propias versiones no pesa."""
        assert parse_version('saas~15.4') == parse_version('15.4')

    def test_dev_sorts_before_everything(self):
        """``dev`` se sustituye por ``@``, que precede a toda letra."""
        assert parse_version('1.0dev') < parse_version('1.0a')
