"""Contrato puro de ``tools.xml_utils`` (``odoo19c: odoo/tools/xml_utils.py``)."""

from io import BytesIO

import pytest
from lxml import etree

from exceptions import UserError
from tools import xml_utils

XSD = b"""<?xml version="1.0"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="Invoice">
    <xs:complexType><xs:sequence>
      <xs:element name="ID" type="xs:string"/>
    </xs:sequence></xs:complexType>
  </xs:element>
</xs:schema>"""


def test_remove_control_characters_keeps_tab_newline_and_text():
    assert xml_utils.remove_control_characters(b'a\x00b\x07\tc\nd\x1f') == b'ab\tc\nd'


def test_create_xml_node_chain_nests_and_sets_the_last_text():
    root = etree.Element('root')
    nodes = xml_utils.create_xml_node_chain(root, ['a', 'b', 'c'], 'v')
    assert [n.tag for n in nodes] == ['a', 'b', 'c']
    assert root.find('a/b/c').text == 'v'
    assert xml_utils.create_xml_node(root, 'd', 'x').getparent() is root


def test_cleanup_xml_node_drops_blank_leaves_and_indents():
    node = xml_utils.cleanup_xml_node(
        '<r><a>  </a><b>1</b><c><d/></c></r>')
    assert etree.tostring(node) == b'<r>\n  <b>1</b>\n</r>\n'


def test_cleanup_xml_node_keeps_indentation_when_asked():
    node = xml_utils.cleanup_xml_node(
        b'<r><a/><b>1</b></r>', remove_blank_nodes=False, indent_level=-1)
    assert etree.tostring(node) == b'<r><a/><b>1</b></r>'


def test_cleanup_xml_node_parses_bytes_with_control_characters():
    node = xml_utils.cleanup_xml_node(b'<r><b>1\x01</b></r>')
    assert node.find('b').text == '1'


def test_find_xml_value_returns_the_first_text_or_none():
    tree = etree.fromstring(b'<r><a>1</a><a>2</a></r>')
    assert xml_utils.find_xml_value('//a', tree) == '1'
    assert xml_utils.find_xml_value('//z', tree) is None


def test_check_with_xsd_accepts_a_valid_document():
    xml_utils._check_with_xsd(b'<Invoice><ID>F-1</ID></Invoice>', BytesIO(XSD))


def test_check_with_xsd_raises_user_error_with_the_schema_log():
    with pytest.raises(UserError) as error:
        xml_utils._check_with_xsd(b'<Invoice><Nope/></Invoice>', BytesIO(XSD))
    assert 'Nope' in str(error.value)


def test_remove_control_characters_works_on_bytes_not_code_points():
    """La clase de la fuente se compila sobre ``bytes`` (``.encode()``), así
    que filtra bytes UTF-8 y no puntos de código: un carácter fuera del BMP
    sobrevive entero y un control ASCII cae. ``U+FFFE`` tampoco cae, igual
    que en la fuente; la copia no corrige su conducta."""
    data = 'a\x01\U00010000\ufffec'.encode()
    assert xml_utils.remove_control_characters(data) == 'a\U00010000\ufffec'.encode()
