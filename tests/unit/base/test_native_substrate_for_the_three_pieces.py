r"""Sonda: las tres piezas de QWeb, ¿se hacen de forma nativa con nuestro stack?

Pregunta del ejecutor 2026-08-29: *"esas tres piezas que QWeb aporta, ¿las
podemos hacer de forma nativa, de acuerdo a nuestro stack? que es python,
django, django restframework, lxml"*.

La pregunta tiene una ambigüedad que la sonda separa, porque las dos lecturas
dan respuestas distintas:

- **nativo = el stack lo trae hecho** — hay un símbolo instalado que ya hace
  eso, y basta llamarlo;
- **nativo = el stack tiene con qué construirlo** — no hay símbolo hecho, pero
  las primitivas están y no hace falta ninguna dependencia de fuera.

Cada caso declara en cuál de las dos cae, con la medición al lado.

*Métrica:* qué acepta y qué rechaza cada primitiva del stack, ejercida sobre el
mismo juego de expresiones y el mismo documento.
*Ciega a:* el coste por evaluación, que no se mide aquí; y a si el allowlist de
opcodes sobrevive a un cambio de versión de CPython — de eso sólo se mide el
mecanismo que lo amortigua, no su conducta bajo una versión futura.
"""
import ast
import dis
import operator
import sys
from opcode import opmap
from pathlib import Path

import pytest
from django.template import Context, Engine, TemplateSyntaxError, Variable
from django.template.base import VariableDoesNotExist
from lxml import etree

import tools.safe_eval as safe_eval_module
from tools.safe_eval import safe_eval


class Line:
    price = 10.5
    qty = 2


CONTEXT = {'a': 1, 'line': Line(), 'rows': [10, 20]}

#: El allowlist mínimo que hace falta para la aritmética de un importe. Se
#: escribe aquí, en seis nombres, para medir que la pieza 1 se construye con
#: primitivas de la biblioteca estándar y nada más.
MINIMAL_ALLOWLIST = {
    'RESUME', 'LOAD_CONST', 'LOAD_NAME', 'LOAD_ATTR', 'BINARY_OP',
    'BINARY_SUBSCR', 'RETURN_VALUE',
}


def compile_within(source, allowlist=MINIMAL_ALLOWLIST):
    """La pieza 1 en seis líneas: compilar y mirar el bytecode que salió."""
    code = compile(source, '<expr>', 'eval')
    outside = {i.opname for i in dis.get_instructions(code)} - allowlist
    if outside:
        raise ValueError('opcodes fuera del allowlist: %s' % sorted(outside))
    return code


