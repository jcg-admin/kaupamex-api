"""Parche, comparación y *unified diff* entre dos versiones de un HTML.

Adaptación de ``odoo19c: addons/html_editor/models/diff_utils.py``
(349 líneas, LGPL-3 — copia + adaptación con atribución, DEC-KX-03; la
licencia se leyó del manifiesto de la fuente, no de la reputación del árbol).

**14 símbolos en la fuente, 14 portados, 0 ausentes.** Diez constantes de
módulo y cuatro funciones públicas más tres privadas; el censo verbatim está
en la tabla de abajo.

Qué hace, y por qué su unidad es el ``<``
=========================================

El historial de un campo HTML no guarda cada versión entera: guarda la
**primera** y, por cada revisión, el parche que la revierte. Este archivo es
ese formato de parche.

La unidad de línea NO es el salto de línea: es el carácter ``<``. Partir por
``<`` deja **una etiqueta por elemento de la lista**, así que un cambio dentro
de un párrafo mueve un elemento y no toda la cadena. Es la decisión que hace
que el parche sea corto y que el *diff* señale el nodo y no el documento.

Qué pieza de este stack cubre cada delegación de la fuente
==========================================================

===============================  =====================================
Fuente delega en                 Aquí lo cubre
===============================  =====================================
``difflib`` (stdlib)             **cpython** — ``SequenceMatcher`` y
                                 ``unified_diff``, los mismos. Ver
                                 «La decisión de ``difflib``».
``bs4`` (``BeautifulSoup``) en   **lxml** — el inventario del stack le
``_indent``                      asigna a ``lxml`` el parseo y la
                                 construcción de nodos, y ``bs4`` no es
                                 dependencia declarada de este proyecto.
                                 Ver «La decisión de ``_indent``».
``re`` (stdlib)                  **cpython**
===============================  =====================================

La decisión de ``difflib``
==========================

El enunciado de la tarea plantea la alternativa: ``difflib`` de la biblioteca
estándar o un algoritmo propio. Se elige ``difflib``, y el criterio es
**reproducir la salida de la fuente**, no la elegancia:

- El formato de parche que este archivo emite —``R@12,15:<p>…``— codifica los
  ``opcodes`` de ``SequenceMatcher`` (``replace``/``delete``/``insert``) y sus
  índices. Un algoritmo propio con otra segmentación produciría **otros
  índices**, y los parches ya guardados en ``html_field_history`` dejarían de
  aplicarse: el historial es dato persistido, no cálculo repetible.
- ``get_grouped_opcodes(0)`` —con ``n=0``, sin líneas de contexto— es lo que
  produce un grupo por región cambiada. Reimplementarlo es reimplementar
  Ratcliff/Obershelp con su heurística de *junk*, que es trabajo sin
  contrapartida: mismo resultado, más superficie que mantener.
- Coste: ``difflib`` es cuadrático en el peor caso. Acotado por
  ``_html_field_history_size_limit`` (300 revisiones) y por el tamaño de un
  campo HTML de un registro, no de un documento arbitrario.

La decisión de ``_indent``
==========================

La fuente indenta con ``BeautifulSoup(...).prettify()`` **sólo** para alimentar
``unified_diff``: el *diff* unificado es por líneas, así que sin un renderizado
línea-por-nodo compararía dos cadenas de una sola línea y su salida sería
inútil.

``bs4`` no está entre las dependencias de este proyecto y el inventario del
stack asigna a ``lxml`` el parseo y la construcción de nodos. Las dos opciones
con ``lxml`` eran:

1. ``etree.tostring(root, pretty_print=True)`` — **descartada**. ``lxml`` no
   indenta un elemento con contenido mixto (texto y elementos hermanos), que
   es exactamente la forma de un campo HTML redactado por una persona: el
   resultado sería una línea larga, y el *diff* volvería a ser inútil.
2. Un recorrido propio que emite **una etiqueta por línea** — el que se
   implementa. Es determinista, no depende de la heurística de contenido mixto
   de ninguna versión de ``lxml``, y da al ``unified_diff`` la granularidad de
   nodo que su consumidor (la vista de historial) necesita.

Divergencia declarada: la salida de :func:`_indent` **no es byte a byte** la
de ``prettify()``. Lo que se conserva es su contrato —una unidad sintáctica
por línea, atributos incluidos— porque es lo único que ``unified_diff``
consume. La salida de esta función no se persiste en ninguna parte: se calcula
al vuelo para mostrar un *diff* y se descarta.

Censo símbolo a símbolo
=======================

=================================  =========  ==========================
Símbolo de la fuente               Portado    Nota
=================================  =========  ==========================
``OPERATION_SEPARATOR``            sí         verbatim
``LINE_SEPARATOR``                 sí         verbatim
``PATCH_OPERATION_LINE_AT``        sí         verbatim
``PATCH_OPERATION_CONTENT``        sí         verbatim
``PATCH_OPERATION_ADD``            sí         verbatim
``PATCH_OPERATION_REMOVE``         sí         verbatim
``PATCH_OPERATION_REPLACE``        sí         verbatim
``PATCH_OPERATIONS``               sí         verbatim
``HTML_ATTRIBUTES_TO_REMOVE``      sí         verbatim
``HTML_TAG_ISOLATION_REGEX``       sí         verbatim
``ADDITION_COMPARISON_REGEX``      sí         verbatim
``ADDITION_1ST_REPLACE_COMPARISON_REGEX``  sí  verbatim; la fuente lo
                                              declara y no lo consume
``DELETION_COMPARISON_REGEX``      sí         verbatim
``EMPTY_OPERATION_TAG``            sí         verbatim
``SAME_TAG_REPLACE_FIXER``         sí         verbatim
``UNNECESSARY_REPLACE_FIXER``      sí         verbatim
``apply_patch``                    sí         verbatim
``generate_comparison``            sí         verbatim
``_format_line_index``             sí         verbatim
``_patch_generator``               sí         verbatim
``generate_patch``                 sí         verbatim
``_remove_html_attribute``         sí         verbatim
``_indent``                        sí         ``bs4`` → ``lxml``
``generate_unified_diff``          sí         verbatim
=================================  =========  ==========================

``ADDITION_1ST_REPLACE_COMPARISON_REGEX`` se conserva aunque la fuente no lo
use: retirarlo sería decidir por su autor que el símbolo sobra, y el símbolo
es API del módulo (sin guion bajo). Su ausencia rompería a quien lo importe.
"""
import re
from difflib import SequenceMatcher, unified_diff

