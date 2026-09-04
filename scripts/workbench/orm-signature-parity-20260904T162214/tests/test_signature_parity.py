"""El test se escribe ANTES del instrumento: fija que se le va a exigir.

Los casos sinteticos miden la MECANICA (que el comparador distinga las siete
formas de divergencia). El control que decide si el instrumento sirve es otro
—``TestTheControlCanFail``— y apunta a un simbolo REAL del arbol, no a uno
fabricado: quien escribe el patron no puede validarlo con su propio encuadre
(``hallazgo-abierto-genera-sucesor.md``).
"""
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from signature_parity import (  # noqa: E402  (el sys.path se arma arriba)
    Divergence,
    compare_file,
    signature_of,
    signatures,
)


def _write(tmp_path, name, body):
    path = tmp_path / name
    path.write_text(body)
    return path


class TestSignatureReading:
    """Que lee ``signatures`` de un archivo, y con que forma."""

    def test_it_reads_the_five_parameter_categories(self, tmp_path):
        path = _write(tmp_path, 'a.py', (
            'def f(po, /, normal, *args, kwonly, **rest):\n'
            '    pass\n'
        ))
        firma = signatures(path)['f']
        assert firma.posonly == ('po',)
        assert firma.args == ('normal',)
        assert firma.vararg == 'args'
        assert firma.kwonly == ('kwonly',)
        assert firma.kwarg == 'rest'

    def test_it_records_which_parameters_carry_a_default(self, tmp_path):
        path = _write(tmp_path, 'a.py', 'def f(a, b=1, *, c, d=2):\n    pass\n')
        firma = signatures(path)['f']
        assert firma.defaults == frozenset({'b', 'd'})

    def test_a_method_is_read_under_its_bare_name(self, tmp_path):
        path = _write(tmp_path, 'a.py', (
            'class C:\n'
            '    def m(self, x):\n'
            '        pass\n'
        ))
        assert 'm' in signatures(path)
        assert signatures(path)['m'].args == ('self', 'x')

    def test_the_first_declaration_wins_when_a_name_repeats(self, tmp_path):
        """Dos clases con el mismo metodo: se compara contra la primera.

        Es una ceguera declarada, no un acierto — el instrumento la publica
        en ``ambiguous`` para que el conteo no la absuelva en silencio.
        """
        path = _write(tmp_path, 'a.py', (
            'class A:\n'
            '    def m(self, x):\n'
            '        pass\n'
            'class B:\n'
            '    def m(self, y, z):\n'
            '        pass\n'
        ))
        assert signatures(path)['m'].args == ('self', 'x')


