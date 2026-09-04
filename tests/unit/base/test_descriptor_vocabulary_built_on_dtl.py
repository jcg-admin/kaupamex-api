r"""TDD: lo que hay que CONSTRUIR en el intérprete del descriptor, sin QWeb.

Directiva del ejecutor 2026-08-29: *"en un análisis mencionaste algo importante,
una distinción entre lo que trae nuestro stack y lo que nuestro stack nos aporta
para poder construir, ya que estamos quitando QWeb; genera los test para
construirlo"*.

La distinción es la que abre
``test_native_substrate_for_the_three_pieces.py``:

- **el stack lo trae hecho** — hay un símbolo instalado y basta llamarlo;
- **el stack tiene con qué construirlo** — no hay símbolo hecho, pero las
  primitivas están y no hace falta ninguna dependencia de fuera.

Las cuatro construcciones de este archivo caen en la **segunda**. DTL trae
hechos ``{% if %}``, ``{% with %}``, ``forloop`` e ``{% include %}`` —medido en
``test_directive_substrate_without_qweb.py``—, pero los trae para un motor de
**texto**. El descriptor no es texto: es un **árbol XML que se interpreta a un
dict**. El intérprete que recorre ese árbol y decide qué nodo entra al
documento lo construimos nosotros, con DTL como evaluador y nada más.

Lo que hoy existe (``report_template.py``) es el vocabulario mínimo:
``<descriptor>``, ``<section>``, ``<field>``, ``<list>``. Le faltan las cuatro
capacidades que ``t-if``, ``t-set``, ``t-foreach`` (con índice) y ``t-call``
daban, y que ningún consumidor puede pedirle todavía porque no existen.

**Este archivo se escribe antes que la implementación** y se observa en rojo.

*Métrica:* la conducta de ``interpret_descriptor`` sobre archs que ejercen cada
capacidad nueva.
*Ciega a:* el rendimiento del recorrido, y a si el helper de PDF acepta el
descriptor resultante — eso lo mide su propio contrato.
"""
import pytest
from lxml import etree

from addons.base.report_template import InvalidReportTemplate, interpret_descriptor


def arch(xml):
    return etree.fromstring(xml)


class Line:
    def __init__(self, name, qty):
        self.name = name
        self.qty = qty


CONTEXT = {
    'doc': {'ref': 'SO-001', 'total': 42},
    'lines': [Line('a', 1), Line('b', 2), Line('c', 3)],
    'vacio': [],
}


class TestTheConditional:
    """``t-if`` — el nodo entra al documento o no entra.

    El stack trae la evaluación (``{% if %}`` de DTL); lo que no trae es que un
    **nodo del árbol** se omita del dict resultante. Eso es el intérprete.
    """

    def test_a_true_condition_keeps_the_field(self):
        d = interpret_descriptor(arch(
            '<descriptor><field name="ref" when="doc.total">{{ doc.ref }}</field>'
            '</descriptor>'), CONTEXT)
        assert d == {'ref': 'SO-001'}

    def test_a_false_condition_drops_the_key_entirely(self):
        # No es una clave con valor vacío: la clave NO está. Un descriptor con
        # `"ref": ""` y uno sin `ref` son documentos distintos para el helper.
        d = interpret_descriptor(arch(
            '<descriptor><field name="ref" when="vacio">{{ doc.ref }}</field>'
            '</descriptor>'), CONTEXT)
        assert d == {}

    def test_the_condition_also_guards_a_section(self):
        d = interpret_descriptor(arch(
            '<descriptor><section name="tot" when="vacio">'
            '<field name="v">x</field></section></descriptor>'), CONTEXT)
        assert d == {}

    def test_an_unresolvable_condition_fails_closed_and_says_which(self):
        # Fail-closed: una condición que no resuelve NO se lee como falsa. Un
        # dato ausente por un typo saldría del papel sin que nadie lo note.
        with pytest.raises(InvalidReportTemplate, match='no.existe'):
            interpret_descriptor(arch(
                '<descriptor><field name="v" when="no.existe">x</field></descriptor>'),
                CONTEXT)


