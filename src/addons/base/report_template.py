"""Plantilla-descriptor de reportes — el intérprete sobre ``ir.ui.view``.

**Forma propia, declarada como tal.** La referencia no cubre este caso: allá
la plantilla del reporte emite HTML (QWeb) y ``wkhtmltopdf`` lo convierte,
así que la plantilla puede ser HTML libre. Aquí el conversor es el helper de
``tools/pdf/`` y **no acepta HTML** — consume un descriptor JSON. Lo que este
módulo define es el punto medio que preserva las dos propiedades que la
directiva del ejecutor pide:

- *lo que se lee* es un **registro en BD** (``ir.ui.view``, ``type='template'``,
  resuelto por ``key`` = ``report_name``) — igual que la referencia
  (``odoo19c: ir_actions_report.py:769-781`` resuelve ``ir.ui.view``);
- *cómo llega el documento* es **interpretado**, no ejecutado: el arch es XML
  con forma de descriptor, y los valores son expresiones DTL evaluadas
  contra el registro — el mismo intérprete vivo del árbol
  (``mail/models/mail_template.py:100``).

Que el arch sea **XML** y no el JSON directo no es capricho: es lo que hace
al documento **extensible por XPath** — ``sale_stock`` añade su bloque
*incoterm* al reporte de ``sale`` con un ``<xpath position=…>``
(``odoo19c: sale_stock/report/sale_order_report_templates.xml``), y esa
herencia opera sobre nodos, no sobre texto. Un JSON en texto plano no tendría
dónde anclar el parche.

Vocabulario del arch (deliberadamente mínimo)
=============================================

===============================  =============================================
Elemento                         Qué produce en el descriptor
===============================  =============================================
``<descriptor>``                 el objeto raíz
``<section name="k">…</section>``  ``k`` → objeto (dict) con sus hijos
``<field name="k">expr</field>``   ``k`` → string: el texto renderizado con DTL
``<list name="k" in="path">…``     ``k`` → lista; ``path`` se resuelve con DTL
                                   sobre el contexto y se itera exponiendo
                                   cada elemento como ``item`` y su posición
                                   como ``loop``
``<set name="k" value="path"/>``   nada en el documento: liga ``k`` para los
                                   hermanos siguientes, dentro de su nodo
``<call key="k"/>``                injerta los hijos del descriptor ``k``
===============================  =============================================

Y un atributo que vale en cualquiera de ellos:

``when="path"``
    el nodo entra al documento sólo si el path resuelve a un valor cierto.
    **Fail-closed**: un path que no resuelve levanta, no se lee como falso.

Las tres capacidades nuevas —condicional, variable local e injerto— son
``t-if``, ``t-set`` y ``t-call`` **construidas**, no traídas: DTL trae hechos
``{% if %}``, ``{% with %}`` e ``{% include %}``, pero para un motor de
**texto**. Aquí el sustrato es un árbol XML que se interpreta a un dict, y el
recorrido que decide qué nodo entra es nuestro. Es la distinción que
``tests/unit/base/test_native_substrate_for_the_three_pieces.py`` abre: *el
stack lo trae hecho* frente a *el stack tiene con qué construirlo*. Éstas son
del segundo grupo, y DEC-FW-05 fija por qué DTL es el evaluador.

``loop`` expone ``index`` (base 0), ``number`` (base 1), ``first``, ``last``,
``even``, ``odd`` y ``size``. La paridad va incluida porque el ``forloop`` de
DTL **no** la expone —se construye con el filtro ``divisibleby``— y un
descriptor la pide a menudo.

Por qué DTL y no el compilador portado (DEC-FW-05)
==================================================

``IrTemplateExpressions._compile_expr`` existe en este árbol, portado fiel de
la fuente con su allowlist de opcodes, y **no se cablea aquí**. Los dos
candidatos se midieron con las mismas expresiones
(``tests/unit/base/test_template_engine_choice.py``): DTL **rechaza** la
aritmética y la llamada con argumentos; el compilador las admite.

Para un **descriptor** ese rechazo es la propiedad que se quiere: el modelo
calcula y expone el campo, y la plantilla sólo lo lee. Toda superficie de más
en un evaluador es superficie que hay que contener, y la de DTL se contiene
**por gramática** —``Variable('line.__class__')`` levanta
``TemplateSyntaxError``— sin necesidad del allowlist.

Su caveat, medido y con su consecuencia ya cerrada (:ref:`h-api-930`): DTL
**invoca por su cuenta** un callable que encuentre en el contexto, y su guarda
es ``alters_data``.

DTL corre con ``autoescape`` **apagado**: el texto va a un dict de Python y
``json.dumps`` se encarga del quoting; con autoescape encendido un ``&`` del
dato llegaría al papel como ``&amp;`` (medido en
``analisis-motor-de-plantillas-django-y-el-descriptor-json``).
"""
from django.template import Context, Engine, Variable, VariableDoesNotExist

