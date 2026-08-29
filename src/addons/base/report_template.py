"""Plantilla-descriptor de reportes — el intérprete sobre ``ir.ui.view``.

**Forma propia, declarada como tal.** La referencia no cubre este caso: allá
la plantilla del reporte emite HTML (QWeb) y ``wkhtmltopdf`` lo convierte,
así que la plantilla puede ser HTML libre. Aquí el conversor es el helper de
``tools/pdf/`` y **no acepta HTML** — consume un descriptor JSON. Lo que este
módulo define es el punto medio que preserva las dos propiedades que la
directiva del ejecutor pide:

- *lo que se lee* es un **registro en BD** (``ir.ui.view``, ``type='qweb'``,
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
                                   cada elemento como ``item``
===============================  =============================================

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


def _interpret_children(node, context):
    result = {}
    for child in node:
        if not isinstance(child.tag, str):
            # comentarios / processing-instructions del combinador
            continue
        name = child.get('name')
        if not name:
            raise InvalidReportTemplate(
                _("Element <%s> without 'name' in report template") % child.tag)
        if child.tag == 'field':
            result[name] = _render_text(child.text, context)
        elif child.tag == 'section':
            result[name] = _interpret_children(child, context)
        elif child.tag == 'list':
            path = child.get('in')
            if not path:
                raise InvalidReportTemplate(
                    _("Element <list name=%r> without 'in' path") % name)
            items = []
            for item in _resolve_path(path, Context(context)):
                item_context = dict(context, item=item)
                items.append(_interpret_children(child, item_context))
            result[name] = items
        else:
            raise InvalidReportTemplate(
                _("Unknown element <%s> in report template") % child.tag)
    return result


def interpret_descriptor(arch, context):
    """Interpreta el arch combinado de una vista hacia el descriptor JSON.

    :param arch: elemento raíz (lxml) — normalmente el resultado de
        ``IrUiView._get_combined_arch()``
    :param context: variables visibles para las expresiones DTL; el reporte
        pasa ``docs`` (el recordset) y el contexto del render
    :return: dict listo para ``json.dumps`` → stdin del helper
    :raises InvalidReportTemplate: si el arch sale del vocabulario
    """
    if arch.tag != 'descriptor':
        raise InvalidReportTemplate(
            _("Report template root must be <descriptor>, got <%s>") % arch.tag)
    return _interpret_children(arch, context)
