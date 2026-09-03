"""Contrato de ``tools.i18n`` — enumeración de listas y código de idioma.

Fuente: ``odoo19c: odoo/tools/i18n.py``. Sin pruebas propias allá; estos casos
miden los dos contratos que sus consumidores usan: el conector del idioma en
una enumeración y la traducción XPG → BCP 47 que consume el cliente.

Dos controles pueden fallar y son los que dan valor a la suite:

* la **degradación de estilo** se mide con un estilo que el idioma **no
  declara** (``standard-short`` no está en ``es_MX``). Si la degradación no
  existiera, ``lists.format_list`` levantaría y el caso lo vería; con un
  estilo que sí existe, el caso pasaría en verde diga lo que diga el código.
* el **orden de las subetiquetas** de ``py_to_js_locale``: BCP 47 pone el
  script antes de la región. Un caso con sólo ``sr@latin`` no distingue el
  orden correcto del inverso — hace falta ``sr_RS@latin``.
"""
import pytest

from tools.i18n import XPG_LOCALE_RE, format_list, py_to_js_locale
from tools.misc import babel_locale_parse


class TestPyToJsLocale:
    """XPG (Python) → BCP 47 (JavaScript)."""

    @pytest.mark.parametrize('python_code, js_code', [
        ('fr_BE', 'fr-BE'),
        ('es_MX', 'es-MX'),
        ('en', 'en'),
        ('pt_BR', 'pt-BR'),
    ])
    def test_the_underscore_becomes_a_hyphen(self, python_code, js_code):
        assert py_to_js_locale(python_code) == js_code

    def test_the_serbian_modifier_becomes_a_script_subtag(self):
        assert py_to_js_locale('sr@latin') == 'sr-Latn'
        assert py_to_js_locale('sr@Cyrl') == 'sr-Cyrl'

    def test_the_script_subtag_precedes_the_region(self):
        # El control de orden: BCP 47 es
        # ``language[-extlang][-script][-region]``. Con un código sin
        # territorio los dos órdenes darían el mismo resultado.
        assert py_to_js_locale('sr_RS@latin') == 'sr-Latn-RS'
        assert py_to_js_locale('sr_RS@Cyrl') == 'sr-Cyrl-RS'

    def test_an_unknown_modifier_is_dropped_and_the_rest_survives(self):
        # Sólo los dos del serbio se traducen; el resto no tiene subetiqueta
        # que le corresponda y la fuente lo descarta sin tocar lo demás.
        assert py_to_js_locale('de_DE@euro') == 'de-DE'

    @pytest.mark.parametrize('unmatched', [
        'en_US.UTF-8',   # con codeset: la fuente declara que NO lo admite
        'EN_us',         # el idioma va en minúscula
        'zh-Hans',       # ya viene en la forma BCP 47
        '',
    ])
    def test_what_does_not_match_is_returned_untouched(self, unmatched):
        assert not XPG_LOCALE_RE.match(unmatched)
        assert py_to_js_locale(unmatched) == unmatched


class TestFormatList:
    """El conector del idioma — ``env`` se acepta y no se consume."""

    def test_the_connector_comes_from_the_language(self):
        assert format_list(None, ['a', 'b', 'c'], lang_code='es_MX') == 'a, b y c'
        assert format_list(None, ['a', 'b', 'c'], lang_code='en_US') == 'a, b, and c'

    def test_the_or_style_uses_the_disjunctive_connector(self):
        assert format_list(None, ['a', 'b', 'c'], 'or', 'es_MX') == 'a, b o c'
        assert format_list(None, ['a', 'b', 'c'], 'or', 'en_US') == 'a, b, or c'

    def test_a_style_the_language_does_not_declare_degrades_to_standard(self):
        # ``es_MX`` no declara ``standard-short``; ``en_US`` sí. El mismo estilo
        # da la enumeración larga en uno y la corta en el otro: eso es lo que
        # prueba que la degradación ocurre y no que el estilo se ignore.
        assert 'standard-short' not in babel_locale_parse('es_MX').list_patterns
        assert 'standard-short' in babel_locale_parse('en_US').list_patterns

        assert format_list(None, ['a', 'b', 'c'], 'standard-short',
                           'es_MX') == 'a, b y c'
        assert format_list(None, ['a', 'b', 'c'], 'standard-short',
                           'en_US') == 'a, b, & c'

    def test_an_unknown_language_falls_back_instead_of_raising(self):
        # ``babel_locale_parse`` nunca lanza: quien formatea está mostrando.
        assert format_list(None, ['a', 'b'], lang_code='xx_YY')

    @pytest.mark.parametrize('elements, expected', [
        ([], ''),
        (['a'], 'a'),
        (['a', 'b'], 'a y b'),
    ])
    def test_the_short_lists_have_their_own_pattern(self, elements, expected):
        assert format_list(None, elements, lang_code='es_MX') == expected

    def test_the_elements_are_coerced_with_str(self):
        assert format_list(None, [1, 2, 3], lang_code='es_MX') == '1, 2 y 3'

    def test_an_iterable_that_is_not_a_list_is_accepted(self):
        assert format_list(None, (x for x in 'abc'), lang_code='es_MX') == 'a, b y c'

    def test_the_env_is_accepted_and_never_touched(self):
        # La divergencia declarada en el docstring del puerto: la firma
        # conserva ``env`` por fidelidad de contrato y el cuerpo no lo consume.
        # Un objeto que revienta ante cualquier acceso lo demuestra.
        class ExplodingEnv:
            def __getattr__(self, name):
                raise AssertionError(f'format_list tocó env.{name}')

            def __getitem__(self, key):
                raise AssertionError(f'format_list tocó env[{key!r}]')

        assert format_list(ExplodingEnv(), ['a', 'b'],
                           lang_code='es_MX') == 'a y b'