class TestTheComparison:
    """Que cuenta como divergencia, y con que etiqueta."""

    def _pair(self, tmp_path, ref_src, mine_src):
        ref = _write(tmp_path, 'ref.py', ref_src)
        mine = _write(tmp_path, 'mine.py', mine_src)
        return compare_file(ref, mine)

    def test_an_identical_signature_is_not_a_divergence(self, tmp_path):
        fila = self._pair(tmp_path,
                          'def f(self, a, b=1):\n    pass\n',
                          'def f(self, a, b=1):\n    pass\n')
        assert fila.divergences == []
        assert fila.identical == ['f']

    def test_a_renamed_parameter_is_reported(self, tmp_path):
        fila = self._pair(tmp_path,
                          'def f(self, vals):\n    pass\n',
                          'def f(self, values):\n    pass\n')
        assert [d.symbol for d in fila.divergences] == ['f']
        assert fila.divergences[0].kind == 'renombre'

    def test_a_missing_parameter_is_reported(self, tmp_path):
        fila = self._pair(tmp_path,
                          'def f(self, a, b):\n    pass\n',
                          'def f(self, a):\n    pass\n')
        assert fila.divergences[0].kind == 'parametro_ausente'

    def test_an_extra_parameter_is_reported(self, tmp_path):
        fila = self._pair(tmp_path,
                          'def f(self, a):\n    pass\n',
                          'def f(self, a, b):\n    pass\n')
        assert fila.divergences[0].kind == 'parametro_extra'

    def test_a_reordering_is_reported_and_is_not_a_rename(self, tmp_path):
        fila = self._pair(tmp_path,
                          'def f(self, a, b):\n    pass\n',
                          'def f(self, b, a):\n    pass\n')
        assert fila.divergences[0].kind == 'orden_distinto'

    def test_a_lost_default_is_reported(self, tmp_path):
        fila = self._pair(tmp_path,
                          'def f(self, a=1):\n    pass\n',
                          'def f(self, a):\n    pass\n')
        assert fila.divergences[0].kind == 'default_perdido'

    def test_an_added_default_is_reported(self, tmp_path):
        fila = self._pair(tmp_path,
                          'def f(self, a):\n    pass\n',
                          'def f(self, a=1):\n    pass\n')
        assert fila.divergences[0].kind == 'default_anadido'

    def test_a_dropped_kwargs_is_reported(self, tmp_path):
        fila = self._pair(tmp_path,
                          'def f(self, **kw):\n    pass\n',
                          'def f(self):\n    pass\n')
        assert fila.divergences[0].kind == 'varargs_divergente'

    def test_the_default_VALUE_is_declared_blind(self, tmp_path):
        """Ceguera declarada: se mide la PRESENCIA del default, no su valor."""
        fila = self._pair(tmp_path,
                          'def f(self, a=1):\n    pass\n',
                          'def f(self, a=999):\n    pass\n')
        assert fila.divergences == []

    def test_the_annotation_is_declared_blind(self, tmp_path):
        fila = self._pair(tmp_path,
                          'def f(self, a: int) -> str:\n    pass\n',
                          'def f(self, a):\n    pass\n')
        assert fila.divergences == []

    def test_a_symbol_absent_here_is_not_a_signature_divergence(self, tmp_path):
        """El porte ausente lo mide el censo, no este instrumento.

        Sin esta separacion las dos cifras se suman y el eje de firma queda
        inflado con deuda que ya tiene su propio cubo (sub-patron A).
        """
        fila = self._pair(tmp_path,
                          'def f(self):\n    pass\n'
                          'def g(self):\n    pass\n',
                          'def f(self):\n    pass\n')
        assert fila.divergences == []
        assert fila.not_ported == ['g']

    def test_a_symbol_that_is_not_a_function_here_is_not_comparable(self, tmp_path):
        """Un metodo de la fuente portado como CAMPO no tiene firma que leer.

        Se publica aparte: contarlo como identico seria un verde que no
        discrimina; contarlo como divergencia, una acusacion sin medida.
        """
        fila = self._pair(tmp_path,
                          'def f(self):\n    pass\n',
                          'f = 3\n')
        assert fila.divergences == []
        assert fila.not_ported == ['f']


class TestTheControlCanFail:
    """El control que decide si el instrumento sirve — sobre el arbol REAL.

    Un comparador que devolviera siempre ``[]`` pasa TODOS los casos de
    ``TestTheComparison`` que exigen lista vacia. Estos dos exigen lo
    contrario sobre simbolos que existen en el repo: uno que DEBE salir
    marcado y uno que NO. Sin el par, el verde no distingue «las firmas
    coinciden» de «el instrumento no mira» (sub-patron D).
    """

    def test_a_known_real_divergence_is_flagged(self, real_pair):
        ref, mine, divergente, _ = real_pair
        fila = compare_file(ref, mine)
        marcados = {d.symbol for d in fila.divergences}
        assert divergente in marcados, (
            f'{divergente} diverge en el arbol y el instrumento no lo ve'
        )

    def test_a_known_real_match_is_not_flagged(self, real_pair):
        ref, mine, _, identico = real_pair
        fila = compare_file(ref, mine)
        marcados = {d.symbol for d in fila.divergences}
        assert identico not in marcados, (
            f'{identico} coincide en el arbol y el instrumento lo acusa'
        )


class TestTheInstrumentDeclaresItsScope:
    """Un conteo sin denominador no es un resultado."""

    def test_signature_of_returns_none_for_a_non_function(self, tmp_path):
        path = _write(tmp_path, 'a.py', 'x = 1\n')
        assert signature_of(path, 'x') is None

    def test_a_divergence_carries_both_sides(self, tmp_path):
        ref = _write(tmp_path, 'ref.py', 'def f(self, vals):\n    pass\n')
        mine = _write(tmp_path, 'mine.py', 'def f(self, values):\n    pass\n')
        d = compare_file(ref, mine).divergences[0]
        assert isinstance(d, Divergence)
        assert 'vals' in d.reference and 'values' in d.mine