from lxml import html

# ------------------------------------------------------------
# Funciones de parche y comparación
# ------------------------------------------------------------


OPERATION_SEPARATOR = "\n"
LINE_SEPARATOR = "<"

PATCH_OPERATION_LINE_AT = "@"
PATCH_OPERATION_CONTENT = ":"

PATCH_OPERATION_ADD = "+"
PATCH_OPERATION_REMOVE = "-"
PATCH_OPERATION_REPLACE = "R"

PATCH_OPERATIONS = dict(
    insert=PATCH_OPERATION_ADD,
    delete=PATCH_OPERATION_REMOVE,
    replace=PATCH_OPERATION_REPLACE,
)

HTML_ATTRIBUTES_TO_REMOVE = ["data-last-history-steps"]
HTML_TAG_ISOLATION_REGEX = r"^([^>]*>)(.*)$"
ADDITION_COMPARISON_REGEX = r"\1<added>\2</added>"
ADDITION_1ST_REPLACE_COMPARISON_REGEX = r"added>\2</added>"
DELETION_COMPARISON_REGEX = r"\1<removed>\2</removed>"
EMPTY_OPERATION_TAG = r"<(added|removed)><\/(added|removed)>"
SAME_TAG_REPLACE_FIXER = r"<\/added><(?:[^\/>]|(?:><))+><removed>"
UNNECESSARY_REPLACE_FIXER = (
    r"<added>([^<](?!<\/added>)*)<\/added>"
    r"<removed>([^<](?!<\/removed>)*)<\/removed>"
)


