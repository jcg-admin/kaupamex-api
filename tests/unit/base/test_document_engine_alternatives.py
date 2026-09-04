r"""Sonda: las alternativas a QWeb para generar un documento, medidas.

Directiva del ejecutor 2026-08-29: *"Si queremos usar DTL, en vez de QWeb es
posible? … si no queremos QWeb qué alternativas tenemos considerando nuestro
stack?"*, sobre un texto que sostiene que *"DTL is designed for HTML
templating, not for API responses"*.

La sonda separa **dos preguntas que ese texto mezcla** y mide cada una:

1. ¿DTL sirve para emitir algo que no sea HTML? — sí, y **Django mismo lo hace**
   (``contrib/sitemaps/templates/sitemap.xml``).
2. ¿DTL sirve para **este** documento? — **depende de la salida**, y ahí está el
   hallazgo: con salida ``dict`` sí; con salida **texto XML** no, por una razón
   medida abajo que no es de estilo.

*Métrica:* la salida de cada motor sobre el mismo juego de datos, validada
después con ``lxml.etree.fromstring``.
*Ciega a:* el rendimiento de cada motor y la ergonomía de escribir la
plantilla — ninguno es medible por una prueba.
"""
import pathlib
import string

import django.contrib.sitemaps as sitemaps
import lxml.etree as ET
import pytest
from django.template import Context, Engine
from django.template.defaultfilters import register as filter_register
from django.utils.html import escape
from lxml.builder import E

#: Un dato con ampersand: el carácter que separa un generador de texto correcto
#: de uno que produce marcado roto.
ROWS = [
    {'name': 'Tornillo & tuerca', 'amount': '10.50'},
    {'name': 'Clavo', 'amount': '2.00'},
]

#: Una plantilla que emite XML, no HTML.
XML_TEMPLATE = '<items>{% for row in rows %}<i n="{{ row.name }}">{{ row.amount }}</i>{% endfor %}</items>'


def is_well_formed(text):
    try:
        ET.fromstring(text)
    except ET.XMLSyntaxError:
        return False
    return True


class TestDtlIsNotTiedToHtml:
    """La premisa del texto, medida: el núcleo de DTL no sabe de HTML."""

    def test_django_itself_ships_dtl_templates_that_emit_xml(self):
        plantilla = pathlib.Path(sitemaps.__file__).parent / 'templates' / 'sitemap.xml'
        contenido = plantilla.read_text(encoding='utf-8')
        # Es una plantilla DTL -tiene sus etiquetas- y su salida es XML.
        assert '{% for url in urlset %}' in contenido
        assert contenido.startswith('<?xml version="1.0"')

    def test_most_builtin_filters_are_format_agnostic(self):
        # El sesgo hacia HTML de DTL vive en su librería de filtros, no en su
        # núcleo: la mayoría no sabe nada de marcado.
        html_aware = {
            'escape', 'escapejs', 'safe', 'safeseq', 'striptags', 'linebreaks',
            'linebreaksbr', 'urlize', 'urlizetrunc', 'force_escape', 'iriencode',
            'urlencode', 'json_script', 'unordered_list', 'linenumbers',
        }
        todos = set(filter_register.filters)
        assert html_aware < todos                      # los 15 existen
        assert len(todos - html_aware) > len(html_aware)  # y son minoría


class TestTheAutoescapeDecisionDependsOnTheOutput:
    """El hallazgo: la misma opción es correcta o incorrecta según el destino."""

    def test_with_autoescape_off_the_ampersand_breaks_the_xml(self):
        engine = Engine(autoescape=False)
        output = engine.from_string(XML_TEMPLATE).render(
            Context({'rows': ROWS}, autoescape=False))
        assert 'n="Tornillo & tuerca"' in output
        assert is_well_formed(output) is False

    def test_with_autoescape_on_the_xml_is_well_formed(self):
        engine = Engine(autoescape=True)
        output = engine.from_string(XML_TEMPLATE).render(Context({'rows': ROWS}))
        assert 'n="Tornillo &amp; tuerca"' in output
        assert is_well_formed(output) is True

    def test_the_django_escape_covers_the_five_xml_entities(self):
        # El escape de HTML resulta ser XML-seguro: `&#x27;` es una referencia
        # numérica válida, no la entidad `&apos;`, pero XML la admite.
        assert escape('& < > " \'') == '&amp; &lt; &gt; &quot; &#x27;'
        assert is_well_formed(f'<r a="{escape(chr(34))}">{escape("& < >")}</r>')