class TestTheLocalVariable:
    """``t-set`` — un valor calculado una vez y visible para los hermanos."""

    def test_it_binds_a_name_for_the_following_siblings(self):
        d = interpret_descriptor(arch(
            '<descriptor><set name="n" value="doc.total"/>'
            '<field name="v">{{ n }}</field></descriptor>'), CONTEXT)
        assert d == {'v': '42'}

    def test_the_set_itself_does_not_appear_in_the_document(self):
        d = interpret_descriptor(arch(
            '<descriptor><set name="n" value="doc.total"/></descriptor>'), CONTEXT)
        assert d == {}

    def test_it_does_not_leak_out_of_its_section(self):
        # El ámbito es el nodo que lo contiene. Sin esto, dos secciones que
        # usen el mismo nombre se pisan según el orden del árbol.
        with pytest.raises(InvalidReportTemplate):
            interpret_descriptor(arch(
                '<descriptor><section name="a">'
                '<set name="n" value="doc.total"/><field name="v">{{ n }}</field>'
                '</section>'
                '<field name="fuera" when="n">x</field></descriptor>'), CONTEXT)

    def test_a_set_without_value_is_refused(self):
        with pytest.raises(InvalidReportTemplate, match="'value'"):
            interpret_descriptor(arch(
                '<descriptor><set name="n"/></descriptor>'), CONTEXT)


class TestTheLoopExposesItsPosition:
    """``t-foreach`` con ``_index``/``_first``/``_last``/paridad.

    ``forloop`` de DTL los trae —salvo la paridad, que sale de
    ``divisibleby``—, pero ``forloop`` sólo existe dentro de un ``{% for %}``
    de una plantilla de texto. En el árbol lo expone el intérprete.
    """

    def test_the_item_is_exposed_as_before(self):
        d = interpret_descriptor(arch(
            '<descriptor><list name="l" in="lines">'
            '<field name="n">{{ item.name }}</field></list></descriptor>'), CONTEXT)
        assert d == {'l': [{'n': 'a'}, {'n': 'b'}, {'n': 'c'}]}

    @pytest.mark.parametrize('expr,expected', [
        ('{{ loop.index }}', ['0', '1', '2']),
        ('{{ loop.number }}', ['1', '2', '3']),
        ('{{ loop.first }}', ['True', 'False', 'False']),
        ('{{ loop.last }}', ['False', 'False', 'True']),
        ('{{ loop.even }}', ['True', 'False', 'True']),
        ('{{ loop.odd }}', ['False', 'True', 'False']),
        ('{{ loop.size }}', ['3', '3', '3']),
    ])
    def test_the_loop_exposes_position_and_parity(self, expr, expected):
        d = interpret_descriptor(arch(
            '<descriptor><list name="l" in="lines">'
            '<field name="v">%s</field></list></descriptor>' % expr), CONTEXT)
        assert [row['v'] for row in d['l']] == expected

    def test_an_empty_iterable_gives_an_empty_list_not_a_missing_key(self):
        d = interpret_descriptor(arch(
            '<descriptor><list name="l" in="vacio">'
            '<field name="v">x</field></list></descriptor>'), CONTEXT)
        assert d == {'l': []}

    def test_the_loop_variable_does_not_survive_the_list(self):
        with pytest.raises(InvalidReportTemplate):
            interpret_descriptor(arch(
                '<descriptor><list name="l" in="lines">'
                '<field name="v">x</field></list>'
                '<field name="fuera" when="loop">y</field></descriptor>'), CONTEXT)


class TestComposingTwoDescriptors:
    """``t-call`` — incluir otro descriptor por su ``key``.

    ``{% include %}`` de DTL exige un loader; aquí el loader es la propia
    ``ir.ui.view`` resuelta por ``key``, que ya existe. El intérprete recibe
    quién resuelve, para no depender de la base en una prueba unitaria.
    """

    def test_it_splices_the_children_of_the_called_descriptor(self):
        blocks = {'bloque.pie': arch(
            '<descriptor><field name="pie">{{ doc.ref }}</field></descriptor>')}
        d = interpret_descriptor(arch(
            '<descriptor><field name="cab">x</field>'
            '<call key="bloque.pie"/></descriptor>'),
            CONTEXT, resolve_key=blocks.get)
        assert d == {'cab': 'x', 'pie': 'SO-001'}

    def test_an_unknown_key_fails_closed(self):
        with pytest.raises(InvalidReportTemplate, match='bloque.ausente'):
            interpret_descriptor(arch(
                '<descriptor><call key="bloque.ausente"/></descriptor>'),
                CONTEXT, resolve_key=lambda k: None)

    def test_a_call_without_a_resolver_is_refused_not_ignored(self):
        # Sin resolutor el `call` no se puede cumplir. Ignorarlo produciría un
        # documento al que le falta un bloque entero, en silencio.
        with pytest.raises(InvalidReportTemplate, match='resolve_key'):
            interpret_descriptor(arch(
                '<descriptor><call key="b"/></descriptor>'), CONTEXT)


