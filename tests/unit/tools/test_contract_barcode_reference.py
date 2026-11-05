"""``tools.barcode`` —sus dos funciones de dígito— contra la fuente ejecutada.

Se carga ``odoo19c: odoo/tools/barcode.py`` por ruta —en el tope sólo importa
``functools``, ``re`` y ``threading``; ``reportlab`` va dentro de las
funciones de dibujo, que no se llaman— y se comparan
``get_barcode_check_digit`` y ``check_barcode_encoding`` sobre códigos de cada
codificación GS1, válidos e inválidos.

Las tres funciones de dibujo (``_init_barcode``, ``createBarcodeDrawing``,
``get_barcode_font``) no entran: el puerto no las declara.

*Métrica:* el valor devuelto —o el nombre de la excepción— por código y
codificación.
*Ciega a:* códigos fuera de la rejilla y a toda divergencia que la fuente
comparta con nosotros.
"""
import importlib.util
import itertools
import pathlib

import pytest

from tools import barcode as ported

pytestmark = pytest.mark.unit

_REPO = pathlib.Path(__file__).resolve().parents[3]
_SPEC = importlib.util.spec_from_file_location(
    'reference_roots_for_barcode', _REPO / 'scripts' / 'reference_roots.py')
reference_roots = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(reference_roots)

CODES = (
    '96385074', '96385075', '4006381333931', '4006381333932',
    '0006381333931', '0036000291452', '036000291452', '036000291453',
    '10614141000415',
    '00106141412345678908', '106141412345678908', '12345', '',
    '40063813339a1', '4006381333931 ', '1', '00',
)
ENCODINGS = ('any', 'ANY', 'ean8', 'EAN13', 'ean13', 'gtin14', 'upca',
             'sscc', 'code128')


def reference_module():
    try:
        root = pathlib.Path(reference_roots.tree('odoo19c'))
    except Exception:
        return None
    path = root / 'odoo' / 'tools' / 'barcode.py'
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location('reference_barcode', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='module')
def reference():
    module = reference_module()
    if module is None:
        pytest.skip('la referencia no está montada en esta sesión')
    return module


def outcome(call):
    try:
        value = call()
    except Exception as error:
        return ('raises', type(error).__name__)
    return ('value', type(value).__name__, value)


class TestBarcodeMatchesTheReference:

    @pytest.mark.parametrize('code', CODES)
    def test_the_check_digit_matches(self, reference, code):
        assert outcome(lambda: ported.get_barcode_check_digit(code)) == \
            outcome(lambda: reference.get_barcode_check_digit(code))

    def test_every_encoding_check_matches(self, reference):
        divergences = [
            (code, encoding)
            for code, encoding in itertools.product(CODES, ENCODINGS)
            if outcome(lambda c=code, e=encoding:
                       ported.check_barcode_encoding(c, e))
            != outcome(lambda c=code, e=encoding:
                       reference.check_barcode_encoding(c, e))]
        assert not divergences, divergences[:3]


class TestBarcodeLiterally:
    """Casos escritos a mano: el diferencial no dice cuál se rompió."""

    def test_a_valid_ean13_passes(self):
        assert ported.check_barcode_encoding('4006381333931', 'ean13')

    def test_an_ean13_cannot_start_with_zero(self):
        # Un UPC-A rellenado con cero: dígito de control válido, así que sólo
        # la regla del cero inicial lo rechaza.
        assert ported.check_barcode_encoding('036000291452', 'upca')
        assert not ported.check_barcode_encoding('0036000291452', 'ean13')

    def test_the_check_digit_of_an_ean8(self):
        assert ported.get_barcode_check_digit('96385074') == 4
