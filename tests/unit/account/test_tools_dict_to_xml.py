"""``dict_to_xml`` -- serializacion de un ``dict`` Python a nodo XML.

Cubre ``addons/account/tools/dict_to_xml.py``, portacion pura sin ORM (tarea
#398, hallazgo H-API-682). Ver el docstring del modulo bajo prueba para la
divergencia declarada sobre ``remove_control_characters``.
"""
import pytest
from lxml import etree

from addons.account.tools.dict_to_xml import dict_to_xml

pytestmark = [pytest.mark.unit]


class TestDictToXmlBasics:
    """El contrato base: tag, atributos, texto."""

    def test_renders_the_tag(self):
        element = dict_to_xml({'_tag': 'root'}, render_empty_nodes=True)
        assert element.tag == 'root'

    def test_renders_simple_values_as_attributes(self):
        element = dict_to_xml({'_tag': 'root', 'currency': 'MXN'})
        assert element.get('currency') == 'MXN'

    def test_underscore_keys_other_than_tag_and_text_are_not_rendered(self):
        element = dict_to_xml({'_tag': 'root', '_dummy': 'x', 'real': 'y'})
        assert element.get('_dummy') is None
        assert element.get('real') == 'y'

    def test_renders_text_content(self):
        element = dict_to_xml({'_tag': 'root', '_text': 'hola'})
        assert element.text == 'hola'

    def test_false_and_none_values_are_not_rendered_as_attributes(self):
        element = dict_to_xml({'_tag': 'root', 'a': None, 'b': False, 'c': 'ok'})
        assert element.get('a') is None
        assert element.get('b') is None
        assert element.get('c') == 'ok'


class TestDictToXmlNestedNodes:
    """Nodos hijo: dict simple y lista de dicts."""

    def test_child_dict_becomes_a_child_element(self):
        element = dict_to_xml({'_tag': 'root', 'child': {'_text': 'x'}})
        children = list(element)
        assert len(children) == 1
        assert children[0].tag == 'child'
        assert children[0].text == 'x'

    def test_list_of_dicts_becomes_multiple_children_with_same_tag(self):
        element = dict_to_xml({
            '_tag': 'root',
            'line': [{'_text': '1'}, {'_text': '2'}],
        })
        children = list(element)
        assert [c.tag for c in children] == ['line', 'line']
        assert [c.text for c in children] == ['1', '2']

    def test_none_entries_in_a_child_list_are_skipped(self):
        element = dict_to_xml({
            '_tag': 'root',
            'line': [{'_text': '1'}, None, {'_text': '2'}],
        })
        assert [c.text for c in element] == ['1', '2']


class TestDictToXmlEmptyNodes:
    """``render_empty_nodes`` controla si un nodo sin contenido sobrevive."""

    def test_empty_node_returns_none_by_default(self):
        assert dict_to_xml({'_tag': 'root'}) is None

    def test_empty_node_is_kept_when_render_empty_nodes_is_true(self):
        element = dict_to_xml({'_tag': 'root'}, render_empty_nodes=True)
        assert element is not None
        assert element.tag == 'root'

    def test_a_node_with_only_empty_children_is_itself_empty(self):
        # El hijo vacio no se agrega (default render_empty_nodes=False),
        # asi que el padre queda sin atributos/texto/hijos -> None.
        assert dict_to_xml({'_tag': 'root', 'child': {}}) is None


class TestDictToXmlTagRequirement:
    """Sin ``_tag`` en ningun nivel -- ``ValueError``, no un fallo silencioso."""

    def test_raises_without_any_tag(self):
        with pytest.raises(ValueError):
            dict_to_xml({'no_tag_here': 'x'})


class TestDictToXmlTemplate:
    """``template`` fuerza el orden de claves y valida los hijos declarados."""

    def test_child_not_declared_in_template_raises(self):
        with pytest.raises(ValueError):
            dict_to_xml(
                {'_tag': 'root', 'undeclared': {'_text': 'x'}},
                template={'_tag': 'root'},
            )

    def test_child_declared_in_template_is_accepted(self):
        element = dict_to_xml(
            {'_tag': 'root', 'declared': {'_text': 'x'}},
            template={'_tag': 'root', 'declared': None},
        )
        assert [c.tag for c in element] == ['declared']


class TestDictToXmlNamespaces:
    """``nsmap`` + tag con prefijo (``ns:tag``) -- conversion a QName lxml."""

    def test_namespaced_tag_resolves_to_a_qname(self):
        element = dict_to_xml(
            {'_tag': 'inv:Invoice'},
            nsmap={'inv': 'urn:example:invoice'},
            render_empty_nodes=True,
        )
        assert element.tag == '{urn:example:invoice}Invoice'


class TestRemoveControlCharacters:
    """El vendorizado local de ``remove_control_characters`` (ver
    divergencia declarada en el docstring del modulo bajo prueba): quita
    los caracteres de control ``#x0``-``#x1F``/``#x7F`` del texto, tal como
    exige XML 1.0.
    """

    def test_strips_a_control_character_from_the_text(self):
        element = dict_to_xml({'_tag': 'root', '_text': 'a\x01b'})
        assert element.text == 'ab'

    def test_keeps_tab_newline_and_carriage_return(self):
        element = dict_to_xml({'_tag': 'root', '_text': 'a\tb\nc\rd'})
        assert element.text == 'a\tb\nc\rd'

    def test_serialized_xml_has_no_raw_control_byte(self):
        element = dict_to_xml({'_tag': 'root', '_text': 'x\x02y'})
        serialized = etree.tostring(element)
        assert b'\x02' not in serialized
