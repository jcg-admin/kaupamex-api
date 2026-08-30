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
import io

from django.template import Context, Engine, Variable, VariableDoesNotExist
from django.utils.html import conditional_escape, escape
from PIL import Image, ImageDraw, ImageFont

from addons.base.models import ir_field_converters
from tools.translate import _

#: Motor DTL propio del intérprete. ``autoescape=False`` es parte del
#: contrato (ver el docstring del módulo); no se reusa el engine global de
#: settings para no heredar su autoescape ni sus context processors.
_ENGINE = Engine(autoescape=False)


#: Tope de anidamiento de ``<call>``. Es el de la fuente, verbatim:
#: ``if len(stack) > 50: raise RecursionError('Qweb template infinite
#: recursion')`` (``odoo19c: odoo/addons/base/models/ir_qweb.py:766-768``).
#:
#: El mecanismo es un **tope de profundidad**, no un conjunto de claves ya
#: visitadas, y la diferencia es deliberada allá y aquí: un conjunto de
#: visitados rechazaría llamar dos veces al mismo bloque en puntos distintos
#: del documento —legítimo— mientras que el tope sólo rechaza el anidamiento
#: que no termina.
MAX_CALL_DEPTH = 50


class InvalidReportTemplate(ValueError):
    """El arch combinado no respeta el vocabulario de la plantilla."""


def converter_for(widget):
    """``widget`` → la clase de ``ir.qweb.field.*`` que lo sabe formatear.

    Es el despacho de la fuente, verbatim en su forma:
    ``model = 'ir.qweb.field.' + field_options['type']`` y
    ``converter = self.env[model] if model in self.env else
    self.env['ir.qweb.field']`` (``odoo19c: ir_qweb.py:2759-2760`` y
    ``:2783-2784``). **Cae a la base cuando el modelo no existe** — no levanta;
    se porta esa elección, que hace que un ``widget`` desconocido produzca el
    valor escapado en vez de un documento roto.

    Resuelve por el ``_name`` declarado en cada clase, no por el nombre de la
    clase de Python: el nombre punteado es la identidad de la entidad en el
    porte (pieza 4 de DEC-FW-05, :ref:`h-api-932`).

    **Por qué no usa** ``orm.registry.model_by_name``: los 21 conversores son
    ``Meta.abstract = True``, y Django no emite ``class_prepared`` para un
    modelo abstracto — medido, ``model_by_name('ir.qweb.field')`` devuelve
    ``None``. El mapa se construye recorriendo las subclases, que es donde el
    dato sí está.
    """
    return _converters_by_name().get(
        'ir.qweb.field.' + widget, ir_field_converters.IrFieldConverter)


def _converters_by_name(_cache={}):
    # Se construye una vez y se reusa: las subclases se declaran al importar
    # el módulo y no cambian después.
    if not _cache:
        pending = [ir_field_converters.IrFieldConverter]
        while pending:
            klass = pending.pop()
            name = getattr(klass, '_name', None)
            if name:
                _cache[name] = klass
            pending.extend(klass.__subclasses__())
    return _cache


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


def _interpret_field(node, scope, widget_options=None):
    """``<field>`` — su texto DTL, o el valor pasado por un conversor.

    Dos formas, y la segunda es la que la tarea #197 cablea:

    - **sin** ``widget``: el texto del nodo se renderiza con DTL y sale crudo.
      Es el camino de siempre y **no cambia** — el control que lo fija vive en
      ``test_who_formats_on_the_paper_path.py``.
    - **con** ``widget``: el ``value`` se resuelve como *path* y lo formatea el
      conversor de ``ir.qweb.field.*`` que ese widget nombre.

    El ``widget`` exige ``value`` porque lo que se formatea es un **valor**, no
    un texto ya renderizado: pasarle la salida de DTL daría una cadena a un
    conversor que espera un ``Decimal``, y el error saldría lejos de su causa.

    :raises InvalidReportTemplate: ``widget`` sin ``value``.
    """
    widget = node.get('widget')
    if not widget:
        return _render_text(node.text, scope)
    path = node.get('value')
    if not path:
        raise InvalidReportTemplate(
            _("Element <field name=%r> with widget %r needs a 'value' path")
            % (node.get('name'), widget))
    value = _resolve_path(path, Context(scope))
    options = (widget_options or {}).get(widget)
    return converter_for(widget).value_to_html(value, options)


