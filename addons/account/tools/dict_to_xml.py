"""``dict_to_xml`` -- serializa un ``dict`` Python como nodo XML.

Adaptacion de ``odoo19c: addons/account/tools/dict_to_xml.py``
(``odoo-tools@622ddc2a``, LGPL-3 -- atribucion y aviso de licencia
preservados, DEC-KX-03). Es una funcion pura: no depende de ningun modelo
ni del ORM, asi que el porte es completo simbolo a simbolo.

Cobertura del porte -- 1 de 1 simbolo publico
==============================================

.. list-table::
   :header-rows: 1

   * - Simbolo
     - Estado
   * - ``dict_to_xml``
     - portado verbatim (misma firma, mismo contrato)

**Divergencia declarada -- ``remove_control_characters``.** La fuente la
importa de ``odoo.tools.xml_utils`` (``odoo19c: odoo/tools/xml_utils.py:24``).
Ese modulo no existe en el espejo ``src/tools/`` de este arbol y crearlo esta
fuera de mi alcance de escritura en este pase (no esta en la lista de
archivos escribibles de la tarea #398). Es una funcion pura de ~10 lineas sin
ningun otro consumidor medido en el arbol
(``grep -rn "remove_control_characters" src/ addons/`` -> 0 hits antes de
este archivo), asi que se vendoriza aqui como
``_remove_control_characters``, equivalente a la fuente (mismo rango de
caracteres validos segun la especificacion XML 1.0 citada en su docstring,
construido con ``chr(codepoint)`` en vez de escapes de barra para no
depender de como el editor normalice backslashes). Si en el futuro un
segundo consumidor la necesita, el sitio correcto es
``src/tools/xml_utils.py`` (tarea **#401**, DESCONOCIDA hasta que aparezca
ese segundo consumidor).
"""
import re

from lxml import etree

#: Puntos de codigo validos segun XML 1.0 (``odoo19c:
#: odoo/tools/xml_utils.py:31-39``), armados con ``chr(N)`` sobre el entero
#: exacto -- evita que un escape de barra invertida (``\t``, ``퟿``...)
#: se corrompa al pasar por una herramienta que normalice el texto del
#: archivo.
_TAB = chr(9)
_LINE_FEED = chr(10)
_CARRIAGE_RETURN = chr(13)
_XML_VALID_CHAR_RANGES = (
    _TAB
    + _LINE_FEED
    + _CARRIAGE_RETURN
    + chr(0x20) + '-' + chr(0xD7FF)
    + chr(0xE000) + '-' + chr(0xFFFD)
    + chr(0x10000) + '-' + chr(0x10FFFF)
)
_CONTROL_CHARACTERS_RE = re.compile(('[^' + _XML_VALID_CHAR_RANGES + ']').encode())


def _remove_control_characters(byte_node):
    """Quita los caracteres de control no permitidos por XML 1.0.

    Vendorizado de ``odoo19c: odoo/tools/xml_utils.py:24-42`` -- ver la nota
    de procedencia en el docstring del modulo. Los caracteres a escapar son
    los de control ``#x0`` a ``#x1F`` y ``#x7F`` (la mayoria no puede
    aparecer en XML); el estandar acepta un ``Char`` de tab, salto de linea,
    retorno de carro, o uno de los tres rangos altos declarados arriba.

    Fuente: https://www.w3.org/TR/xml/
    """
    return _CONTROL_CHARACTERS_RE.sub(b'', byte_node)


def dict_to_xml(node, *, nsmap={}, template=None, render_empty_nodes=False, tag=None, path=None):
    """Ayudante para renderizar un ``dict`` Python como nodo XML.

    Se espera que el ``dict`` tenga esta forma::

        {
            # Claves especiales:
            '_tag': 'tag_name',      # '_tag' se renderiza como el tag del nodo
            '_text': 'content',      # '_text' se renderiza como texto del nodo
            '_dummy': 'dummy_value', # las claves con '_' no se renderizan

            # Los valores simples se renderizan como atributos
            'attribute_name': 'attribute_value',

            # Los dicts se renderizan como nodos hijos
            'child_tag': {
                '_text': 'content',
                'attribute_name': 'attribute_value',
            },

            # Las listas de dicts tambien se renderizan como nodos hijos
            'child_tag': [
                {
                    '_text': 'content',
                    'attribute_name': 'attribute_value',
                },
            ],
        }

    :param node: el ``dict`` Python a renderizar.
    :param nsmap: (opcional) ``dict`` de namespaces para renderizar el nodo.
    :param template: (opcional) ``dict`` Python que da valores por defecto y
        un orden de claves para renderizar el nodo.
    :param render_empty_nodes: (opcional) si es ``True``, los nodos vacios
        se renderizan igual en el arbol XML.
    :param tag: (opcional) el tag del nodo a renderizar (solo hace falta en
        llamadas recursivas).
    :param path: (opcional) la ruta del nodo actual dentro del arbol XML
        (solo hace falta en llamadas recursivas).
    :return: el nodo XML renderizado, como ``lxml.Element``, o ``None`` si
        quedo vacio y ``render_empty_nodes`` es ``False``.
    """
    def convert_tag_to_lxml_convention(tag):
        if ':' in tag:
            namespace, local_name = tag.split(':')
            if namespace in nsmap:
                return etree.QName(nsmap[namespace], local_name).text
        return tag

    if template is not None:
        # Asegura el orden de las claves
        node = dict.fromkeys(template) | node

    tag = node.get('_tag') or (template or {}).get('_tag', tag)

    if tag is None:
        raise ValueError(f"No se especifico tag para el nodo: {str(node)[:20]}")

    if path is None:
        path = tag

    element = etree.Element(convert_tag_to_lxml_convention(tag), nsmap=nsmap)

    # Anade atributos
    for attr_name, attr_value in node.items():
        if not attr_name.startswith('_') and not isinstance(attr_value, (dict, list)) and attr_value is not None and attr_value is not False:
            element.set(convert_tag_to_lxml_convention(attr_name), str(attr_value))

    # Anade el texto, si lo hay
    text = node.get('_text')
    if text is not None and text is not False:
        element.text = _remove_control_characters(str(text).encode()).decode()

    # Anade nodos hijos
    for child_tag, child in node.items():
        if not child_tag.startswith('_') and isinstance(child, (dict, list)):
            child_template = (template or {}).get(child_tag)
            child_is_empty = True
            if isinstance(child, dict):
                child = [child]

            # child es una lista (de dicts)
            for sub_child in child:
                if sub_child is not None:
                    child_element = dict_to_xml(
                        sub_child,
                        nsmap=nsmap,
                        template=child_template,
                        render_empty_nodes=render_empty_nodes,
                        tag=child_tag,
                        path=f'{path}/{child_tag}',
                    )
                    if child_element is not None:
                        element.append(child_element)
                        child_is_empty = False

            # Verifica que todo nodo hijo no vacio este definido en el template
            if template is not None and child_tag not in template and not child_is_empty:
                raise ValueError(f"El siguiente nodo hijo no esta definido en el template: {path}/{child_tag}")

    if not render_empty_nodes and not element.attrib and not element.text and len(element) == 0:
        return None

    return element
