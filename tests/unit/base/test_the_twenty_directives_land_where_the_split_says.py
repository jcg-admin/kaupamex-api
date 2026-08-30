r"""Las 20 directivas ``t-*``, aplicadas: dónde aterriza cada una en ESTE árbol.

Directiva del ejecutor 2026-08-30: cerrar las piezas que quedan del desmontaje
de QWeb con el mismo criterio de las dos categorías. Pieza 2 de 8.

Hay ya dos archivos sobre estas 20 y **ninguno mide lo que este mide**:

- ``test_directive_substrate_without_qweb.py`` ejerce el **sustrato**: que
  DTL, ``lxml`` y el ORM traen el mecanismo que la tabla del análisis les
  atribuye. Responde *"¿existe con qué?"*.
- Éste ejerce el **destino**: en qué símbolo de este árbol aterrizó cada
  directiva, ahora que el intérprete del descriptor está escrito. Responde
  *"¿dónde quedó?"* — y para cuatro de las veinte la respuesta es una
  divergencia declarada, no un símbolo.

La lista **no se teclea**: sale de ``_directives_eval_order()``, así que una
directiva nueva en la fuente aparece aquí sin destino en vez de pasar
inadvertida.

*Métrica:* la conducta de ``interpret_descriptor`` sobre archs que ejercen
cada destino, y el rechazo del vocabulario cerrado para las que no aterrizan.
*Ciega a:* si el helper de libharu acepta el descriptor resultante —eso lo
mide su propio contrato— y a si el destino cubre todos los casos de borde de
su directiva. Mide dónde aterriza y que ahí hace lo que la tabla dice.
"""
from decimal import Decimal

import pytest
from lxml import etree

from addons.base import report_template
from addons.base.models.res_currency import ResCurrency
from addons.base.models.ir_template_expressions import IrTemplateExpressions
from addons.base.report_template import InvalidReportTemplate, interpret_descriptor

#: Los cuatro desenlaces posibles de una directiva en este árbol.
#:
#: ``descriptor``   el intérprete la implementa; hay arch que la ejerce.
#: ``converters``   la resuelve la familia de conversores (pieza 4).
#: ``orm-policy``   la resuelve una política fuera de la plantilla.
#: ``divergencia``  no aterriza, y la razón está escrita.
LANDING = {
    'if': 'descriptor',
    'elif': 'divergencia',
    'else': 'divergencia',
    'foreach': 'descriptor',
    'as': 'descriptor',
    'set': 'descriptor',
    'call': 'descriptor',
    'call-assets': 'divergencia',
    'esc': 'divergencia',
    'raw': 'divergencia',
    'out': 'divergencia',
    'field': 'converters',
    'att': 'divergencia',
    'tag-open': 'divergencia',
    'tag-close': 'divergencia',
    'inner-content': 'divergencia',
    'lang': 'orm-policy',
    'groups': 'orm-policy',
    'options': 'orm-policy',
    'debug': 'divergencia',
}


def arch(xml):
    return etree.fromstring(xml)


class TestTheListComesFromTheSourceNotFromHere:
    """El control que impide que este archivo envejezca en silencio."""

    def test_every_directive_of_the_source_has_a_landing(self):
        declared = IrTemplateExpressions._directives_eval_order(IrTemplateExpressions)
        assert set(declared) == set(LANDING), {
            'sin destino': sorted(set(declared) - set(LANDING)),
            'destino sin directiva': sorted(set(LANDING) - set(declared)),
        }

    def test_the_landing_is_one_of_the_four(self):
        assert set(LANDING.values()) == {
            'descriptor', 'converters', 'orm-policy', 'divergencia'}

    def test_the_split_is_the_one_the_decision_publishes(self):
        counts = {v: sum(1 for x in LANDING.values() if x == v)
                  for v in set(LANDING.values())}
        assert counts == {'descriptor': 5, 'converters': 1,
                          'orm-policy': 3, 'divergencia': 11}, counts


class TestTheFiveThatLandInTheInterpreter:
    """Las cinco que el intérprete del descriptor implementa, una por una."""

    def test_if_lands_as_the_when_attribute(self):
        doc = arch('<descriptor><section name="s" when="flag">'
                   '<field name="f">x</field></section></descriptor>')
        assert interpret_descriptor(doc, {'flag': True}) == {'s': {'f': 'x'}}
        assert interpret_descriptor(doc, {'flag': False}) == {}

    def test_foreach_and_as_land_as_the_list_element(self):
        # ``as`` no es un destino aparte: el nombre de la variable de bucle lo
        # fija el intérprete (``item``), no la plantilla. Es la divergencia
        # mínima que hace innecesaria la directiva.
        doc = arch('<descriptor><list name="rows" in="items">'
                   '<field name="n">{{ item }}</field></list></descriptor>')
        assert interpret_descriptor(doc, {'items': ['a', 'b']}) == {
            'rows': [{'n': 'a'}, {'n': 'b'}]}

    def test_set_lands_as_the_set_element(self):
        doc = arch('<descriptor><set name="tot" value="importe"/>'
                   '<field name="f">{{ tot }}</field></descriptor>')
        assert interpret_descriptor(doc, {'importe': 7}) == {'f': '7'}

    def test_call_lands_as_the_call_element(self):
        pieces = {'pie': arch('<descriptor><field name="p">ok</field></descriptor>')}
        doc = arch('<descriptor><call key="pie"/></descriptor>')
        assert interpret_descriptor(doc, {}, pieces.get) == {'p': 'ok'}


