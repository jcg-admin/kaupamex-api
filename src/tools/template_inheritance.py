"""Herencia de vistas por XPath — fiel a ``odoo/tools/template_inheritance.py``.

Adaptado de Odoo Community 19 (LGPL-3), ``odoo-tools@622ddc2aa5`` — atribución
y aviso de licencia preservados (DEC-KX-03). Gobierna 19 sobre 18 porque
difieren (28 líneas): 19 introduce el *sentinel* que permite mover hijos
existentes dentro del contenido nuevo (``position="move"`` bajo
``replace mode="inner"``), capacidad que 18 no tiene.

Es el **motor** de la herencia de ``ir.ui.view``: funciones puras sobre
árboles lxml, sin ORM. El modelo (``addons/base/models/ir_ui_view.py``)
delega aquí, igual que en la referencia (``ir_ui_view.py:27``).

Divergencias declaradas respecto de la referencia:

- ``LazyTranslate('base')`` → ``tools.translate._`` (``gettext_lazy`` de
  Django); el formateo ``%`` se aplica al construir la excepción.
- ``html_escape`` viene de ``tools.misc``, que lo resuelve con Django en vez
  de ``markupsafe`` (decisión anotada allí).
"""
import copy
import itertools
import logging
import re

from lxml import etree
from lxml.builder import E

from exceptions import ValidationError
from tools.translate import _

from .misc import SKIPPED_ELEMENT_TYPES, html_escape

__all__ = []

_logger = logging.getLogger(__name__)
RSTRIP_REGEXP = re.compile(r'\n[ \t]*$')

# Atributos cuyo valor es una expresión Python: al componer ``add``/``remove``
# el separador debe ser un operador booleano, no una coma.
PYTHON_ATTRIBUTES = {'readonly', 'required', 'invisible', 'column_invisible', 't-if', 't-elif'}


def add_stripped_items_before(node, spec, extract):
    # Inserta el contenido de ``spec`` antes de ``node``, normalizando el
    # whitespace de frontera (texto/colas) para que el árbol resultante no
    # acumule saltos de línea de las vistas heredantes.
    text = spec.text or ''

    before_text = ''
    prev = next((n for n in node.itersiblings(preceding=True) if not (n.tag == etree.ProcessingInstruction and n.target == "apply-inheritance-specs-node-removal")), None)
    if prev is None:
        parent = node.getparent()
        result = parent.text and RSTRIP_REGEXP.search(parent.text)
        before_text = result.group(0) if result else ''
        fallback_text = None if spec.text is None else ''
        parent.text = ((parent.text or '').rstrip() + text) or fallback_text
    else:
        result = prev.tail and RSTRIP_REGEXP.search(prev.tail)
        before_text = result.group(0) if result else ''
        prev.tail = (prev.tail or '').rstrip() + text

    if len(spec) > 0:
        spec[-1].tail = (spec[-1].tail or "").rstrip() + before_text
    else:
        spec.text = (spec.text or "").rstrip() + before_text

    for child in spec:
        if child.get('position') == 'move':
            tail = child.tail
            child = extract(child)
            child.tail = tail
        node.addprevious(child)


def add_text_before(node, text):
    """Añade ``text`` antes de ``node`` en su árbol XML."""
    if text is None:
        return
    prev = node.getprevious()
    if prev is not None:
        prev.tail = (prev.tail or "") + text
    else:
        parent = node.getparent()
        parent.text = (parent.text or "").rstrip() + text


def remove_element(node):
    """Elimina ``node`` de su árbol XML, preservando su cola (``tail``)."""
    add_text_before(node, node.tail)
    node.tail = None
    node.getparent().remove(node)


def locate_node(arch, spec):
    """Localiza un nodo en una arquitectura fuente (la vista padre).

    Dada la arquitectura completa de la vista padre (el campo ``arch``) y un
    nodo *spec* (un nodo de la vista heredante que indica QUÉ lugar de la
    fuente se va a modificar), devuelve — si existe — el nodo de la fuente
    que la especificación señala.

    :param arch: arquitectura padre a modificar
    :param spec: nodo modificador de una vista heredante
    :return: el nodo de la fuente que coincide con el spec
    """
    if spec.tag == 'xpath':
        expr = spec.get('expr')
        if expr is None:
            raise ValidationError(_("Missing 'expr' attribute in xpath specification"))
        try:
            xPath = etree.ETXPath(expr)
        except etree.XPathSyntaxError as e:
            raise ValidationError(_("Invalid Expression while parsing xpath “%s”") % expr) from e
        nodes = xPath(arch)
        return nodes[0] if nodes else None
    elif spec.tag == 'field':
        # Sólo se compara el nombre del campo: un campo aparece una única vez
        # en una vista a un nivel dado (para expresiones multinivel el spec
        # correcto es xpath).
        for node in arch.iter('field'):
            if node.get('name') == spec.get('name'):
                return node
        return None

    for node in arch.iter(spec.tag):
        if all(node.get(attr) == spec.get(attr) for attr in spec.attrib if attr != 'position'):
            return node
    return None


