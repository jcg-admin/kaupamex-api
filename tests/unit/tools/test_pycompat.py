"""``tools.pycompat`` — los tres puentes que la fuente conserva avisando.

Los tres estan marcados obsoletos desde Odoo 18.0 y se portan **con su
aviso**: retirarlos aqui adelantaria una retirada que la referencia no ha
hecho, y su contrato —que el stream sea de bytes, no de texto— es justo lo que
sus asserts protegen.

Los casos se escribieron ANTES del modulo.
"""
import io

import pytest

from tools.pycompat import csv_reader, csv_writer, to_text


class TestCsvReader:
    def test_it_reads_a_byte_stream(self):
        stream = io.BytesIO('a,b\nñ,2\n'.encode())
        with pytest.warns(DeprecationWarning):
            rows = list(csv_reader(stream))
        assert rows == [['a', 'b'], ['ñ', '2']]

    def test_it_refuses_a_text_stream(self):
        """El assert es el contrato: por compatibilidad toma bytes."""
        with pytest.warns(DeprecationWarning), pytest.raises(AssertionError):
            csv_reader(io.StringIO('a,b\n'))


class TestCsvWriter:
    def test_it_writes_a_byte_stream(self):
        stream = io.BytesIO()
        with pytest.warns(DeprecationWarning):
            writer = csv_writer(stream)
        writer.writerow(['ñ', '2'])
        assert stream.getvalue().decode() == 'ñ,2\r\n'

    def test_it_refuses_a_text_stream(self):
        with pytest.warns(DeprecationWarning), pytest.raises(AssertionError):
            csv_writer(io.StringIO())


class TestToText:
    """Las cuatro ramas que el docstring de la fuente enumera."""

    @pytest.mark.parametrize('given, expected', [
        (None, ''),
        (False, ''),
        ('ya es texto', 'ya es texto'),
        ('ñandú'.encode(), 'ñandú'),
        (42, '42'),
        (0, '0'),
    ])
    def test_it_textifies(self, given, expected):
        with pytest.warns(DeprecationWarning):
            assert to_text(given) == expected

    def test_the_zero_is_not_the_false(self):
        """El control: ``False`` da vacio, pero ``0`` da «0».

        Sin este caso la rama ``source is False`` y la caida a ``str()`` no se
        distinguirian — ``0 == False`` en Python.
        """
        with pytest.warns(DeprecationWarning):
            assert to_text(False) == ''
            assert to_text(0) == '0'