class TestTheTwoCaveatsTheMeasurementAdded:
    """DEC-FW-05 midió dos huecos del sustrato. Los dos están aplicados."""

    @pytest.mark.parametrize('expr, expected', [
        ('{{ loop.even }}', ['True', 'False', 'True']),
        ('{{ loop.odd }}', ['False', 'True', 'False']),
    ])
    def test_the_parity_that_forloop_does_not_expose_is_built_here(self, expr, expected):
        # Caveat 1: ``forloop`` de DTL da ``counter``/``first``/``last`` y la
        # paridad se construye con ``divisibleby``. El intérprete recorre el
        # árbol él mismo, así que su estado de bucle la trae hecha.
        doc = arch(f'<descriptor><list name="r" in="items">'
                   f'<field name="p">{expr}</field></list></descriptor>')
        salida = interpret_descriptor(doc, {'items': [1, 2, 3]})
        assert [fila['p'] for fila in salida['r']] == expected

    def test_the_loader_that_include_demands_is_an_explicit_argument(self):
        # Caveat 2: ``{% include %}`` exige un loader declarado. Aquí el
        # equivalente es ``resolve_key``, y su ausencia **levanta** en vez de
        # dejar el nodo fuera en silencio — fail-closed, como el ``when``.
        doc = arch('<descriptor><call key="pie"/></descriptor>')
        with pytest.raises(InvalidReportTemplate, match='resolve_key'):
            interpret_descriptor(doc, {})


class TestTheElevenThatDoNotLand:
    """Una divergencia declarada se prueba por el rechazo, no por la ausencia."""

    @pytest.mark.parametrize('tag', ['att', 'tag-open', 'tag-close', 'inner-content'])
    def test_the_four_that_build_markup_nodes_are_refused_by_name(self, tag):
        # Construyen un nodo de marcado pieza a pieza. El intermedio de este
        # árbol es un dict, no marcado: no hay nodo que abrir ni atributo que
        # colgar. El vocabulario cerrado lo dice nombrando el elemento.
        doc = arch(f'<descriptor><{tag} name="k">v</{tag}></descriptor>')
        with pytest.raises(InvalidReportTemplate, match=tag):
            interpret_descriptor(doc, {})

    def test_the_three_output_directives_have_nothing_to_escape(self):
        # ``esc``/``raw``/``out`` distinguen salida escapada de cruda. Aquí el
        # texto va a un dict de Python y el quoting lo hace ``json.dumps`` al
        # serializar, así que el valor llega al descriptor **verbatim**: los
        # tres colapsarían en el mismo comportamiento.
        doc = arch('<descriptor><field name="n">{{ nombre }}</field></descriptor>')
        assert interpret_descriptor(doc, {'nombre': 'Muebles & Cía <SA>'}) == {
            'n': 'Muebles & Cía <SA>'}

    def test_elif_and_else_have_no_chain_to_hang_from(self):
        # Cada nodo lleva su propio ``when``, evaluado contra el mismo ámbito.
        # No hay estado entre hermanos que un ``else`` pudiera leer, así que la
        # alternativa se escribe como la condición negada.
        doc = arch('<descriptor>'
                   '<field name="si" when="flag">A</field>'
                   '<field name="no" when="vacio">B</field>'
                   '</descriptor>')
        assert interpret_descriptor(doc, {'flag': True, 'vacio': False}) == {'si': 'A'}
        assert interpret_descriptor(doc, {'flag': False, 'vacio': True}) == {'no': 'B'}


class TestWhereTheFieldValueLandsOnThePaperPath:
    """``field`` aterriza en la pieza 4 — y formatea sólo si declara ``widget``."""

    def test_a_field_without_widget_delivers_the_canonical_value(self):
        # Es el corte que la pieza 4 ratificó: el API entrega decimal crudo e
        # ISO 8601, y ``ui: src/lib/intl.js`` presenta. Un ``<field>`` sin
        # ``widget`` hace lo mismo — el valor sale por el ``str()`` de DTL.
        doc = arch('<descriptor><field name="m">{{ importe }}</field></descriptor>')
        assert interpret_descriptor(doc, {'importe': Decimal('1234.50')}) == {
            'm': '1234.50'}

    def test_and_with_a_widget_it_arrives_formatted_by_its_converter(self):
        # El control que sustituye al anterior. Aquél afirmaba que en el camino
        # del papel nadie formatea, y lo medía por los nombres exportados de dos
        # módulos: cuando la tarea #197 cableó el conversor, siguió verde y su
        # afirmación ya era falsa (:ref:`h-api-941`). Éste mide conducta — el
        # mismo valor sale distinto según el ``widget``, así que cae si el
        # cableado se rompe y cae si se ensancha al campo sin ``widget``.
        currency = ResCurrency(name='MXN', symbol='$', position='before',
                               rounding=Decimal('0.01'), decimal_places=2)
        doc = arch('<descriptor><field name="m" value="importe" '
                   'widget="monetary"/></descriptor>')
        d = interpret_descriptor(
            doc, {'importe': Decimal('1234.50')},
            widget_options={'monetary': {'display_currency': currency}})
        assert d['m'].replace('\N{NO-BREAK SPACE}', ' ') == '$ 1,234.50'