def _interpret_children(node, context, resolve_key=None, depth=0,
                        widget_options=None):
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
            _interpret_call(child, scope, result, resolve_key, depth,
                            widget_options)
            continue
        name = child.get('name')
        if not name:
            raise InvalidReportTemplate(
                _("Element <%s> without 'name' in report template") % child.tag)
        if child.tag == 'field':
            result[name] = _interpret_field(child, scope, widget_options)
        elif child.tag == 'set':
            value = child.get('value')
            if not value:
                raise InvalidReportTemplate(
                    _("Element <set name=%r> without 'value' path") % name)
            scope[name] = _resolve_path(value, Context(scope))
        elif child.tag == 'section':
            result[name] = _interpret_children(child, scope, resolve_key, depth,
                                               widget_options)
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
                items.append(
                    _interpret_children(child, item_scope, resolve_key, depth,
                                        widget_options))
            result[name] = items
        else:
            raise InvalidReportTemplate(
                _("Unknown element <%s> in report template") % child.tag)
    return result


def _interpret_call(node, context, result, resolve_key, depth=0,
                    widget_options=None):
    """``<call key="…"/>`` — injerta los hijos de otro descriptor.

    El equivalente de ``{% include %}``, con la diferencia que la medición
    dejó clara: DTL resuelve contra un *loader*, y aquí el loader es
    ``ir.ui.view`` por su ``key``. Se recibe por parámetro para que el
    intérprete no dependa de la base y se pueda medir suelto.

    **Sin resolutor se levanta, no se ignora.** Ignorarlo produciría un
    documento al que le falta un bloque entero, en silencio.

    ``depth`` es el anidamiento de llamadas, no el del árbol: una ``section``
    o una ``list`` no lo incrementan porque viven dentro del mismo descriptor.
    Es el mismo criterio de la fuente, cuya pila cuenta un cuadro por
    *plantilla* renderizada, no por nodo recorrido.
    """
    if depth >= MAX_CALL_DEPTH:
        raise RecursionError(
            'Report template infinite recursion (depth %d)' % MAX_CALL_DEPTH)
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
    result.update(_interpret_children(called, context, resolve_key, depth + 1,
                                      widget_options))


def interpret_descriptor(arch, context, resolve_key=None, widget_options=None):
    """Interpreta el arch combinado de una vista hacia el descriptor JSON.

    :param arch: elemento raíz (lxml) — normalmente el resultado de
        ``IrUiView._get_combined_arch()``
    :param context: variables visibles para las expresiones DTL; el reporte
        pasa ``docs`` (el recordset) y el contexto del render
    :param resolve_key: callable ``key -> elemento`` que resuelve un
        ``<call>``; sin él, un ``<call>`` levanta en vez de omitirse
    :param widget_options: ``{widget: options}`` — lo que cada conversor de
        ``ir.qweb.field.*`` necesita para formatear (p. ej.
        ``{'monetary': {'display_currency': moneda}}``). Sólo lo consume un
        ``<field widget="…" value="…"/>``; un ``<field>`` sin ``widget`` sigue
        saliendo por DTL.
    :return: dict listo para ``json.dumps`` → stdin del helper
    :raises InvalidReportTemplate: si el arch sale del vocabulario
    :raises RecursionError: si el anidamiento de ``<call>`` pasa de
        ``MAX_CALL_DEPTH`` — dos descriptores que se llaman entre sí
    """
    if arch.tag != 'descriptor':
        raise InvalidReportTemplate(
            _("Report template root must be <descriptor>, got <%s>") % arch.tag)
    return _interpret_children(arch, context, resolve_key,
                               widget_options=widget_options)


# --- Serializadores del descriptor -----------------------------------------
#
# La fuente no los tiene, y la razón es que allá no hacen falta: su intermedio
# YA es HTML —``ir.ui.view._render_template`` devuelve marcado y
# ``_render_template`` lo codifica (``odoo19c: ir_actions_report.py:789``)—,
# así que ``_render_qweb_html`` no serializa nada, sólo devuelve lo compuesto.
# Aquí el intermedio es el descriptor, que es lo que el motor de libharu dibuja
# (ADR-017), y por eso los dos formatos que no son papel necesitan un paso más.
#
# Es la categoría CONSTRUYE del criterio de las dos categorías: el stack trae
# las primitivas —``conditional_escape`` para no re-escapar lo que un conversor
# ya marcó seguro, y el propio recorrido del dict— y lo que falta es el mapeo
# del vocabulario ``<descriptor>`` a etiquetas y a líneas, que es nuestro.


def _bodies_and_ids(rendered):
    """Los cuerpos y sus ids, venga el intermedio o un descriptor suelto.

    Acepta las dos formas por la misma razón que ``_prepare_html``: el
    intermedio de ``_render_template`` es ``{'bodies': …, 'html_ids': …}``, y
    un llamador que interprete un arch por su cuenta tiene un dict pelado.
    """
    if isinstance(rendered, dict) and 'bodies' in rendered:
        bodies = list(rendered['bodies'])
        ids = list(rendered.get('html_ids') or [None] * len(bodies))
        return bodies, ids
    return [rendered], [None]