def apply_patch(initial_content, patch):
    """Aplica un parche (varias operaciones) sobre un contenido.

    Cada operación es una cadena con el formato::

        <tipo_operacion>@<indice_inicio>[,<indice_fin>][:<texto_parche>*]

    Ejemplo de formato de parche::

        +@4:<p>ab</p><p>cd</p>
        +@4,15:<p>ef</p><p>gh</p>
        -@32
        -@125,129
        R@523:<b>sdf</b>

    :param string initial_content: el contenido inicial a parchear
    :param string patch: el parche a aplicar

    :return: string: el contenido parcheado
    """
    if not patch:
        return initial_content

    # Se retiran los saltos de línea del contenido inicial para que no
    # interfieran con las operaciones.
    initial_content = initial_content.replace("\n", "")
    initial_content = _remove_html_attribute(
        initial_content, HTML_ATTRIBUTES_TO_REMOVE
    )

    content = initial_content.split(LINE_SEPARATOR)
    patch_operations = patch.split(OPERATION_SEPARATOR)
    # Las operaciones se aplican en orden inverso para preservar la
    # integridad de los índices.
    patch_operations.reverse()

    for operation in patch_operations:
        metadata, *patch_content_line = operation.split(LINE_SEPARATOR)

        metadata_split = metadata.split(PATCH_OPERATION_LINE_AT)
        operation_type = metadata_split[0]
        lines_index_range = metadata_split[1] if len(metadata_split) > 1 else ""
        # Hay que quitar el carácter PATCH_OPERATION_CONTENT del rango.
        lines_index_range = lines_index_range.split(PATCH_OPERATION_CONTENT)[0]
        indexes = lines_index_range.split(",")
        start_index = int(indexes[0]) if len(indexes) else 0
        end_index = int(indexes[1]) if len(indexes) > 1 else start_index

        # Las líneas se insertan de la última a la primera para preservar la
        # integridad de los índices.
        patch_content_line.reverse()

        if end_index > start_index:
            for index in range(end_index, start_index, -1):
                if operation_type in [
                    PATCH_OPERATION_REMOVE,
                    PATCH_OPERATION_REPLACE,
                ]:
                    del content[index]

        if operation_type in [PATCH_OPERATION_ADD, PATCH_OPERATION_REPLACE]:
            for line in patch_content_line:
                content.insert(start_index + 1, line)
        if operation_type in [PATCH_OPERATION_REMOVE, PATCH_OPERATION_REPLACE]:
            del content[start_index]

    return LINE_SEPARATOR.join(content)