from tools.translate import _

#: Motor DTL propio del intérprete. ``autoescape=False`` es parte del
#: contrato (ver el docstring del módulo); no se reusa el engine global de
#: settings para no heredar su autoescape ni sus context processors.
_ENGINE = Engine(autoescape=False)


class InvalidReportTemplate(ValueError):
    """El arch combinado no respeta el vocabulario de la plantilla."""


def _render_text(text, context):
    # Un valor del descriptor: texto plano o expresión DTL. Se renderiza con
    # el motor del módulo — el mismo camino que mail_template usa para
    # body_html, con el autoescape que el descriptor exige.
    if not text or ('{{' not in text and '{%' not in text):
        return (text or '').strip()
    template = _ENGINE.from_string(text)
    return template.render(Context(context, autoescape=False)).strip()


def _resolve_path(path, context):
    # ``in="order.order_line.all"`` — la resolución de variables de DTL, la
    # misma que un ``{{ }}`` usa por dentro (llama callables sin argumentos,
    # p. ej. managers .all).
    #
    # ``AttributeError`` entra en la guarda a propósito, y no es defensa
    # genérica: DTL degrada a ``string_if_invalid`` en dos ramas —el callable
    # que exige argumentos (``django/template/base.py:1009-1011``) y el que
    # lleva ``alters_data`` (``:996-997``)— y ese valor vive en el motor, que
    # un ``Context`` suelto no tiene. Sin la guarda, las dos ramas escapan
    # como ``AttributeError: 'NoneType' object has no attribute 'engine'``,
    # que no dice nada del descriptor que lo causó.
    try:
        return Variable(path).resolve(context)
    except (VariableDoesNotExist, AttributeError) as e:
        raise InvalidReportTemplate(
            _("Cannot resolve list path %r in report template") % path
        ) from e


def _condition_holds(node, context):
    """``when="path"`` — si el nodo entra al documento o no.

    **Fail-closed a propósito.** Una condición que no resuelve NO se lee como
    falsa: se levanta. Leerla como falsa haría desaparecer del papel un dato
    por un typo en el ``path``, y el documento saldría bien formado y
    equivocado — el sub-patrón D de ``metrica-decide-la-conclusion.md``
    aplicado a la plantilla.

    Toma un **path**, no una expresión: es la misma contención por gramática
    que DTL da a ``in=`` y a ``{{ }}``, y la razón por la que el descriptor no
    usa el compilador de la fuente (DEC-FW-05). El cálculo vive en el modelo.
    """
    path = node.get('when')
    if path is None:
        return True
    return bool(_resolve_path(path, Context(context)))


def _loop_state(index, size):
    """Lo que ``t-foreach`` expone y ``forloop`` de DTL sólo da dentro de un texto.

    ``forloop`` es del ``{% for %}`` de una plantilla; aquí el bucle lo recorre
    el intérprete sobre el árbol, así que su estado lo construye él. La paridad
    va incluida porque ``forloop`` **no** la expone —se construye con el filtro
    ``divisibleby``— y en un descriptor se pide a menudo (fila cebreada).
    """
    return {
        'index': index,          # base 0, como ``_index`` de la fuente
        'number': index + 1,     # base 1, para el texto que ve el lector
        'first': index == 0,
        'last': index == size - 1,
        'even': index % 2 == 0,
        'odd': index % 2 == 1,
        'size': size,
    }