class TestPieceOneTheStdlibBringsThePrimitivesNotTheMechanism:
    """Contención: el stack NO la trae hecha, pero la construye sin nada de fuera."""

    @pytest.mark.parametrize('source', [
        '1 + 1',            # ni siquiera una suma de constantes
        'line.price',       # ni un acceso a atributo
        'a + 1',
    ])
    def test_literal_eval_is_native_and_contained_and_cannot_do_the_job(self, source):
        # `ast.literal_eval` es lo más nativo que hay para «evaluar seguro»:
        # stdlib, cero configuración, imposible de escapar. Y no sirve para un
        # documento: sólo acepta literales.
        with pytest.raises(ValueError, match='malformed node or string'):
            ast.literal_eval(source)

    def test_but_it_does_parse_a_pure_literal(self):
        """Control positivo: el rechazo de arriba es por la gramática, no por
        que el parámetro esté mal formado."""
        assert ast.literal_eval("{'a': 1, 'b': [2, 3]}") == {'a': 1, 'b': [2, 3]}

    def test_compile_and_dis_are_enough_to_build_the_containment(self):
        # Las tres primitivas —`compile`, `dis`, `opcode`— son stdlib, y con
        # ellas el allowlist ya discrimina. Esto ES lo que safe_eval hace.
        assert compile_within('line.price * line.qty') is not None

    @pytest.mark.parametrize('source, forbidden', [
        ('lambda: 1', 'MAKE_FUNCTION'),
        ('[x for x in rows]', 'FOR_ITER'),
    ])
    def test_and_the_allowlist_rejects_what_is_not_in_it(self, source, forbidden):
        with pytest.raises(ValueError) as excinfo:
            compile_within(source)
        assert forbidden in str(excinfo.value)

    def test_the_ported_containment_imports_nothing_from_outside_the_stack(self):
        """La medición que responde la pregunta para la pieza 1.

        Si `safe_eval` necesitara una dependencia ajena, «nativo» sería falso.
        Se mide por AST sobre sus propios imports, no leyendo el docstring.
        """
        tree = ast.parse(Path(safe_eval_module.__file__).read_text())
        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split('.')[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                roots.add(node.module.split('.')[0])

        stdlib = set(sys.stdlib_module_names)
        our_stack = {'django', 'rest_framework'}
        ours = {'exceptions', '_monkeypatches'}
        outside = roots - stdlib - our_stack - ours
        # Exacto, no `<=`: así una raíz nueva rompe el caso en vez de colarse.
        # `dateutil` NO es de la contención — se importa en la línea 554, muy
        # por debajo de `assert_valid_codeobj` (:272) y `safe_eval` (:430), y
        # sólo para exponerlo como módulo evaluable, que es otra función del
        # archivo. `pytz` no aparece aquí: llega por `_monkeypatches`.
        assert outside == {'dateutil'}, sorted(outside)

    def test_and_that_third_party_import_sits_below_the_containment(self):
        """Control del comentario de arriba: la posición se mide, no se afirma."""
        lines = Path(safe_eval_module.__file__).read_text().splitlines()
        def line_of(prefix):
            return next(i for i, text in enumerate(lines, 1)
                        if text.startswith(prefix))
        assert line_of('def assert_valid_codeobj') < line_of('import dateutil')
        assert line_of('def safe_eval') < line_of('import dateutil')

    def test_the_allowlist_survives_a_renamed_opcode_by_failing_closed(self):
        """El coste de construirlo sobre bytecode, y cómo se amortigua.

        `to_opcodes` descarta el nombre que este intérprete no conoce
        (``safe_eval.py:114-117``). En un allowlist eso es fail-closed: el
        opcode desaparecido deja de estar permitido, no deja de estar
        prohibido. `safe_eval.py` no lleva ninguna guarda por versión de
        CPython — se apoya en esa propiedad.
        """
        assert list(safe_eval_module.to_opcodes(['ESTE_OPCODE_NO_EXISTE'])) == []
        assert list(safe_eval_module.to_opcodes(['RETURN_VALUE'])) == [opmap['RETURN_VALUE']]
        source = Path(safe_eval_module.__file__).read_text()
        assert 'version_info' not in source


class TestPieceTwoDjangoBringsItDone:
    """Resolución de nombres: el stack SÍ la trae hecha, y dos veces."""

    def test_attrgetter_resolves_a_dotted_path_and_contains_nothing(self):
        # stdlib, una línea — y llega a `__class__` sin oponer nada. Resuelve
        # nombres; no es contención. Los dos ejes son independientes.
        assert operator.attrgetter('price')(Line()) == 10.5
        assert operator.attrgetter('price.__class__')(Line()) is float

    def test_django_variable_resolves_and_does_contain(self):
        assert Variable('line.price').resolve(Context(CONTEXT)) == 10.5
        with pytest.raises(TemplateSyntaxError, match='may not begin with underscores'):
            Variable('line.__class__')

    def test_lxml_xpath_resolves_over_a_tree_without_running_python(self):
        doc = etree.fromstring('<doc><line price="10.5" qty="2"/></doc>')
        assert doc.xpath('string(/doc/line/@price)') == '10.5'
        # Y no alcanza un objeto de Python: el sustrato es el árbol, no el ORM.
        with pytest.raises(TypeError, match='Invalid input object'):
            etree.XPath('/doc')(Line())


class TestPieceThreeBothDjangoAndLxmlCompileTemplatesNatively:
    """Compilar la plantilla: el stack lo trae hecho — pero no a Python."""

    def test_django_compiles_to_a_node_tree_not_to_python_source(self):
        # La diferencia con QWeb, que es la que el ejecutor no quiere: DTL
        # compila a un árbol de nodos que se recorre, no a código Python que se
        # ejecuta. No hay un `compile()` de por medio.
        template = Engine(autoescape=False).from_string(
            '{% for r in rows %}{{ r }}{% endfor %}')
        assert [type(node).__name__ for node in template.nodelist] == ['ForNode']
        assert not hasattr(template, 'co_code')

    def test_lxml_compiles_a_stylesheet_into_a_transformer(self):
        sheet = etree.XSLT(
            etree.fromstring(
                '<xsl:stylesheet version="1.0"'
                ' xmlns:xsl="http://www.w3.org/1999/XSL/Transform">'
                '<xsl:template match="/doc"><out><xsl:for-each select="line">'
                '<amount><xsl:value-of'
                ' select="format-number(@price * @qty, \'#0.00\')"/></amount>'
                '</xsl:for-each></out></xsl:template></xsl:stylesheet>'),
            access_control=etree.XSLTAccessControl.DENY_ALL)
        output = sheet(etree.fromstring(
            '<doc><line price="10.5" qty="2"/><line price="3" qty="4"/></doc>'))
        assert etree.tostring(output.getroot()) == (
            b'<out><amount>21.00</amount><amount>12.00</amount></out>')

    def test_the_stylesheet_does_the_per_node_arithmetic_xpath_alone_cannot(self):
        """El control que separa las dos piezas de lxml.

        XPath 1.0 suelto no multiplica atributo por atributo a lo largo de una
        lista: `sum()` sólo suma un nodo-set. Por eso el importe por línea sale
        del `xsl:for-each` de arriba y no de una sola expresión XPath.
        """
        doc = etree.fromstring('<doc><line price="10.5" qty="2"/></doc>')
        # Sobre UN nodo sí opera; lo que no hay es el producto a lo largo del set.
        assert doc.xpath('number(/doc/line/@price) * number(/doc/line/@qty)') == 21.0
        with pytest.raises(etree.XPathEvalError):
            doc.xpath('sum(/doc/line/@price * /doc/line/@qty)')


class TestWhatTheStackDoesNotBring:
    """El hueco real, para no publicar un sí sin su resto."""

    def test_literal_eval_refuses_it_by_grammar(self):
        with pytest.raises(ValueError, match='malformed node or string'):
            ast.literal_eval('line.price * line.qty')

    def test_attrgetter_reads_it_as_one_attribute_name(self):
        # No evalúa: busca un atributo llamado literalmente `price * qty`.
        with pytest.raises(AttributeError, match=r"no attribute 'price \* qty'"):
            operator.attrgetter('price * qty')(Line())

    def test_django_variable_reads_it_as_a_lookup_that_does_not_exist(self):
        with pytest.raises(VariableDoesNotExist, match=r'price \* line'):
            Variable('line.price * line.qty').resolve(Context(CONTEXT))

    def test_lxml_cannot_even_see_the_orm_object(self):
        with pytest.raises(TypeError, match='Invalid input object'):
            etree.XPath('/doc')(Line())

    def test_and_the_composition_of_stdlib_primitives_does(self):
        """Lo que cierra el hueco, y es la razón de que safe_eval exista."""
        assert safe_eval('line.price * line.qty', CONTEXT) == 21.0