def _html_block(body, level=1):
    """Un bloque del descriptor como marcado, recursivo por su forma.

    Las tres formas del descriptor tienen las tres su etiqueta, y el nombre
    viaja en ``data-name`` en vez de en el texto: quien lea el HTML puede
    volver al descriptor sin adivinar dónde acaba la etiqueta y empieza el
    valor, que es la misma razón por la que la fuente marca ``data-oe-id``
    en vez de escribir el id dentro del cuerpo.
    """
    indent = '  ' * level
    parts = []
    for name, value in body.items():
        attribute = escape(name)
        if isinstance(value, dict):
            parts.append(f'{indent}<div class="section" data-name="{attribute}">')
            parts.append(_html_block(value, level + 1))
            parts.append(f'{indent}</div>')
        elif isinstance(value, list):
            parts.append(f'{indent}<div class="list" data-name="{attribute}">')
            for item in value:
                parts.append(f'{indent}  <div class="item">')
                parts.append(_html_block(item, level + 2))
                parts.append(f'{indent}  </div>')
            parts.append(f'{indent}</div>')
        else:
            # ``conditional_escape`` y no ``escape``: el valor de un ``<field
            # widget="…">`` sale del conversor ya marcado seguro —la familia
            # ``ir.qweb.field.*`` usa ``mark_safe`` donde emite etiquetas— y
            # volver a escaparlo publicaría ``&lt;img …&gt;`` en el papel. El
            # de un ``<field>`` sin widget sale de DTL con ``autoescape=False``
            # y sí hay que escaparlo.
            parts.append(f'{indent}<div class="field" data-name="{attribute}">'
                          f'{conditional_escape(value)}</div>')
    return '\n'.join(parts)


def descriptor_to_html(rendered, model=None):
    """El descriptor como documento HTML — lo que ``report_type='html'`` promete.

    :param rendered: el intermedio de ``_render_template``, o un descriptor.
    :param model: el modelo del reporte, para ``data-oe-model``.
    :returns: ``bytes``, como la fuente (``:774`` declara ``:rtype: bytes``).

    **El par ``data-oe-model``/``data-oe-id`` es el contrato**, no adorno: es
    lo que la fuente busca al partir el documento por registro
    (``_prepare_html``, ``:383-463``) y lo que permite guardar un adjunto por
    registro. Aquí el reparto ya viene hecho —un cuerpo por registro— y el par
    se escribe igual, para que el HTML diga lo mismo que el descriptor.
    """
    bodies, ids = _bodies_and_ids(rendered)
    model_attribute = f' data-oe-model="{escape(model)}"' if model else ''
    parts = ['<html><body>']
    for body, res_id in zip(bodies, ids):
        id_attribute = '' if res_id is None else f' data-oe-id="{escape(res_id)}"'
        parts.append(f'<div class="article"{model_attribute}{id_attribute}>')
        bloque = _html_block(body)
        if bloque:
            parts.append(bloque)
        parts.append('</div>')
    parts.append('</body></html>')
    return '\n'.join(parts).encode()


def _text_block(body, level=0):
    """Un bloque del descriptor como líneas indentadas."""
    indent = '  ' * level
    lines = []
    for name, value in body.items():
        if isinstance(value, dict):
            lines.append(f'{indent}{name}:')
            lines.extend(_text_block(value, level + 1))
        elif isinstance(value, list):
            lines.append(f'{indent}{name}:')
            for item in value:
                rows = _text_block(item, level + 2)
                if rows:
                    # El guion marca dónde empieza cada elemento; sin él, dos
                    # elementos de dos campos se leen como uno de cuatro.
                    rows[0] = f'{indent}  - {rows[0].lstrip()}'
                lines.extend(rows)
        else:
            lines.append(f'{indent}{name}: {value}')
    return lines