class TestWhereDtlCannotFailAndLxmlCan:
    """Sub-patrón D aplicado a la generación: quién falla en el punto correcto."""

    #: Tabulador vertical: válido en una cadena de Python, PROHIBIDO en XML 1.0.
    CONTROL_CHARACTER = 'linea\x0bcon tabulador vertical'

    def test_dtl_emits_the_forbidden_character_and_fails_later(self):
        engine = Engine(autoescape=True)
        output = engine.from_string('<r><v>{{ d }}</v></r>').render(
            Context({'d': self.CONTROL_CHARACTER}))
        # El motor no se queja: emite el carácter tal cual.
        assert '\x0b' in output
        # El fallo aparece al parsear, es decir en OTRO sitio y más tarde.
        assert is_well_formed(output) is False

    def test_lxml_refuses_at_the_point_of_writing(self):
        # Aquí el error se comete y se detecta en la misma línea.
        with pytest.raises(ValueError, match='All strings must be XML compatible'):
            E.r(E.v(self.CONTROL_CHARACTER))

    def test_lxml_escapes_the_ampersand_by_construction(self):
        node = E.items(*[E.i(row['amount'], n=row['name']) for row in ROWS])
        output = ET.tostring(node, encoding='unicode')
        assert 'n="Tornillo &amp; tuerca"' in output
        assert is_well_formed(output) is True


class TestTheThirdCandidateIsXsltAndItIsInstalled:
    """lxml trae libxslt: transformar XML a XML sin motor de plantillas."""

    def test_libxslt_is_available_and_transforms(self):
        assert hasattr(ET, 'XSLT')
        sheet = ET.XSLT(ET.XML(
            '<xsl:stylesheet version="1.0"'
            ' xmlns:xsl="http://www.w3.org/1999/XSL/Transform">'
            '<xsl:template match="/doc"><out><xsl:value-of select="@n"/></out>'
            '</xsl:template></xsl:stylesheet>'))
        result = str(sheet(ET.XML('<doc n="42"/>')))
        assert '<out>42</out>' in result

    def test_xslt_escapes_by_construction_too(self):
        sheet = ET.XSLT(ET.XML(
            '<xsl:stylesheet version="1.0"'
            ' xmlns:xsl="http://www.w3.org/1999/XSL/Transform">'
            '<xsl:template match="/doc"><out><xsl:value-of select="@n"/></out>'
            '</xsl:template></xsl:stylesheet>'))
        result = str(sheet(ET.XML('<doc n="Tornillo &amp; tuerca"/>')))
        assert '&amp;' in result
        assert is_well_formed(result.split('?>', 1)[-1].strip()) is True


class TestStringSubstitutionIsNotACandidate:
    """Se mide para descartarla con evidencia, no por reputación."""

    def test_it_has_no_iteration_so_the_list_lands_as_its_repr(self):
        output = string.Template('<items>$rows</items>').substitute({'rows': ROWS})
        # No hay bucle: la lista entera se interpola como su repr de Python.
        assert output.startswith("<items>[{'name':")
        assert is_well_formed(output) is False

    def test_and_it_cannot_be_patched_by_xpath(self):
        # La razón de fondo, y la que descarta toda plantilla de texto plano:
        # la herencia entre addons parchea NODOS. Un texto no tiene nodos.
        plain_text = '<items>$rows</items>'
        tree = ET.fromstring(plain_text.replace('$rows', ''))
        assert tree.xpath('//i') == []          # no hay dónde anclar el parche
