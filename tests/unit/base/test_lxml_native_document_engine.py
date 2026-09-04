r"""Sonda: hasta dónde llega lxml solo, sin motor de plantillas encima.

Pregunta del ejecutor 2026-08-29: *"¿y porque no lxml o lxml.etree? ¿de forma
nativa?"*.

La sonda mide las tres piezas que la respuesta necesita, y ninguna se afirma de
memoria:

1. **Qué hace XPath 1.0** sobre un árbol — y dónde se queda corto.
2. **Por qué no puede evaluar el valor de una hoja del descriptor hoy** — el
   nodo de contexto tiene que ser un ``Element``, y el nuestro es un objeto del
   ORM.
3. **Qué se abre si el dato se serializa a XML primero** — XSLT cubre entonces
   estructura, aritmética y formato, con una puerta de escape a Python… y con
   una superficie de ataque que hay que cerrar explícitamente.

*Métrica:* la conducta de ``lxml.etree`` 5.x con libxml2 (2, 14, 6) y libxslt
(1, 1, 43) instalados.
*Ciega a:* el coste de serializar el registro a XML, que es el precio real de
la vía completa y no se mide aquí.
"""
import pathlib
import tempfile

import lxml.etree as ET
import pytest
from lxml.builder import E

#: Una orden de dos líneas, como árbol — la forma que XPath sí puede recorrer.
ORDER = ET.XML(
    '<order name="SO-1">'
    '<line price="10.5" qty="2"/>'
    '<line price="3" qty="4"/>'
    '</order>'
)


class TestWhatXpathAlreadyDoes:
    """El recorrido y la agregación no necesitan motor de plantillas."""

    @pytest.mark.parametrize('expression, expected', [
        ('string(@name)',                    'SO-1'),
        ('count(line)',                      2.0),
        ('sum(line/@price)',                 13.5),
        ('concat(@name, "-", count(line))',  'SO-1-2'),
    ])
    def test_it_covers_lookup_aggregation_and_concatenation(self, expression, expected):
        assert ORDER.xpath(expression) == expected

    def test_but_it_cannot_multiply_two_node_sets_elementwise(self):
        # El límite real de XPath 1.0, y la razón por la que el importe de
        # línea no se puede calcular en una sola expresión: no hay `for`.
        with pytest.raises(ET.XPathEvalError, match='Invalid type'):
            ORDER.xpath('sum(line/@price * line/@qty)')


class TestWhyItCannotEvaluateOurLeafToday:
    """La razón por la que DTL cubre `_render_text` y lxml no."""

    def test_the_context_node_must_be_an_element(self):
        class Order:
            name = 'SO-1'

        # No existe XPath sobre objetos de Python: el registro del ORM no es
        # un nodo, así que no hay árbol que recorrer.
        with pytest.raises(TypeError, match='Invalid input object'):
            ET.XPath('@name')(Order())


class TestWhatOpensIfTheDataBecomesXmlFirst:
    """Con el dato serializado, XSLT cubre lo que XPath solo no alcanza."""

    SHEET = (
        '<xsl:stylesheet version="1.0"'
        ' xmlns:xsl="http://www.w3.org/1999/XSL/Transform">'
        '<xsl:output method="xml" indent="no"/>'
        '<xsl:template match="/order"><doc n="{@name}">'
        '<xsl:for-each select="line">'
        '<l><xsl:value-of select="format-number(@price * @qty, \'#,##0.00\')"/></l>'
        '</xsl:for-each>'
        '<total><xsl:value-of select="format-number(sum(line/@price), \'#,##0.00\')"/></total>'
        '</doc></xsl:template></xsl:stylesheet>'
    )

    def test_inside_for_each_the_multiplication_works(self):
        # Lo que el node-set no permite, el nodo individual sí: es el mismo
        # cálculo que el caso anterior rechaza, resuelto por iteración.
        result = str(ET.XSLT(ET.XML(self.SHEET))(ORDER))
        assert '<l>21.00</l><l>12.00</l>' in result

    def test_format_number_covers_the_money_formatting(self):
        result = str(ET.XSLT(ET.XML(self.SHEET))(ORDER))
        assert '<total>13.50</total>' in result

    def test_a_python_function_can_be_called_from_the_transformation(self):
        namespace = ET.FunctionNamespace('urn:kaupamex-probe')
        namespace.prefix = 'kx'

        @namespace
        def amount_with_currency(_context, value):
            return f'{float(value):.2f} MXN'

        assert ORDER.xpath('kx:amount_with_currency(sum(line/@price))') == '13.50 MXN'


class TestTheXsltAttackSurfaceIsRealAndClosable:
    """`document()` lee archivos: con la hoja en BD, eso es una primitiva."""

    @pytest.fixture
    def readable_xml_file(self):
        target = pathlib.Path(tempfile.mkdtemp()) / 'secret.xml'
        target.write_text('<s>CONTENIDO-SECRETO</s>', encoding='utf-8')
        return target

    def sheet_reading(self, target):
        return ET.XML(
            '<xsl:stylesheet version="1.0"'
            ' xmlns:xsl="http://www.w3.org/1999/XSL/Transform">'
            f'<xsl:template match="/"><read>'
            f'<xsl:value-of select="document(\'file://{target}\')"/>'
            '</read></xsl:template></xsl:stylesheet>'
        )

    def test_without_access_control_it_reads_the_file(self, readable_xml_file):
        # CONTROL POSITIVO: apunta a un archivo que EXISTE y es XML parseable.
        # Con un archivo inexistente -o con uno que no sea XML- el caso pasaría
        # por la razón equivocada y no mediría la guarda.
        result = str(ET.XSLT(self.sheet_reading(readable_xml_file))(ET.XML('<d/>')))
        assert 'CONTENIDO-SECRETO' in result

    def test_deny_all_closes_it(self, readable_xml_file):
        with pytest.raises(ET.XSLTApplyError, match='read rights .* denied'):
            ET.XSLT(
                self.sheet_reading(readable_xml_file),
                access_control=ET.XSLTAccessControl.DENY_ALL,
            )(ET.XML('<d/>'))


class TestTheProgrammaticTreeNeedsNoTemplateAtAll:
    """La cuarta vía: construir el árbol, sin plantilla de por medio."""

    def test_it_escapes_and_refuses_by_construction(self):
        node = E.items(E.i('10.50', n='Tornillo & tuerca'))
        assert 'n="Tornillo &amp; tuerca"' in ET.tostring(node, encoding='unicode')

        with pytest.raises(ValueError, match='All strings must be XML compatible'):
            E.i('valor\x0bcon control')

    def test_but_it_has_no_arch_so_no_addon_can_patch_it(self):
        # El precio de no tener plantilla: la herencia entre addons parchea el
        # `arch` con `<xpath position=…>`, y un árbol construido en código no
        # tiene `arch` que parchear — hay que subclasear o pasar por un hook.
        node = E.items(E.i('10.50'))
        assert node.xpath('//xpath') == []
