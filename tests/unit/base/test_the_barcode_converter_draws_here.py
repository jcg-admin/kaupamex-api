"""``ir.qweb.field.barcode`` — el conversor que dibuja, no el que declina.

La clase se declinaba con una razón medida: entonces ninguna dependencia
declaraba un generador de raster. Esa razón caducó sola cuando el porte de
``ir_actions_report.py`` trajo ``python-barcode`` y ``tools/barcode.py`` — hoy
``grep -n "barcode" pyproject.toml`` da **1**, ``pyproject.toml:82``. La cita
va con su valor de hoy y no con el de entonces: un comando emparejado con un
cero caduco es justo lo que ``check_stale_zero_claims.py`` existe para atajar,
y este archivo lo disparó al escribirse. Ver :ref:`h-api-991`.

Estos casos miden **conducta**, no la existencia del símbolo: el PNG que sale
se decodifica y se comprueba que es un PNG, y el marcado se lee por sus
atributos. Un caso que sólo afirmara «no levanta ``NotImplementedError``»
pasaría con un ``return ''`` (sub-patrón D de
``metrica-decide-la-conclusion.md``).
"""
import base64
import re

import pytest

from addons.base.models.ir_field_converters import IrFieldConverterBarcode

#: Los ocho primeros bytes de todo PNG (RFC 2083, §3.1).
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


def src_of(html):
    """El valor del atributo ``src`` del ``<img>`` renderizado."""
    match = re.search(r'src="([^"]*)"', html)
    assert match, f'sin src en {html!r}'
    return match.group(1)


class TestTheEmptyAndTheNonAsciiTakeTheirOwnPaths:
    """Reglas 1 y 2 de la fuente, antes de tocar el dibujante."""

    @pytest.mark.parametrize('value', ['', None, False, 0])
    def test_an_empty_value_gives_an_empty_string(self, value):
        assert IrFieldConverterBarcode.value_to_html(value) == ''

    def test_a_non_ascii_value_is_not_drawn(self):
        out = IrFieldConverterBarcode.value_to_html('códigó')
        assert '<img' not in out
        assert 'c&#x27;' not in out          # se escapa, no se rompe

    def test_a_non_ascii_value_keeps_its_line_breaks(self):
        out = IrFieldConverterBarcode.value_to_html('cañón\nsegunda')
        assert '<br>' in out


class TestThePngComesOutOfTheDrawer:
    """El contrato que la declinación negaba: aquí SÍ hay generador."""

    def test_the_src_carries_a_real_png(self):
        out = IrFieldConverterBarcode.value_to_html('123456789012')
        src = src_of(out)
        assert src.startswith('data:image/png;base64,')
        raw = base64.b64decode(src.removeprefix('data:image/png;base64,'))
        assert raw.startswith(PNG_SIGNATURE), raw[:16]

    def test_the_symbology_option_reaches_the_drawer(self):
        # Dos simbologías distintas sobre el mismo valor dan dibujos
        # distintos. Si la opción se ignorase, los dos PNG serían iguales.
        code128 = src_of(IrFieldConverterBarcode.value_to_html(
            '12345670', options={'symbology': 'Code128'}))
        ean8 = src_of(IrFieldConverterBarcode.value_to_html(
            '12345670', options={'symbology': 'EAN8'}))
        assert code128 != ean8

    def test_the_size_options_reach_the_drawer(self):
        small = src_of(IrFieldConverterBarcode.value_to_html(
            '123456789012', options={'width': 200, 'height': 50}))
        big = src_of(IrFieldConverterBarcode.value_to_html(
            '123456789012', options={'width': 600, 'height': 100}))
        assert small != big


class TestTheMarkupFollowsTheSourceRules:
    """Reglas 3 y 4: la lista blanca de ``img_*`` y el ``alt`` compuesto."""

    def test_without_an_explicit_alt_one_is_composed_with_the_value(self):
        out = IrFieldConverterBarcode.value_to_html('123456789012')
        assert 'alt="Barcode 123456789012"' in out

    def test_an_img_prefixed_option_in_the_allowlist_reaches_the_tag(self):
        out = IrFieldConverterBarcode.value_to_html(
            '123456789012', options={'img_class': 'barcode-print'})
        assert 'class="barcode-print"' in out

    def test_an_img_prefixed_option_outside_the_allowlist_is_dropped(self):
        # ``onerror`` es el caso que la lista blanca existe para detener.
        out = IrFieldConverterBarcode.value_to_html(
            '123456789012', options={'img_onerror': 'alert(1)'})
        assert 'onerror' not in out

    def test_an_explicit_alt_wins_over_the_composed_one(self):
        out = IrFieldConverterBarcode.value_to_html(
            '123456789012', options={'img_alt': 'etiqueta'})
        assert 'alt="etiqueta"' in out
        assert 'Barcode 123456789012' not in out

    def test_the_attribute_value_is_escaped(self):
        out = IrFieldConverterBarcode.value_to_html(
            '123456789012', options={'img_title': 'a"b<c'})
        assert 'a"b<c' not in out
        assert '&quot;' in out or '&#34;' in out