def descriptor_to_text(rendered):
    """El descriptor como texto plano — lo que ``report_type='text'`` promete.

    :returns: ``bytes``, por el mismo contrato que :func:`descriptor_to_html`.

    Cada registro abre con una regla que lleva su id, que es el equivalente en
    texto del ``data-oe-id`` del marcado: sin ella, dos registros seguidos se
    leen como un documento de campos repetidos.

    *Ciega a:* el valor que un conversor marcó como seguro llega aquí con sus
    etiquetas — ``ir.qweb.field.html`` devuelve marcado por contrato, y en
    texto plano eso se lee tal cual. Despojarlo exige decidir qué se pierde
    (un ``<br>`` es un salto de línea; un ``<img>`` no tiene equivalente), y esa
    decisión es del declarante que pida el formato, no de este serializador.
    """
    bodies, ids = _bodies_and_ids(rendered)
    lines = []
    for body, res_id in zip(bodies, ids):
        if res_id is not None:
            lines.append(f'--- {res_id} ---')
        lines.extend(_text_block(body))
    return '\n'.join(lines).encode()


#: Formatos de imagen que el raster emite, con el nombre que Pillow les da.
#: Son exactamente los dos que la firma de la fuente declara
#: (``image_format: typing.Literal['jpg', 'png']``, ``odoo19c:
#: ir_actions_report.py:471``); no se añade ninguno porque el contrato es suyo.
IMAGE_FORMATS = {'jpg': 'JPEG', 'png': 'PNG'}

#: Métricas del lienzo, en píxeles. Son de este renderizador y no de la
#: fuente: allá la maquetación la resuelve el CSS de la página.
IMAGE_MARGIN = 8
IMAGE_FONT_SIZE = 13
IMAGE_LINE_HEIGHT = 17


class UnknownImageFormat(Exception):
    """El formato pedido no está en :data:`IMAGE_FORMATS`.

    Ruidoso a propósito: devolver un PNG donde se pidió otra cosa es el verde
    que no discrimina — quien guarde los bytes con la extensión pedida sirve
    un archivo cuyo contenido no coincide con su tipo declarado.
    """


def descriptor_to_image(rendered, width, height, image_format='jpg'):
    """El descriptor como imagen raster — lo que ``_run_wkhtmltoimage`` entrega.

    :param rendered: el intermedio de ``_render_template``, o un descriptor.
    :param width: ancho en píxeles.
    :param height: alto en píxeles.
    :param image_format: ``'jpg'`` o ``'png'``, como la firma de la fuente.
    :returns: ``bytes`` de la imagen.
    :raises UnknownImageFormat: si el formato no está en :data:`IMAGE_FORMATS`.

    **Divergencia de mecanismo, con su razón y su medición.** La fuente
    rasteriza con ``wkhtmltoimage``, que maqueta una página HTML con QtWebKit
    y la fotografía. Este árbol **no usa ni quiere** ese binario ni ese motor
    (directiva del ejecutor 2026-08-30), y resulta que tampoco los necesita:
    el cuerpo que aquí viaja **es el descriptor** —no una página— y el
    descriptor ya lleva todo lo que la imagen debe mostrar. Lo que falta es
    dibujarlo, y eso lo trae el stack: Pillow ya está declarado en
    ``pyproject.toml`` y ``tools.barcode`` ya lo usa para su raster.

    **Dibuja las mismas líneas que** :func:`descriptor_to_text`, y no por
    comodidad: es lo que garantiza que los tres formatos digan lo mismo del
    mismo descriptor. Inventar aquí un segundo vocabulario de maquetación
    dejaría al raster contando otra historia que el texto y el marcado, sin
    que nada lo delatara.

    *Métrica:* los píxeles del lienzo emitido, leídos con Pillow.
    *Ciega a:* la calidad tipográfica del resultado —usa la fuente por defecto
    de Pillow, sin medir anchos de glifo— y a lo que no cabe: una línea más
    allá del borde inferior **no se dibuja y no avisa**. Un descriptor que no
    quepa entrega una imagen cierta y parcial, no una imagen falsa.
    """
    pillow_format = IMAGE_FORMATS.get(str(image_format).lower())
    if pillow_format is None:
        raise UnknownImageFormat(
            _("Unknown image format %(asked)s; expected one of %(known)s") % {
                'asked': image_format, 'known': ', '.join(sorted(IMAGE_FORMATS))})

    bodies, ids = _bodies_and_ids(rendered)
    lines = []
    for body, res_id in zip(bodies, ids):
        if res_id is not None:
            lines.append(f'--- {res_id} ---')
        lines.extend(_text_block(body))

    canvas = Image.new('RGB', (max(1, int(width)), max(1, int(height))), 'white')
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=IMAGE_FONT_SIZE)
    top = IMAGE_MARGIN
    for line in lines:
        if top + IMAGE_LINE_HEIGHT > canvas.height - IMAGE_MARGIN:
            break
        draw.text((IMAGE_MARGIN, top), line, fill='black', font=font)
        top += IMAGE_LINE_HEIGHT

    output = io.BytesIO()
    canvas.save(output, format=pillow_format)
    return output.getvalue()