def _interpret_children(node, context, resolve_key=None):
    """Recorre los hijos del nodo y produce su dict.

    El contexto se copia por nodo: un ``<set>`` liga un nombre para sus
    **hermanos siguientes** y no se escapa de la sección que lo contiene. Sin
    esa copia, dos secciones que usen el mismo nombre se pisarían según el
    orden del árbol.
    """
    result = {}
    scope = dict(context)
    for child in node:
        if not isinstance(child.tag, str):
            # comentarios / processing-instructions del combinador
            continue
        if not _condition_holds(child, scope):
            continue
        if child.tag == 'call':
            _interpret_call(child, scope, result, resolve_key)
            continue
        name = child.get('name')
        if not name:
            raise InvalidReportTemplate(
                _("Element <%s> without 'name' in report template") % child.tag)
        if child.tag == 'field':
            result[name] = _render_text(child.text, scope)
        elif child.tag == 'set':
            value = child.get('value')
            if not value:
                raise InvalidReportTemplate(
                    _("Element <set name=%r> without 'value' path") % name)
            scope[name] = _resolve_path(value, Context(scope))
        elif child.tag == 'section':
            result[name] = _interpret_children(child, scope, resolve_key)
        elif child.tag == 'list':
            path = child.get('in')
            if not path:
                raise InvalidReportTemplate(
                    _("Element <list name=%r> without 'in' path") % name)
            rows = list(_resolve_path(path, Context(scope)))
            items = []
            for index, item in enumerate(rows):
                item_scope = dict(scope, item=item,
                                  loop=_loop_state(index, len(rows)))
                items.append(_interpret_children(child, item_scope, resolve_key))
            result[name] = items
        else:
            raise InvalidReportTemplate(
                _("Unknown element <%s> in report template") % child.tag)
    return result


def _interpret_call(node, context, result, resolve_key):
    """``<call key="…"/>`` — injerta los hijos de otro descriptor.

    El equivalente de ``{% include %}``, con la diferencia que la medición
    dejó clara: DTL resuelve contra un *loader*, y aquí el loader es
    ``ir.ui.view`` por su ``key``. Se recibe por parámetro para que el
    intérprete no dependa de la base y se pueda medir suelto.

    **Sin resolutor se levanta, no se ignora.** Ignorarlo produciría un
    documento al que le falta un bloque entero, en silencio.
    """
    key = node.get('key')
    if not key:
        raise InvalidReportTemplate(
            _("Element <call> without 'key' in report template"))
    if resolve_key is None:
        raise InvalidReportTemplate(
            _("Element <call key=%r> needs a resolve_key to resolve it") % key)
    called = resolve_key(key)
    if called is None:
        raise InvalidReportTemplate(
            _("Report template %r called by <call> does not exist") % key)
    if called.tag != 'descriptor':
        raise InvalidReportTemplate(
            _("Report template %r called by <call> is not a <descriptor>") % key)
    result.update(_interpret_children(called, context, resolve_key))


def interpret_descriptor(arch, context, resolve_key=None):
    """Interpreta el arch combinado de una vista hacia el descriptor JSON.

    :param arch: elemento raíz (lxml) — normalmente el resultado de
        ``IrUiView._get_combined_arch()``
    :param context: variables visibles para las expresiones DTL; el reporte
        pasa ``docs`` (el recordset) y el contexto del render
    :param resolve_key: callable ``key -> elemento`` que resuelve un
        ``<call>``; sin él, un ``<call>`` levanta en vez de omitirse
    :return: dict listo para ``json.dumps`` → stdin del helper
    :raises InvalidReportTemplate: si el arch sale del vocabulario
    """
    if arch.tag != 'descriptor':
        raise InvalidReportTemplate(
            _("Report template root must be <descriptor>, got <%s>") % arch.tag)
    return _interpret_children(arch, context, resolve_key)