class TestTheVocabularyStaysClosed:
    """Lo que no está en el vocabulario sigue sin estar."""

    def test_an_unknown_element_is_still_refused(self):
        with pytest.raises(InvalidReportTemplate, match='inventado'):
            interpret_descriptor(arch(
                '<descriptor><inventado name="x"/></descriptor>'), CONTEXT)

    def test_the_root_must_still_be_descriptor(self):
        with pytest.raises(InvalidReportTemplate):
            interpret_descriptor(arch('<otro/>'), CONTEXT)


class TestTheCallDepthIsCapped:
    """Dos descriptores que se llaman mutuamente no cuelgan al proceso.

    La fuente lo resuelve con un **tope de profundidad** de la pila de render,
    no con un conjunto de claves ya visitadas
    (``odoo19c: ir_qweb.py:766-768`` — ``if len(stack) > 50: raise
    RecursionError('Qweb template infinite recursion')``). La diferencia
    importa: un conjunto de visitados rechazaría llamar **dos veces** al mismo
    bloque en puntos distintos del documento, que es legítimo; el tope sólo
    rechaza el anidamiento que no termina.
    """

    def test_a_cycle_between_two_descriptors_raises_instead_of_hanging(self):
        blocks = {
            'a': arch('<descriptor><call key="b"/></descriptor>'),
            'b': arch('<descriptor><call key="a"/></descriptor>'),
        }
        with pytest.raises(RecursionError, match='infinite recursion'):
            interpret_descriptor(arch(
                '<descriptor><call key="a"/></descriptor>'),
                CONTEXT, resolve_key=blocks.get)

    def test_a_descriptor_that_calls_itself_raises_too(self):
        blocks = {}
        blocks['solo'] = arch('<descriptor><call key="solo"/></descriptor>')
        with pytest.raises(RecursionError, match='infinite recursion'):
            interpret_descriptor(arch(
                '<descriptor><call key="solo"/></descriptor>'),
                CONTEXT, resolve_key=blocks.get)

    def test_the_same_block_called_twice_is_not_a_cycle(self):
        # El control que discrimina: si el tope fuera un conjunto de claves
        # visitadas, este caso —legítimo— fallaría igual que los dos de
        # arriba, y el verde de aquéllos no distinguiría un mecanismo del
        # otro. Es el sub-patrón D de ``metrica-decide-la-conclusion.md``.
        blocks = {'pie': arch(
            '<descriptor><field name="v">{{ doc.ref }}</field></descriptor>')}
        d = interpret_descriptor(arch(
            '<descriptor><section name="uno"><call key="pie"/></section>'
            '<section name="dos"><call key="pie"/></section></descriptor>'),
            CONTEXT, resolve_key=blocks.get)
        assert d == {'uno': {'v': 'SO-001'}, 'dos': {'v': 'SO-001'}}

    def test_a_chain_below_the_cap_still_renders(self):
        # Cuarenta llamadas encadenadas: por debajo del tope de la fuente, así
        # que el documento sale. Sin este caso, un tope de 1 pasaría los tres
        # anteriores y nadie lo notaría.
        blocks = {f'n{i}': arch(f'<descriptor><call key="n{i + 1}"/></descriptor>')
                  for i in range(40)}
        blocks['n40'] = arch(
            '<descriptor><field name="fin">{{ doc.ref }}</field></descriptor>')
        d = interpret_descriptor(arch(
            '<descriptor><call key="n0"/></descriptor>'),
            CONTEXT, resolve_key=blocks.get)
        assert d == {'fin': 'SO-001'}