def generate_comparison(new_content, old_content):
    """Compara un contenido contra uno anterior y genera el HTML comparado.

    :param string new_content: el contenido actual
    :param string old_content: el contenido viejo

    :return: string: el contenido de la comparación
    """
    new_content = _remove_html_attribute(new_content, HTML_ATTRIBUTES_TO_REMOVE)
    old_content = _remove_html_attribute(old_content, HTML_ATTRIBUTES_TO_REMOVE)

    if new_content == old_content:
        return new_content

    patch = generate_patch(new_content, old_content)
    comparison = new_content.split(LINE_SEPARATOR)
    patch_operations = patch.split(OPERATION_SEPARATOR)
    # Las operaciones se aplican de la última a la primera para preservar la
    # integridad de los índices.
    patch_operations.reverse()

    for operation in patch_operations:
        metadata, *patch_content_line = operation.split(LINE_SEPARATOR)

        metadata_split = metadata.split(PATCH_OPERATION_LINE_AT)
        operation_type = metadata_split[0]
        lines_index_range = metadata_split[1] if len(metadata_split) > 1 else ""
        lines_index_range = lines_index_range.split(PATCH_OPERATION_CONTENT)[0]
        indexes = lines_index_range.split(",")
        start_index = int(indexes[0]) if len(indexes) else 0
        end_index = int(indexes[1]) if len(indexes) > 1 else start_index

        # Si la operación es un reemplazo hay que marcar los cambios que
        # generarían etiquetas de apertura fantasma si no se ignoran.
        # Esto pasa cuando:
        # * El cambio afecta sólo a parámetros html.
        #   <p class="x">a</p> => <p class="y">a</p>
        # * Hay una adición dentro de una etiqueta antes vacía.
        #   <p></p> => <p>a</p>
        if operation_type == PATCH_OPERATION_REPLACE:
            for i, line in enumerate(patch_content_line):
                current_index = start_index + i
                if current_index > end_index:
                    break

                current_line = comparison[current_index]
                current_line_tag = current_line.split(">")[0]
                line_tag = line.split(">")[0]
                if current_line[-1] == ">" and (
                    current_line_tag == line_tag
                    or current_line_tag.split(" ")[0] == line_tag.split(" ")[0]
                ):
                    comparison[start_index + i] = "delete_me>"

        # Las líneas se insertan de la última a la primera para preservar la
        # integridad de los índices.
        patch_content_line.reverse()

        for index in range(end_index, start_index - 1, -1):
            if operation_type in [
                PATCH_OPERATION_REMOVE,
                PATCH_OPERATION_REPLACE,
            ]:
                deletion_flagged_comparison = re.sub(
                    HTML_TAG_ISOLATION_REGEX,
                    DELETION_COMPARISON_REGEX,
                    comparison[index],
                )
                # Sólo se usa esta línea si no genera una etiqueta <removed>
                # vacía.
                if not re.search(
                    EMPTY_OPERATION_TAG, deletion_flagged_comparison
                ):
                    comparison[index] = deletion_flagged_comparison

        if operation_type == PATCH_OPERATION_ADD:
            for line in patch_content_line:
                addition_flagged_line = re.sub(
                    HTML_TAG_ISOLATION_REGEX, ADDITION_COMPARISON_REGEX, line
                )

                if not re.search(EMPTY_OPERATION_TAG, addition_flagged_line):
                    comparison.insert(start_index + 1, addition_flagged_line)
                else:
                    comparison.insert(start_index + 1, line)

        if operation_type == PATCH_OPERATION_REPLACE:
            for line in patch_content_line:
                addition_flagged_line = re.sub(
                    HTML_TAG_ISOLATION_REGEX, ADDITION_COMPARISON_REGEX, line
                )
                if not re.search(EMPTY_OPERATION_TAG, addition_flagged_line):
                    comparison.insert(start_index, addition_flagged_line)
                elif (
                    line.split(">")[0] != comparison[start_index].split(">")[0]
                    or line.startswith("/")
                ):
                    comparison.insert(start_index, line)

    final_comparison = LINE_SEPARATOR.join(comparison)
    # Se pueden retirar todas las etiquetas de apertura que quedan entre el
    # fin de una etiqueta <added> y el inicio de una <removed>, porque eso no
    # debería ocurrir nunca: las dos deberían estar siempre contiguas. Pasa
    # cuando la etiqueta contenedora nueva cambió un parámetro.
    final_comparison = re.sub(
        SAME_TAG_REPLACE_FIXER, "</added><removed>", final_comparison
    )

    # Se retiran todas las etiquetas <delete_me>.
    final_comparison = final_comparison.replace(r"<delete_me>", "")

    # Esto corrige el problema de las etiquetas de reemplazo innecesarias.
    # ej: <added>abc</added><removed>abc</removed> -> abc
    # Ocurre cuando el contenido nuevo es igual al viejo y sus contenedores
    # son iguales pero con parámetros distintos.
    for match in re.finditer(UNNECESSARY_REPLACE_FIXER, final_comparison):
        if match.group(1) == match.group(2):
            final_comparison = final_comparison.replace(
                match.group(0), match.group(1)
            )

    return final_comparison


def _format_line_index(start, end):
    """Formatea el índice de línea que usa una operación de parche.

    :param start: el índice inicial
    :param end: el índice final
    :return: string
    """
    length = end - start
    if not length:
        start -= 1
    if length <= 1:
        return "%s%s" % (PATCH_OPERATION_LINE_AT, start)
    return "%s%s,%s" % (PATCH_OPERATION_LINE_AT, start, start + length - 1)


