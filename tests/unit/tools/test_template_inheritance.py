"""Motor de herencia XPath — contrato del puerto de ``template_inheritance``.

Los casos ejercen la semántica que el porte debe preservar de la referencia
(``odoo19c: odoo/tools/template_inheritance.py``, ``odoo-tools@622ddc2aa5``):
las cinco posiciones, la composición de atributos y — el caso que hizo ganar a
19 sobre 18 — mover un hijo existente dentro del contenido nuevo de un
``replace mode="inner"``.

Son funciones puras sobre lxml: no tocan la BD ni el ORM.
"""
import pytest
from lxml import etree

from exceptions import ValidationError
from tools.template_inheritance import apply_inheritance_specs, locate_node


def arch(xml: str) -> etree._Element:
    return etree.fromstring(xml)


def spec(xml: str) -> etree._Element:
    return etree.fromstring(xml)


def dump(node: etree._Element) -> str:
    return etree.tostring(node, encoding='unicode')


class TestLocateNode:
    def test_xpath_encuentra_el_nodo(self):
        source = arch('<doc><a/><b name="x"/></doc>')
        node = locate_node(source, spec('<xpath expr="//b" position="after"/>'))
        assert node is not None and node.tag == 'b'

    def test_xpath_sin_expr_levanta(self):
        source = arch('<doc/>')
        with pytest.raises(ValidationError):
            locate_node(source, spec('<xpath position="after"/>'))

    def test_xpath_invalido_levanta(self):
        source = arch('<doc/>')
        with pytest.raises(ValidationError):
            locate_node(source, spec('<xpath expr="//[malo" position="after"/>'))

    def test_field_compara_solo_el_nombre(self):
        source = arch('<doc><field name="total" widget="monetary"/></doc>')
        node = locate_node(source, spec('<field name="total" position="after"/>'))
        assert node is not None and node.get('widget') == 'monetary'


class TestPositions:
    def test_inside_agrega_al_final(self):
        source = arch('<doc><seccion><a/></seccion></doc>')
        result = apply_inheritance_specs(
            source, spec('<xpath expr="//seccion" position="inside"><b/></xpath>'))
        assert [c.tag for c in result.find('seccion')] == ['a', 'b']

    def test_after_inserta_como_hermano(self):
        source = arch('<doc><a/><c/></doc>')
        result = apply_inheritance_specs(
            source, spec('<xpath expr="//a" position="after"><b/></xpath>'))
        assert [c.tag for c in result] == ['a', 'b', 'c']

    def test_before_inserta_como_hermano(self):
        source = arch('<doc><a/><c/></doc>')
        result = apply_inheritance_specs(
            source, spec('<xpath expr="//c" position="before"><b/></xpath>'))
        assert [c.tag for c in result] == ['a', 'b', 'c']

    def test_replace_outer_sustituye_el_nodo(self):
        source = arch('<doc><viejo texto="1"/></doc>')
        result = apply_inheritance_specs(
            source, spec('<xpath expr="//viejo" position="replace"><nuevo/></xpath>'))
        assert [c.tag for c in result] == ['nuevo']

    def test_replace_outer_con_dolar_cero_conserva_el_original(self):
        # ``$0`` dentro del contenido nuevo = "el nodo reemplazado": permite
        # envolver el original en vez de descartarlo.
        source = arch('<doc><viejo/></doc>')
        result = apply_inheritance_specs(
            source,
            spec('<xpath expr="//viejo" position="replace"><caja>$0</caja></xpath>'))
        caja = result.find('caja')
        assert caja is not None and [c.tag for c in caja] == ['viejo']

    def test_replace_inner_puede_mover_un_hijo_existente(self):
        # La capacidad que hizo ganar a 19 sobre 18: el sentinel conserva los
        # hijos mientras entra el contenido nuevo, así que un hijo previo
        # puede moverse DENTRO de ese contenido con position="move".
        source = arch('<doc><nodo><conservar/><descartar/></nodo></doc>')
        result = apply_inheritance_specs(
            source,
            spec('<xpath expr="//nodo" position="replace" mode="inner">'
                 '<nuevo><conservar position="move"/></nuevo>'
                 '</xpath>'))
        nodo = result.find('nodo')
        assert [c.tag for c in nodo] == ['nuevo']
        assert [c.tag for c in nodo.find('nuevo')] == ['conservar']
        assert nodo.find('descartar') is None

    def test_move_a_otra_posicion(self):
        source = arch('<doc><a/><b/><destino/></doc>')
        result = apply_inheritance_specs(
            source,
            spec('<xpath expr="//destino" position="inside">'
                 '<b position="move"/>'
                 '</xpath>'))
        assert [c.tag for c in result] == ['a', 'destino']
        assert [c.tag for c in result.find('destino')] == ['b']

    def test_spec_que_no_localiza_levanta(self):
        source = arch('<doc><a/></doc>')
        with pytest.raises(ValueError):
            apply_inheritance_specs(
                source, spec('<xpath expr="//inexistente" position="after"><b/></xpath>'))


class TestAttributes:
    def test_asignar_y_borrar_atributo(self):
        source = arch('<doc><nodo clase="x"/></doc>')
        result = apply_inheritance_specs(
            source,
            spec('<xpath expr="//nodo" position="attributes">'
                 '<attribute name="clase">y</attribute>'
                 '<attribute name="extra">1</attribute>'
                 '</xpath>'))
        nodo = result.find('nodo')
        assert nodo.get('clase') == 'y' and nodo.get('extra') == '1'

        result = apply_inheritance_specs(
            result,
            spec('<xpath expr="//nodo" position="attributes">'
                 '<attribute name="extra"></attribute>'
                 '</xpath>'))
        assert 'extra' not in result.find('nodo').attrib

    def test_add_remove_componen_listas(self):
        source = arch('<doc><nodo class="a b c"/></doc>')
        result = apply_inheritance_specs(
            source,
            spec('<xpath expr="//nodo" position="attributes">'
                 '<attribute name="class" add="d" remove="b" separator=" "/>'
                 '</xpath>'))
        assert result.find('nodo').get('class') == 'a c d'

    def test_expresion_python_exige_separador_booleano(self):
        source = arch('<doc><nodo invisible="ctx"/></doc>')
        with pytest.raises(ValueError):
            apply_inheritance_specs(
                source,
                spec('<xpath expr="//nodo" position="attributes">'
                     '<attribute name="invisible" add="otro" separator=","/>'
                     '</xpath>'))
        result = apply_inheritance_specs(
            arch('<doc><nodo invisible="ctx"/></doc>'),
            spec('<xpath expr="//nodo" position="attributes">'
                 '<attribute name="invisible" add="otro" separator=" or "/>'
                 '</xpath>'))
        assert result.find('nodo').get('invisible') == '(ctx) or (otro)'


class TestDataWrapper:
    def test_data_agrupa_varios_specs(self):
        # Una heredante real trae varios specs bajo <data>; se aplican todos.
        source = arch('<doc><a/><b/></doc>')
        result = apply_inheritance_specs(
            source,
            spec('<data>'
                 '<xpath expr="//a" position="after"><x/></xpath>'
                 '<xpath expr="//b" position="replace"><y/></xpath>'
                 '</data>'))
        assert [c.tag for c in result] == ['a', 'x', 'y']