def apply_inheritance_specs(source, specs_tree, inherit_branding=False, pre_locate=None):
    """Aplica una vista heredante (descendiente de la vista base).

    Aplica sobre una arquitectura fuente todos los nodos *spec* (nodos que
    describen dónde y qué cambios hacer sobre una arquitectura padre) que
    aporta una vista heredante.

    :param Element source: arquitectura padre a modificar
    :param Element specs_tree: arquitectura modificadora de la heredante
    :param bool inherit_branding: marca las remociones con una
        processing-instruction para que el branding del editor web pueda
        distribuirse; fuera de ese contexto es inerte
    :param pre_locate: función ejecutada antes de localizar cada nodo;
        recibe el spec como argumento
    :return: la fuente modificada con los specs aplicados
    :rtype: Element
    """
    # Cola de nodos de especificación (dónde y qué cambiar en el padre).
    specs = specs_tree if isinstance(specs_tree, list) else [specs_tree]
    pre_locate = pre_locate or (lambda _spec: True)

    def extract(spec):
        # Localiza el nodo que señala ``spec``, lo desprende de la fuente y
        # lo devuelve — el primitivo de ``position="move"``.
        if len(spec):
            raise ValueError(
                _("Invalid specification for moved nodes: “%s”") % etree.tostring(spec, encoding='unicode')
            )
        pre_locate(spec)
        to_extract = locate_node(source, spec)
        if to_extract is not None:
            remove_element(to_extract)
            return to_extract
        else:
            raise ValueError(
                _("Element “%s” cannot be located in parent view") % etree.tostring(spec, encoding='unicode')
            )

    while len(specs):
        spec = specs.pop(0)
        if isinstance(spec, SKIPPED_ELEMENT_TYPES):
            continue
        if spec.tag == 'data':
            specs += [c for c in spec]
            continue
        pre_locate(spec)
        node = locate_node(source, spec)
        if node is not None:
            pos = spec.get('position', 'inside')
            if pos == 'replace':
                mode = spec.get('mode', 'outer')
                if mode == "outer":
                    # ``$0`` dentro del spec = "el nodo reemplazado": se copia
                    # el original dentro del contenido nuevo.
                    for loc in spec.xpath(".//*[text()='$0']"):
                        loc.text = ''
                        copied_node = copy.deepcopy(node)
                        if inherit_branding:
                            copied_node.set('data-oe-no-branding', '1')
                        loc.append(copied_node)
                    if node.getparent() is None:
                        spec_content = None
                        comment = None
                        for content in spec:
                            if content.tag is not etree.Comment:
                                spec_content = content
                                break
                            else:
                                comment = content
                        source = copy.deepcopy(spec_content)
                        # de la raíz reemplazada sólo se conserva su t-name
                        t_name = node.get('t-name')
                        if t_name:
                            source.set('t-name', t_name)
                        if comment is not None:
                            text = source.text
                            source.text = None
                            comment.tail = text
                            source.insert(0, comment)
                    else:
                        # La referencia marca el lugar de la remoción con una
                        # processing-instruction cuando hay branding, para que
                        # la distribución posterior sepa dónde hubo un nodo.
                        # No se marca un nodo que ya trae branding xpath de
                        # raíz: rompería el branding de los hermanos.
                        if inherit_branding and not node.get('data-oe-xpath'):
                            node.addprevious(etree.ProcessingInstruction('apply-inheritance-specs-node-removal', node.tag))

                        for child in spec:
                            if child.get('position') == 'move':
                                child = extract(child)
                            node.addprevious(child)
                        node.getparent().remove(node)
                elif mode == "inner":
                    # Sentinel para conservar los hijos existentes mientras se
                    # inserta el contenido nuevo: así un hijo previo puede
                    # moverse DENTRO del contenido nuevo (position="move").
                    # Este sentinel es la diferencia 18→19 que hizo ganar a 19.
                    sentinel = E.sentinel()
                    if len(node) > 0:
                        node[0].addprevious(sentinel)
                    else:
                        node.append(sentinel)
                    # Rellena el nodo con el spec ANTES del sentinel; se
                    # limpia node.text primero para que no se fusione con el
                    # texto del contenido nuevo.
                    node.text = None
                    add_stripped_items_before(sentinel, copy.deepcopy(spec), extract)
                    # y ahora se retira el contenido viejo junto al sentinel
                    for child in reversed(node):
                        node.remove(child)
                        if child == sentinel:
                            break
                else:
                    raise ValueError(_("Invalid mode attribute: “%s”") % mode)
            elif pos == 'attributes':
                for child in spec.getiterator('attribute'):
                    # El elemento sólo admite estos atributos:
                    # - name (obligatorio),
                    # - add, remove, separator
                    # - cualquier data-oe-*
                    unknown = [
                        key
                        for key in child.attrib
                        if key not in ('name', 'add', 'remove', 'separator')
                        and not key.startswith('data-oe-')
                    ]
                    if unknown:
                        raise ValueError(_(
                            "Invalid attributes %s in element <attribute>"
                        ) % ", ".join(map(repr, unknown)))

                    attribute = child.get('name')
                    value = None

                    if child.get('add') or child.get('remove'):
                        if child.text:
                            raise ValueError(_(
                                "Element <attribute> with 'add' or 'remove' cannot contain text %s"
                            ) % repr(child.text))
                        value = node.get(attribute, '')
                        add = child.get('add', '')
                        remove = child.get('remove', '')
                        separator = child.get('separator')

                        if attribute in PYTHON_ATTRIBUTES or attribute.startswith('decoration-'):
                            # atributo con expresión Python: el separador es
                            # un operador booleano
                            separator = separator.strip()
                            if separator not in ('and', 'or'):
                                raise ValueError(_(
                                    "Invalid separator %(separator)s for python expression %(expression)s; "
                                    "valid values are 'and' and 'or'"
                                ) % {'separator': repr(separator), 'expression': repr(attribute)})
                            if remove:
                                if re.match(rf'^\(*{remove}\)*$', value):
                                    value = ''
                                else:
                                    patterns = [
                                        f"({remove}) {separator} ",
                                        f" {separator} ({remove})",
                                        f"{remove} {separator} ",
                                        f" {separator} {remove}",
                                    ]
                                    for pattern in patterns:
                                        index = value.find(pattern)
                                        if index != -1:
                                            value = value[:index] + value[index + len(pattern):]
                                            break
                            if add:
                                value = f"({value}) {separator} ({add})" if value else add
                        else:
                            if separator is None:
                                separator = ','
                            elif separator == ' ':
                                separator = None    # colapsa espacios
                            values = (s.strip() for s in value.split(separator))
                            to_add = filter(None, (s.strip() for s in add.split(separator)))
                            to_remove = {s.strip() for s in remove.split(separator)}
                            value = (separator or ' ').join(itertools.chain(
                                (v for v in values if v and v not in to_remove),
                                to_add
                            ))
                    else:
                        value = child.text or ''

                    if value:
                        node.set(attribute, value)
                    elif attribute in node.attrib:
                        del node.attrib[attribute]
            elif pos == 'inside':
                # sentinel al final, insertar el spec antes del sentinel,
                # retirar el sentinel
                sentinel = E.sentinel()
                node.append(sentinel)
                add_stripped_items_before(sentinel, spec, extract)
                remove_element(sentinel)
            elif pos == 'after':
                # sentinel justo después del nodo, insertar el spec antes del
                # sentinel, retirar el sentinel
                sentinel = E.sentinel()
                node.addnext(sentinel)
                if node.tail is not None:  # para lxml >= 5.1
                    sentinel.tail = node.tail
                    node.tail = None
                add_stripped_items_before(sentinel, spec, extract)
                remove_element(sentinel)
            elif pos == 'before':
                add_stripped_items_before(node, spec, extract)

            else:
                raise ValueError(_("Invalid position attribute: '%s'") % pos)

        else:
            attrs = ''.join([
                ' %s="%s"' % (attr, html_escape(spec.get(attr)))
                for attr in spec.attrib
                if attr != 'position'
            ])
            tag = "<%s%s>" % (spec.tag, attrs)
            raise ValueError(
                _("Element '%s' cannot be located in parent view") % tag
            )

    return source