def _patch_generator(new_content, old_content):
    """Genera un parche (varias operaciones) entre dos contenidos.

    Cada operación es una cadena con el formato::

        <tipo_operacion>@<indice_inicio>[,<indice_fin>][:<texto_parche>*]

    Ejemplo de formato de parche::

        +@4:<p>ab</p><p>cd</p>
        +@4,15:<p>ef</p><p>gh</p>
        -@32
        -@125,129
        R@523:<b>sdf</b>

    :param string new_content: el contenido nuevo
    :param string old_content: el contenido viejo

    :return: string: el parche con todas las operaciones que revierten el
             contenido nuevo al viejo
    """
    # Se retiran los saltos de línea de ambos contenidos para que no
    # interfieran con las operaciones.
    new_content = new_content.replace("\n", "")
    old_content = old_content.replace("\n", "")

    new_content_lines = new_content.split(LINE_SEPARATOR)
    old_content_lines = old_content.split(LINE_SEPARATOR)

    for group in SequenceMatcher(
        None, new_content_lines, old_content_lines, False
    ).get_grouped_opcodes(0):
        patch_content_line = []
        first, last = group[0], group[-1]
        patch_operation = _format_line_index(first[1], last[2])

        if any(tag in {"replace", "delete"} for tag, _, _, _, _ in group):
            for tag, _, _, _, _ in group:
                if tag not in {"insert", "equal", "replace"}:
                    patch_operation = PATCH_OPERATIONS[tag] + patch_operation

        if any(tag in {"replace", "insert"} for tag, _, _, _, _ in group):
            for tag, _, _, j1, j2 in group:
                if tag not in {"delete", "equal"}:
                    patch_operation = PATCH_OPERATIONS[tag] + patch_operation
                    for line in old_content_lines[j1:j2]:
                        patch_content_line.append(line)

        if patch_content_line:
            patch_content = LINE_SEPARATOR + LINE_SEPARATOR.join(
                patch_content_line
            )
            yield str(patch_operation) + PATCH_OPERATION_CONTENT + patch_content
        else:
            yield str(patch_operation)


def generate_patch(new_content, old_content):
    """Une en una cadena todas las operaciones de :func:`_patch_generator`."""
    new_content = _remove_html_attribute(new_content, HTML_ATTRIBUTES_TO_REMOVE)
    old_content = _remove_html_attribute(old_content, HTML_ATTRIBUTES_TO_REMOVE)

    return OPERATION_SEPARATOR.join(
        list(_patch_generator(new_content, old_content))
    )


def _remove_html_attribute(html_content, attributes_to_remove):
    """Retira del HTML los atributos nombrados, con su valor entrecomillado."""
    for attribute in attributes_to_remove:
        html_content = re.sub(
            r' %s="[^"]*"' % attribute, "", html_content
        )

    return html_content


def _serialize_indented(element, depth, output):
    """Emite ``element`` y su subárbol, una unidad sintáctica por línea.

    ≙ el recorrido interno de ``prettify()``. Cada etiqueta de apertura, cada
    nodo de texto no vacío y cada etiqueta de cierre ocupan **su propia
    línea**, con dos espacios de sangría por nivel. Es lo que da al
    ``unified_diff`` granularidad de nodo; ver «La decisión de ``_indent``».
    """
    indent = "  " * depth
    attributes = "".join(
        ' %s="%s"' % (name, value) for name, value in element.attrib.items()
    )
    output.append("%s<%s%s>" % (indent, element.tag, attributes))

    if element.text and element.text.strip():
        output.append("%s  %s" % (indent, element.text.strip()))

    for child in element:
        if isinstance(child.tag, str):
            _serialize_indented(child, depth + 1, output)
        if child.tail and child.tail.strip():
            output.append("%s  %s" % (indent, child.tail.strip()))

    output.append("%s</%s>" % (indent, element.tag))


def _indent(content):
    """Indenta el contenido para que ``unified_diff`` pueda compararlo.

    :param string content: el contenido a indentar

    :return: string: el contenido indentado
    """
    content = "<document>" + _remove_html_attribute(
        content, HTML_ATTRIBUTES_TO_REMOVE) + "</document>"
    # ``html.fromstring`` tolera el HTML mal formado que una persona escribe
    # en un campo de texto enriquecido; ``etree.fromstring`` levantaría.
    root = html.fromstring(content, parser=html.HTMLParser(encoding='utf-8'))
    # El parser de HTML de lxml envuelve el fragmento en <html><body>; se
    # desciende hasta el <document> que este método añadió, que es la raíz
    # que la fuente indenta.
    for candidate in root.iter('document'):
        root = candidate
        break
    output = []
    _serialize_indented(root, 0, output)
    return OPERATION_SEPARATOR.join(output) + OPERATION_SEPARATOR


def generate_unified_diff(new_content, old_content):
    """Genera un *unified diff* entre dos contenidos.

    :param string new_content: el contenido actual
    :param string old_content: el contenido viejo

    :return: string: el *unified diff*
    """
    new_content = _indent(new_content)
    old_content = _indent(old_content)

    return OPERATION_SEPARATOR.join(
        list(unified_diff(
            old_content.split(OPERATION_SEPARATOR),
            new_content.split(OPERATION_SEPARATOR),
            fromfile='old',
            tofile='new'
        ))
    )
