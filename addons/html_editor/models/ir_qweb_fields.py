"""Los conversores en la dirección de VUELTA — del HTML editado al valor.

Adaptación de ``odoo19c: addons/html_editor/models/ir_qweb_fields.py``
(716 líneas, LGPL-3 — copia + adaptación con atribución, DEC-KX-03).

Docstring de la fuente, verbatim: *"Web_editor-context rendering needs to add
some metadata to rendered and allow to edit fields, as well as render a few
fields differently. Also, adds methods to convert values back to Odoo
models."*

**34 símbolos en la fuente, 34 portados.** Seis de ellos —los que extienden
el compilador de nodos— quedan sin consumidor por una divergencia
arquitectónica ya ratificada, no por un bloqueo: ver «Los seis sin
consumidor».

Las dos mitades del archivo
===========================

1. **``IrQweb``** — cuatro directivas de *snippet* y dos enganches del
   compilador. Es la mitad portada y sin consumidor.
2. **Los trece ``ir.qweb.field.*``** — la dirección **de vuelta**:
   ``from_html`` toma el nodo que la persona acaba de editar y produce el
   valor del campo, y ``attributes`` añade al nodo las marcas ``data-oe-*``
   que el editor necesita para saber qué está editando. ``base`` porta la
   ida (``value_to_html``); esto es la vuelta, y sin ella el editor puede
   pintar y no puede guardar.

Qué pieza de este stack cubre cada delegación de la fuente
==========================================================

===============================  =====================================
Fuente delega en                 Aquí lo cubre
===============================  =====================================
``lxml`` (``html``/``etree``)    **lxml** — el mismo, para leer el nodo
                                 editado y volcar sus hijos
``babel`` (formato por locale)   **django + babel** — ``babel`` es
                                 dependencia declarada del proyecto;
                                 el ``res.lang`` sale de
                                 ``tools.misc.get_lang``
``PIL`` (validar la imagen)      **Pillow** — ``Image.open`` + ``load``
``requests`` (imagen remota)     **requests** — el mismo
``werkzeug.urls.url_parse``      **cpython** — ``urllib.parse``. El
                                 inventario del stack excluye Werkzeug
                                 (servimos con **gunicorn**), y
                                 ``urlparse`` da los mismos ``path`` y
                                 ``query``
``odoo.tools.json.scriptsafe``   **portado** en ``src/tools/json.py``
``odoo.tools.misc.file_open``    **portado** en ``src/tools/misc.py``
                                 (con su confinamiento)
``odoo.tools.misc.get_lang``     **portado** en ``src/tools/misc.py``
``odoo.tools.posix_to_ldml`` /   **construidos aquí** — ver la
``babel_locale_parse``           divergencia 2
``self.env[...]``                ``orm.registry.model_by_name``
``self.env.user``                ``orm.environments.get_current_user``
===============================  =====================================

Los seis sin consumidor — la divergencia, no un bloqueo
=======================================================

``_compile_node``, ``_get_preload_attribute_xmlids``,
``_compile_directive_snippet``, ``_compile_directive_snippet_call``,
``_compile_directive_install`` y ``_compile_directive_placeholder``
**extienden el compilador de nodos de plantilla**, que este árbol **no
porta por decisión ratificada**:
``base.ir_template_expressions`` declara que el HTML lo emite React y que el
backend entrega datos por DRF, así que un emisor de marcado en servidor no
tendría a quién servir. Lo medido: de esa familia, ``base`` porta
``_directives_eval_order`` y no porta ``_compile_node`` ni ningún
``_compile_directive_*``.

**Se portan igual, y con su nombre.** Los seis se instalan con su firma y su
cuerpo, encadenados sobre ``IrTemplateExpressions``, porque
``porte-completo-no-parcial`` no admite omitir un símbolo por conveniencia:
lo que se declara es su **destino**, no su ausencia. Su ``super()`` —
``_compile_node`` y ``_append_text`` de la fuente — no existe aquí y no va a
existir, así que nadie los invoca.

Portarlos completos **no promete un consumidor**: deja el API completo. Quien
consume este API es React, por el contrato que ``drf-spectacular`` publica; lo
que estos seis emiten es marcado, que no viaja por ese contrato.

**No hay sucesor, y ésa es la decisión.** Portar el compilador de nodos sobre
``base.IrTemplateExpressions`` sería construir un emisor de HTML que ningún
consumidor de este producto lee. Si la premisa arquitectónica cambiara —si
algún día el backend renderizara HTML— la que se revisa es la decisión de
``ir_template_expressions.py``, no este archivo.

Los dos que **sí** enganchan hoy:

- ``_directives_eval_order`` — ``base`` lo declara, así que la inserción
  posicional de las cuatro directivas nuevas se hace con ``wrap_method``, que
  entrega la lista previa en la mano. Es exactamente lo que la fuente escribe.
- ``_get_template_cache_keys`` — ``base`` no lo declara todavía (igual que
  ``_prepare_environment``, que ``http_routing`` instala fresco); se instala
  con el ``combine`` acumulativo, así que encadenará solo el día que exista.

Divergencia 1 — ``_inherit`` de trece modelos abstractos
========================================================

La fuente declara trece clases ``_inherit = ['ir.qweb.field.*']``. ``base``
declara esas mismas clases como ``IrFieldConverter*`` abstractas con sus
métodos en ``@classmethod``. Aquí cada bloque se cuelga con ``chain_method``
sobre la clase de ``base``, envuelto en ``classmethod`` para conservar el
descriptor — que es la forma que ``orm.method_chain`` documenta.

``IrQwebFieldRelative`` e ``IrQwebFieldQweb`` de la fuente **no declaran
ningún método**: existen sólo para que el modelo esté registrado. Aquí no
tienen nada que colgar y por eso no aparece un ``apply_*`` suyo; sus
contrapartes ``IrFieldConverterRelative`` e ``IrFieldConverterTemplate`` ya
existen en ``base``. El comentario de la fuente —*"get formatting from
ir.qweb.field.relative but edition/save from datetime"*— se conserva abajo,
porque describe una decisión, no una implementación.

Divergencia 2 — ``posix_to_ldml`` y ``babel_locale_parse`` se construyen aquí
=============================================================================

Su hogar es ``odoo/tools/misc.py`` = ``src/tools/misc.py``, que está fuera de
los archivos de este puerto. Se portan aquí como privados, con el nombre de la
fuente precedido de guion bajo para que se lea que su sitio definitivo es
otro, y con la tabla ``POSIX_TO_LDML`` verbatim.

**Sucesor nombrado:** mover ``POSIX_TO_LDML``, ``posix_to_ldml`` y
``babel_locale_parse`` a ``src/tools/misc.py`` —donde la referencia los
declara— y que este archivo los importe de ahí. Se reporta al orquestador.

Divergencia 3 — lo que ``fields`` de este árbol no declara
===========================================================

Cuatro atributos de campo que la fuente lee no existen en
``orm.fields_textual.Html`` (su docstring declara que va *"sin saneo (capa
UI)"*): ``sanitize``, ``sanitize_overridable``, ``sanitize_attributes`` y
``sanitize_form``. Y ``placeholder`` no es atributo de campo en Django.

Se leen todos con ``getattr(field, ..., <default de la fuente>)``, así que el
cuerpo de la fuente se conserva **entero** y su rama se enciende sola el día
que el sucesor —el mismo de ``html_field_history_mixin.py``— declare los
atributos. Ninguna rama se borra.
"""
import base64
import io
import json
import logging
import os
import re
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import babel
import babel.dates
import pytz
import requests
from addons.base.models.ir_field_converters import (
    IrFieldConverter,
    IrFieldConverterContact,
    IrFieldConverterDate,
    IrFieldConverterDatetime,
    IrFieldConverterDuration,
    IrFieldConverterFloat,
    IrFieldConverterHtml,
    IrFieldConverterImage,
    IrFieldConverterInteger,
    IrFieldConverterMany2one,
    IrFieldConverterMonetary,
    IrFieldConverterSelection,
    IrFieldConverterText,
)
from django.utils import timezone
from lxml import etree, html
from markupsafe import Markup, escape_silent
from orm.environments import get_current_user
from orm.method_chain import (chain_method, extend_list, merge_dict,
                              wrap_method)
from orm.registry import model_by_name
from PIL import Image as I
from tools.json import scriptsafe as json_safe
from tools.misc import file_open, get_lang

from addons.base.models.ir_template_expressions import IrTemplateExpressions

REMOTE_CONNECTION_TIMEOUT = 2.5

logger = logging.getLogger(__name__)


# ------------------------------------------------------
# Lo que ``src/tools/misc.py`` todavía no declara (divergencia 2)
# ------------------------------------------------------

#: ≙ ``POSIX_TO_LDML`` (``odoo19c: odoo/tools/misc.py:588-613``), verbatim.
POSIX_TO_LDML = {
    'a': 'E',
    'A': 'EEEE',
    'b': 'MMM',
    'B': 'MMMM',
    # 'c': '',
    'd': 'dd',
    '-d': 'd',
    'H': 'HH',
    'I': 'hh',
    'j': 'DDD',
    'm': 'MM',
    '-m': 'M',
    'M': 'mm',
    'p': 'a',
    'S': 'ss',
    'U': 'w',
    'w': 'e',
    'W': 'w',
    'y': 'yy',
    'Y': 'yyyy',
    # ver los comentarios de arriba: format_datetime de babel asume UTC para
    # los datetime ingenuos
    # 'z': 'Z',
    # 'Z': 'z',
}


def _posix_to_ldml(fmt, locale):
    """≙ ``posix_to_ldml`` (``odoo19c: odoo/tools/misc.py:616-666``), verbatim.

    Convierte un patrón posix/strftime en un patrón LDML de fecha.

    :param fmt: patrón strftime C89/C90 no extendido
    :param locale: locale de babel, para las conversiones dependientes de
        idioma (``%x`` y ``%X``)
    :return: unicode
    """
    buf = []
    pc = False
    minus = False
    quoted = []

    for c in fmt:
        # los patrones LDML usan letras, así que las letras van entrecomilladas
        if not pc and c.isalpha():
            quoted.append(c if c != "'" else "''")
            continue
        if quoted:
            buf.append("'")
            buf.append(''.join(quoted))
            buf.append("'")
            quoted = []

        if pc:
            if c == '%':  # por ciento escapado
                buf.append('%')
            elif c == 'x':  # formato de fecha; el corto parece coincidir
                buf.append(locale.date_formats['short'].pattern)
            elif c == 'X':  # formato de hora con segundos; el corto no los trae
                buf.append(locale.time_formats['medium'].pattern)
            elif c == '-':
                minus = True
                continue
            else:  # se busca el carácter en la tabla estática
                if minus:
                    c = '-' + c
                    minus = False
                buf.append(POSIX_TO_LDML[c])
            pc = False
        elif c == '%':
            pc = True
        else:
            buf.append(c)

    # se vuelca lo que quede en el buffer entrecomillado
    if quoted:
        buf.append("'")
        buf.append(''.join(quoted))
        buf.append("'")

    return ''.join(buf)


def _babel_locale_parse(lang_code):
    """≙ ``babel_locale_parse`` (``odoo19c: odoo/tools/misc.py:1330-1339``)."""
    if lang_code:
        try:
            return babel.Locale.parse(lang_code)
        except Exception:  # noqa: BLE001
            # silent OK because un codigo de idioma invalido no es un error del
            # editor: la fuente cae al idioma por defecto en el mismo punto
            # (``odoo19c: odoo/tools/misc.py:1334-1336``) para que un dato de
            # usuario mal formado no tumbe el renderizado de la plantilla.
            pass
    try:
        return babel.Locale.default()
    except Exception:  # noqa: BLE001
        # silent OK because el ultimo recurso de la fuente es el mismo literal:
        # sin locale por defecto en el sistema, ``en_US`` siempre parsea.
        return babel.Locale.parse("en_US")


def _user_lang():
    """≙ ``self.user_lang()`` de la referencia — el ``res.lang`` del usuario.

    ``tools.misc.get_lang`` resuelve en el orden de la fuente (código pedido,
    contexto, empresa, ``en_US``), así que llamarlo sin argumento es
    exactamente lo que la fuente hace con el idioma del usuario en el entorno.
    """
    user = get_current_user()
    return get_lang(getattr(user, 'lang', None) if user is not None else None)


def _base_lang_of(record):
    """≙ ``record._get_base_lang()`` — el idioma base del registro.

    La referencia lo declara en ``BaseModel`` con ``return 'en_US'`` y lo
    redefine ``website`` (el idioma por defecto del sitio). Este árbol no lo
    declara todavía: se consulta si el modelo lo trae y si no se usa el mismo
    valor que la fuente pone por defecto.
    """
    getter = getattr(record, '_get_base_lang', None)
    return getter() if callable(getter) else 'en_US'


def _field_domain(field):
    """≙ ``field._description_domain(self.env)`` — el dominio del relacional.

    La fuente descarta el dominio cuando es una cadena (una expresión que sólo
    su ORM sabe evaluar) y devuelve la lista tal cual cuando no lo es. Aquí un
    ``ForeignKey`` de Django declara su restricción en ``limit_choices_to``, y
    ese es el dato equivalente; cuando no lo declara, la lista vacía es lo que
    la fuente produce para el mismo caso.
    """
    domain = getattr(field, 'limit_choices_to', None)
    if not domain or isinstance(domain, str):
        return []
    return domain


def _converter_for(model_name):
    """El conversor ``ir.qweb.field.*`` registrado, o el base."""
    return model_by_name(model_name) or model_by_name('ir.qweb.field')


# ------------------------------------------------------
# IrQweb — las directivas de snippet (ver «Los seis sin consumidor»)
# ------------------------------------------------------


def _compile_node(self, el, compile_context, level):
    """≙ ``_compile_node`` (``odoo19c: :42-77``).

    Marca el nodo raíz de un *snippet* con ``data-snippet`` y ``data-name``, y
    delega. **Divergencia de forma:** la fuente termina con
    ``return super()._compile_node(...)`` en las dos ramas; aquí devuelve
    ``None`` siempre y ``chain_method`` releva en el eslabón previo, que es el
    mismo efecto con el mecanismo de este árbol. Sin eslabón previo —el estado
    de hoy— el método existe, no compila nada y no rompe nada.
    """
    snippet_key = compile_context.get('snippet-key')

    template = compile_context['ref_name']
    sub_call_key = compile_context.get('snippet-sub-call-key')

    # data-snippet y data-name se añaden UNA vez, al compilar el nodo raíz de
    # la plantilla.
    if not template or template not in {snippet_key, sub_call_key} or el.getparent() is not None:
        return None

    snippet_base_node = el
    if el.tag == 't':
        element_children = [child for child in list(el)
                       if isinstance(child.tag, str) and child.tag != 't']
        if len(element_children) == 1:
            snippet_base_node = element_children[0]
        elif not element_children:
            # Si no hay un nodo base válido, se comprueba si el nodo base es un
            # t-call a otra plantilla. Si lo es, la plantilla llamada debe
            # tomar la clave del snippet actual.
            element_children = [child for child in list(el)
                           if isinstance(child.tag, str)]
            if len(element_children) == 1:
                sub_call = element_children[0].get('t-call')
                if sub_call:
                    element_children[0].set(
                        't-options',
                        f"{{'snippet-key': '{snippet_key}', "
                        f"'snippet-sub-call-key': '{sub_call}'}}")
    # Si ya tiene data-snippet es un snippet guardado o heredado. No se pisa.
    if 'data-snippet' not in snippet_base_node.attrib:
        snippet_base_node.attrib['data-snippet'] = \
            snippet_key.split('.', 1)[-1]
    # Si ya tiene data-name es un snippet guardado o heredado. No se pisa.
    snippet_name = compile_context.get('snippet-name')
    if snippet_name and 'data-name' not in snippet_base_node.attrib:
        snippet_base_node.attrib['data-name'] = snippet_name
    return None


def _get_preload_attribute_xmlids(self):
    """≙ ``_get_preload_attribute_xmlids`` (``odoo19c: :79-80``)."""
    return ['t-snippet', 't-snippet-call']


# directivas de compilación


def _compile_directive_snippet(self, el, compile_context, indent):
    """≙ ``_compile_directive_snippet`` (``odoo19c: :84-120``)."""
    key = el.attrib.pop('t-snippet')
    el.set('t-call', key)
    snippet_lang = getattr(self, 'snippet_lang', None)
    if snippet_lang:
        el.set('t-lang', repr(snippet_lang))

    el.set('t-options', f"{{'snippet-key': {key!r}}}")
    view = model_by_name('ir.ui.view')._get_template_view(key)
    name = el.attrib.pop('string', view.name)
    thumbnail = el.attrib.pop('t-thumbnail', "oe-thumbnail")
    image_preview = el.attrib.pop('t-image-preview', None)
    # El motivo concreto por el que se prohíbe sanear:
    # - "true": prohibir siempre
    # - "form": prohibir si los formularios se sanean
    forbid_sanitize = el.attrib.pop('t-forbid-sanitize', None)
    grid_column_span = el.attrib.pop('t-grid-column-span', None)
    snippet_group = el.attrib.pop('snippet-group', None)
    group = el.attrib.pop('group', None)
    label = el.attrib.pop('label', None)
    div = Markup(
        '<div name="%s" data-oe-type="snippet" data-o-image-preview="%s" '
        'data-oe-thumbnail="%s" data-oe-snippet-id="%s" '
        'data-oe-snippet-key="%s" data-oe-keywords="%s" %s %s %s %s %s>') % (
        name,
        escape_silent(image_preview),
        thumbnail,
        view.pk,
        key.split('.')[-1],
        escape_silent(el.findtext('keywords')),
        Markup('data-oe-forbid-sanitize="%s"') % forbid_sanitize if forbid_sanitize else '',
        Markup('data-o-grid-column-span="%s"') % grid_column_span if grid_column_span else '',
        Markup('data-o-snippet-group="%s"') % snippet_group if snippet_group else '',
        Markup('data-o-group="%s"') % group if group else '',
        Markup('data-o-label="%s"') % label if label else '',
    )
    self._append_text(div, compile_context)
    code = self._compile_node(el, compile_context, indent)
    self._append_text('</div>', compile_context)
    return code


def _compile_directive_snippet_call(self, el, compile_context, indent):
    """≙ ``_compile_directive_snippet_call`` (``odoo19c: :122-127``)."""
    key = el.attrib.pop('t-snippet-call')
    snippet_name = el.attrib.pop('string', None)
    el.set('t-call', key)
    el.set('t-options',
           f"{{'snippet-key': {key!r}, 'snippet-name': {snippet_name!r}}}")
    return self._compile_node(el, compile_context, indent)


def _compile_directive_install(self, el, compile_context, indent):
    """≙ ``_compile_directive_install`` (``odoo19c: :129-150``)."""
    key = el.attrib.pop('t-install')
    thumbnail = el.attrib.pop('t-thumbnail', 'oe-thumbnail')
    image_preview = el.attrib.pop('t-image-preview', None)
    group = el.attrib.pop('group', None)
    label = el.attrib.pop('label', None)
    user = get_current_user()
    if user is not None and user.has_group('base.group_system'):
        module = model_by_name('ir.module.module').objects.filter(
            name=key).first()
        if not module or module.state == 'installed':
            return []
        name = el.attrib.get('string') or 'Snippet'
        div = Markup(
            '<div name="%s" data-oe-type="snippet" data-module-id="%s" '
            'data-module-display-name="%s" data-o-image-preview="%s" '
            'data-oe-thumbnail="%s" %s %s><section/></div>') % (
            name,
            module.pk,
            module.display_name,
            escape_silent(image_preview),
            thumbnail,
            Markup('data-o-group="%s"') % group if group else '',
            Markup('data-o-label="%s"') % label if label else '',
        )
        self._append_text(div, compile_context)
    return []


def _compile_directive_placeholder(self, el, compile_context, indent):
    """≙ ``_compile_directive_placeholder`` (``odoo19c: :152-154``)."""
    el.set('t-att-placeholder', el.attrib.pop('t-placeholder'))
    return []


# orden e ignorados


def _directives_eval_order(self, previous):
    """≙ ``_directives_eval_order`` (``odoo19c: :158-168``).

    Se insertan **antes** de ``att`` porque las cuatro dependen de atributos
    estáticos como ``string``, y ``att`` los borra todos.
    """
    directives = previous()
    index = directives.index('att') - 1
    directives.insert(index, 'placeholder')
    directives.insert(index, 'snippet')
    directives.insert(index, 'snippet-call')
    directives.insert(index, 'install')
    return directives


def _get_template_cache_keys(self):
    """≙ ``_get_template_cache_keys`` (``odoo19c: :170-171``)."""
    return ['snippet_lang']


def _extend_cache_keys(new, previous):
    """``combine`` acumulativo — ≙ ``super()._get_template_cache_keys() + [...]``."""
    return list(previous or []) + list(new or [])


# ------------------------------------------------------
# QWeb fields
# ------------------------------------------------------


def attributes(cls, record, field_name, options, values=None):
    """≙ ``IrQwebField.attributes`` (``odoo19c: :182-200``).

    Añade el ``placeholder`` y, para los campos traducibles de texto, el
    estado de traducción que el editor pinta.

    **Divergencia declarada:** ``options['translate']`` y el ``placeholder``
    del campo no existen como atributos en este árbol; se leen con ``getattr``
    y ``options.get`` conservando el default de la fuente (ver la divergencia
    3 del módulo).
    """
    attrs = {}
    field = next((f for f in type(record)._meta.get_fields()
                  if getattr(f, 'name', None) == field_name), None)

    placeholder = options.get('placeholder') or getattr(field, 'placeholder', None)
    if placeholder:
        attrs['placeholder'] = placeholder

    internal_type = getattr(field, 'get_internal_type', lambda: '')()
    if options.get('translate') and internal_type in ('CharField', 'TextField'):
        user = get_current_user()
        lang = getattr(user, 'lang', None) or 'en_US'
        base_lang = _base_lang_of(record)
        if lang == base_lang:
            attrs['data-oe-translation-state'] = 'translated'
        else:
            # ≙ ``record.with_context(lang=base_lang)[field_name]``: este ORM
            # no tiene contexto de idioma por registro, así que el valor base
            # es el almacenado y la comparación resuelve a "traducido" salvo
            # que un mecanismo de traducción por término lo desempate. Es la
            # misma divergencia que ``http_routing`` declara para
            # ``with_context(prefetch_langs=True)``.
            base_value = getattr(record, field_name)
            value = getattr(record, field_name)
            attrs['data-oe-translation-state'] = (
                'translated' if base_value != value else 'to_translate')

    return attrs


def value_from_string(cls, value):
    """≙ ``IrQwebField.value_from_string`` (``odoo19c: :202-203``)."""
    return value


def from_html(cls, model, field, element):
    """≙ ``IrQwebField.from_html`` (``odoo19c: :205-207``)."""
    return cls.value_from_string(element.text_content().strip()) or False


def integer_from_html(cls, model, field, element):
    """≙ ``IrQwebFieldInteger.from_html`` (``odoo19c: :215-219``)."""
    lang = _user_lang()
    value = element.text_content().strip()
    return int(value.replace(lang.thousands_sep or '', ''))


def float_from_html(cls, model, field, element):
    """≙ ``IrQwebFieldFloat.from_html`` (``odoo19c: :227-232``)."""
    lang = _user_lang()
    value = element.text_content().strip()
    return float(value.replace(lang.thousands_sep or '', '')
                      .replace(lang.decimal_point, '.'))


def many2one_attributes(cls, record, field_name, options, values=None):
    """≙ ``IrQwebFieldMany2one.attributes`` (``odoo19c: :240-260``)."""
    field = next((f for f in type(record)._meta.get_fields()
                  if getattr(f, 'name', None) == field_name), None)
    attrs = {}
    if options.get('inherit_branding'):
        many2one = getattr(record, field_name, None)
        if many2one:
            attrs['data-oe-many2one-id'] = many2one.pk
            attrs['data-oe-many2one-model'] = getattr(
                type(many2one), '_name', type(many2one)._meta.label)
        if options.get('null_text'):
            attrs['data-oe-many2one-allowreset'] = 1
            if not many2one:
                related = field.related_model
                attrs['data-oe-many2one-model'] = getattr(
                    related, '_name', related._meta.label)
        attrs['data-oe-many2one-domain'] = json_safe.dumps(_field_domain(field))
    return attrs


def many2one_from_html(cls, model, field, element):
    """≙ ``IrQwebFieldMany2one.from_html`` (``odoo19c: :262-282``)."""
    Model = model_by_name(element.get('data-oe-model'))
    record_id = int(element.get('data-oe-id'))
    field_name = element.get('data-oe-field')
    many2one_id = int(element.get('data-oe-many2one-id'))

    allow_reset = element.get('data-oe-many2one-allowreset')
    if allow_reset and not many2one_id:
        # Se reinicia el id del many2one.
        Model.objects.filter(pk=record_id).update(**{field_name: None})
        return None

    M2O = field.related_model
    record = many2one_id and M2O.objects.filter(pk=many2one_id).first()
    if record:
        # Se guarda el id nuevo del many2one.
        Model.objects.filter(pk=record_id).update(
            **{'%s_id' % field_name: many2one_id})

    return None


def contact_attributes(cls, record, field_name, options, values=None):
    """≙ ``IrQwebFieldContact.attributes`` (``odoo19c: :290-295``)."""
    attrs = {}
    if options.get('inherit_branding'):
        attrs['data-oe-contact-options'] = json.dumps(options)
    return attrs


def get_record_to_html(cls, contact_ids, options=None):
    """≙ ``IrQwebFieldContact.get_record_to_html`` (``odoo19c: :297-300``).

    Ayuda para invocar el renderizado del campo de contacto.
    """
    partner = model_by_name('res.partner').objects.filter(
        pk=contact_ids[0]).first()
    return cls.value_to_html(partner, options=options)


def date_attributes(cls, record, field_name, options, values=None):
    """≙ ``IrQwebFieldDate.attributes`` (``odoo19c: :308-329``)."""
    attrs = {}
    if options.get('inherit_branding'):
        attrs['data-oe-original'] = getattr(record, field_name)

        field = next((f for f in type(record)._meta.get_fields()
                      if getattr(f, 'name', None) == field_name), None)
        if getattr(field, 'get_internal_type', lambda: '')() == 'DateTimeField':
            attrs = _converter_for('ir.qweb.field.datetime').attributes(
                record, field_name, options, values)
            attrs['data-oe-type'] = 'datetime'
            return attrs

        lg = _user_lang()
        locale = _babel_locale_parse(lg.code)
        babel_format = value_format = _posix_to_ldml(lg.date_format,
                                                     locale=locale)

        if getattr(record, field_name):
            value_format = babel.dates.format_date(
                getattr(record, field_name), format=babel_format,
                locale=locale)

        attrs['data-oe-original-with-format'] = value_format
    return attrs


def date_from_html(cls, model, field, element):
    """≙ ``IrQwebFieldDate.from_html`` (``odoo19c: :331-339``)."""
    value = element.text_content().strip()
    if not value:
        return False

    lg = _user_lang()
    return datetime.strptime(value, lg.date_format).date()


def datetime_attributes(cls, record, field_name, options, values=None):
    """≙ ``IrQwebFieldDatetime.attributes`` (``odoo19c: :347-370``)."""
    attrs = {}

    if options.get('inherit_branding'):
        value = getattr(record, field_name)

        lg = _user_lang()
        locale = _babel_locale_parse(lg.code)
        babel_format = value_format = _posix_to_ldml(
            '%s %s' % (lg.date_format, lg.time_format), locale=locale)
        user = get_current_user()
        tz = getattr(user, 'tz', None) or timezone.get_current_timezone_name()

        if isinstance(value, str):
            value = datetime.fromisoformat(value)

        if value:
            # se convierte de UTC (hora del servidor) a la del usuario
            value = value.astimezone(pytz.timezone(tz))
            value_format = babel.dates.format_datetime(
                value, format=babel_format, locale=locale)
            value = value.isoformat()

        attrs['data-oe-original'] = value
        attrs['data-oe-original-with-format'] = value_format
        attrs['data-oe-original-tz'] = tz
    return attrs


def datetime_from_html(cls, model, field, element):
    """≙ ``IrQwebFieldDatetime.from_html`` (``odoo19c: :372-401``)."""
    value = element.text_content().strip()
    if not value:
        return False

    # se parsea de cadena a datetime
    lg = _user_lang()
    datetime_format = f'{lg.date_format} {lg.time_format}'
    try:
        dt = datetime.strptime(value, datetime_format)
    except ValueError:
        raise ValueError(
            "The datetime %(value)s does not match the format %(format)s" % {
                'value': value, 'format': datetime_format})

    # se convierte de la zona del usuario de vuelta a UTC
    user = get_current_user()
    tz_name = (element.attrib.get('data-oe-original-tz')
               or getattr(user, 'tz', None))
    if tz_name:
        try:
            user_tz = pytz.timezone(tz_name)
            utc = pytz.utc

            dt = user_tz.localize(dt).astimezone(utc)
        except Exception:  # noqa: BLE001
            logger.warning(
                "Failed to convert the value for a field of the model"
                " %s back from the user's timezone (%s) to UTC",
                model, tz_name,
                exc_info=True)

    # se vuelve a formatear a cadena
    return dt.isoformat()


def text_from_html(cls, model, field, element):
    """≙ ``IrQwebFieldText.from_html`` (``odoo19c: :409-411``)."""
    return html_to_text(element)


def selection_from_html(cls, model, field, element):
    """≙ ``IrQwebFieldSelection.from_html`` (``odoo19c: :419-427``)."""
    value = element.text_content().strip()
    selection = field.choices or ()
    for k, v in selection:
        if value == v:
            return k

    raise ValueError("No value found for label %s in selection %s" % (
                     value, selection))


def html_attributes(cls, record, field_name, options, values=None):
    """≙ ``IrQwebFieldHtml.attributes`` (``odoo19c: :435-460``).

    Ver la divergencia 3: las cuatro banderas de saneo se leen con ``getattr``
    y su default es el que hace la rama inofensiva mientras no existan.
    """
    attrs = {}
    if options.get('inherit_branding'):
        field = next((f for f in type(record)._meta.get_fields()
                      if getattr(f, 'name', None) == field_name), None)
        if getattr(field, 'sanitize', False):
            if getattr(field, 'sanitize_overridable', False):
                user = get_current_user()
                if user is not None and user.has_group(
                        'base.group_sanitize_override'):
                    # No se marca el campo como 'sanitize' si el saneo es
                    # anulable y el usuario tiene derecho a hacerlo.
                    return attrs
                try:
                    field.convert_to_column_insert(
                        getattr(record, field_name), record)
                except Exception:  # noqa: BLE001
                    # El campo contiene elementos que el saneo quitaría.
                    # Significa que alguien de un grupo que puede saltarse el
                    # saneo lo guardó antes. Se marca como no editable.
                    attrs['data-oe-sanitize-prevent-edition'] = 1
                    return attrs
            # La edición no está impedida del todo y el saneo no es anulable.
            attrs['data-oe-sanitize'] = (
                'no_block' if getattr(field, 'sanitize_attributes', False)
                else 1 if getattr(field, 'sanitize_form', True)
                else 'allow_form')

    return attrs


def html_from_html(cls, model, field, element):
    """≙ ``IrQwebFieldHtml.from_html`` (``odoo19c: :462-469``)."""
    content = []
    if element.text:
        content.append(element.text)
    content.extend(html.tostring(child, encoding='unicode')
                   for child in element.iterchildren(tag=etree.Element))
    return '\n'.join(content)


#: ≙ ``IrQwebFieldImage.local_url_re`` (``odoo19c: :480``).
local_url_re = re.compile(r'^/(?P<module>[^]]+)/static/(?P<rest>.+)$')
#: ≙ ``IrQwebFieldImage.redirect_url_re`` (``odoo19c: :481``).
redirect_url_re = re.compile(r'\/web\/image\/\d+-redirect\/')


def image_from_html(cls, model, field, element):
    """≙ ``IrQwebFieldImage.from_html`` (``odoo19c: :483-511``)."""
    if element.find('img') is None:
        return False
    url = element.find('img').get('src')

    url_object = urlparse(url)
    if url_object.path.startswith('/web/image'):
        fragments = url_object.path.split('/')
        query = {k: v[0] for k, v in parse_qs(url_object.query).items()}
        url_id = fragments[3].split('-')[0]
        # urls de imagen de ir.attachment: /web/image/<id>[-<checksum>][/...]
        if url_id.isdigit():
            model = 'ir.attachment'
            oid = url_id
            field = 'datas'
        # url de un campo binario de un modelo:
        # /web/image/<model>/<id>/<field>[/...]
        else:
            model = query.get('model', fragments[3])
            oid = query.get('id', fragments[4])
            field = query.get('field', fragments[5])
        item = model_by_name(model).objects.filter(pk=int(oid)).first()
        if redirect_url_re.match(url_object.path):
            return cls.load_remote_url(item.url)
        return getattr(item, field)

    if local_url_re.match(url_object.path):
        return cls.load_local_url(url)

    return cls.load_remote_url(url)


def load_local_url(cls, url):
    """≙ ``IrQwebFieldImage.load_local_url`` (``odoo19c: :513-529``)."""
    match = local_url_re.match(urlparse(url).path)
    rest = match.group('rest')

    path = os.path.join(
        match.group('module'), 'static', rest)

    try:
        with file_open(path, 'rb') as f:
            # se fuerza la carga completa para comprobar que es imagen válida
            image = I.open(f)
            image.load()
            f.seek(0)
            return base64.b64encode(f.read())
    except Exception:  # noqa: BLE001
        logger.exception("Failed to load local image %r", url)
        return None


def load_remote_url(cls, url):
    """≙ ``IrQwebFieldImage.load_remote_url`` (``odoo19c: :531-561``)."""
    if url.startswith('data:'):
        logger.debug("Cannot load binary data url %r", url)
        return None
    try:
        # habría que retirar las URL remotas por completo:
        # * en un campo, bajarlas sin tumbar el servidor es un reto
        # * en una vista, pueden disparar avisos de contenido mixto si un CMS
        #   HTTPS enlaza imágenes HTTP
        # ¿implementar la subida por arrastrar y soltar para mitigarlo?

        req = requests.get(url, timeout=REMOTE_CONNECTION_TIMEOUT)
        # PIL necesita un archivo con posicionamiento, así que el resultado va
        # envuelto en un buffer de IO
        image = I.open(io.BytesIO(req.content))
        # se fuerza la carga completa para validar el dato
        image.load()
    # se atrapa todo porque las excepciones de Pillow heredan de Exception
    except Exception:  # noqa: BLE001
        logger.warning("Failed to load remote image %r", url, exc_info=True)
        return None

    # no se usa el dato original por si venía algo raro dentro; con suerte PIL
    # quita parte de ello
    out = io.BytesIO()
    image.save(out, image.format)
    return base64.b64encode(out.getvalue())


def monetary_from_html(cls, model, field, element):
    """≙ ``IrQwebFieldMonetary.from_html`` (``odoo19c: :566-573``)."""
    lang = _user_lang()

    value = element.find('span').text_content().strip()

    return float(value.replace(lang.thousands_sep or '', '')
                      .replace(lang.decimal_point, '.'))


def duration_attributes(cls, record, field_name, options, values=None):
    """≙ ``IrQwebFieldDuration.attributes`` (``odoo19c: :581-586``)."""
    attrs = {}
    if options.get('inherit_branding'):
        attrs['data-oe-original'] = getattr(record, field_name)
    return attrs


def duration_from_html(cls, model, field, element):
    """≙ ``IrQwebFieldDuration.from_html`` (``odoo19c: :588-592``)."""
    value = element.text_content().strip()

    # valor sin localizar
    return float(value)


# ``IrQwebFieldRelative`` (``odoo19c: :595-599``) no declara ningún método:
# "get formatting from ir.qweb.field.relative but edition/save from datetime".
# ``IrQwebFieldQweb`` (``:602-605``) tampoco. Sus contrapartes
# ``IrFieldConverterRelative`` e ``IrFieldConverterTemplate`` ya viven en
# ``base``; no hay nada que colgarles.


def html_to_text(element):
    """≙ ``html_to_text`` (``odoo19c: :608-655``).

    Convierte contenido HTML con saltos de línea marcados por etiquetas (br,
    p, div, …) en el texto aproximadamente equivalente.

    Sirve para arreglar el viaje de ida y vuelta de texto y m2o: con libxml
    2.8.0 (no con 2.9.1), al parsear un ``IrQwebFieldHtml`` con
    ``lxml.html.fromstring`` los nodos de texto compuestos **sólo** de espacio
    en blanco se pierden sin remedio; y depender de que los saltos de línea
    estén en el texto (por ejemplo, insertados al editar) es de todos modos
    mala práctica.

    -> esta utilidad colapsa las secuencias de espacio en blanco y reemplaza
       nodos por los saltos de línea que les corresponden
       * p se rodea de 2 saltos, antes y después
       * br se reemplaza por un salto
       * los elementos de bloque no mencionados se rodean de un salto

    Debería parecerse (con mucha menos tecnología) al html2text de aaronsw. El
    de aquél produce markdown completo; nuestro conversor de texto a html sólo
    reemplaza saltos por elementos <br>, así que aquí se revierte eso y unos
    pocos elementos más por si alguien intentó meter saltos o párrafos en un
    campo de texto.

    :param element: contenido lxml.html
    :returns: la salida de texto puro correspondiente
    """
    # la salida es una lista de str | int. Los enteros son peticiones de
    # relleno (mínimo de saltos de línea). Cuando hay varias, se funden en la
    # mayor.
    output = []
    _wrap(element, output)

    # se quita el espacio en blanco inicial y final y se reemplazan las
    # secuencias (espacio)\n(espacio) por un solo salto, donde (espacio) es
    # espacio en blanco que no es salto
    return re.sub(
        r'[ \t\r\f]*\n[ \t\r\f]*',
        '\n',
        ''.join(_realize_padding(output)).strip())


_PADDED_BLOCK = {"p", "h1", "h2", "h3", "h4", "h5", "h6"}
# https://developer.mozilla.org/en-US/docs/HTML/Block-level_elements menos p
_MISC_BLOCK = {"address", "article", "aside", "audio", "blockquote", "canvas",
               "dd", "dl", "div", "figcaption", "figure", "footer", "form",
               "header", "hgroup", "hr", "ol", "output", "pre", "section",
               "tfoot", "ul", "video"}


def _collapse_whitespace(text):
    """≙ ``_collapse_whitespace`` (``odoo19c: :664-668``).

    Colapsa las secuencias de espacio en blanco de ``text`` a un solo espacio.
    """
    return re.sub(r'\s+', ' ', text)


def _realize_padding(it):
    """≙ ``_realize_padding`` (``odoo19c: :671-687``).

    Funde y convierte las peticiones de relleno: los enteros de la secuencia
    de salida piden al menos n saltos de línea. Las rachas se colapsan en la
    petición mayor y se convierten en saltos.
    """
    padding = 0
    for item in it:
        if isinstance(item, int):
            padding = max(padding, item)
            continue

        if padding:
            yield '\n' * padding
            padding = 0

        yield item
    # el relleno sobrante da igual: la salida se recorta


def _wrap(element, output, wrapper=''):
    """≙ ``_wrap`` (``odoo19c: :690-702``).

    Extrae recursivamente el texto de ``element`` (vía
    :func:`_element_to_text`) y lo rodea de ``wrapper``. El texto extraído se
    añade a ``output``.

    :type wrapper: basestring | int
    """
    output.append(wrapper)
    if element.text:
        output.append(_collapse_whitespace(element.text))
    for child in element:
        _element_to_text(child, output)
    output.append(wrapper)


def _element_to_text(e, output):
    """≙ ``_element_to_text`` (``odoo19c: :705-716``)."""
    if e.tag == 'br':
        output.append('\n')
    elif e.tag in _PADDED_BLOCK:
        _wrap(e, output, 2)
    elif e.tag in _MISC_BLOCK:
        _wrap(e, output, 1)
    else:
        # en línea
        _wrap(e, output)

    if e.tail:
        output.append(_collapse_whitespace(e.tail))


def apply_html_editor_extensions():
    """Cuelga las dos mitades — ≙ los catorce ``_inherit`` de la fuente.

    **Cada instalación se escribe como una llamada propia, con el nombre del
    símbolo literal y la clase destino nombrada.** Antes iban en dos bucles
    sobre tuplas, y aunque el efecto en ejecución es el mismo, el receptor y
    la clave quedaban en variables de bucle: ``check_porte_completo`` —que lee
    las llamadas de instalación sin ejecutarlas— no podía atribuir ni uno de
    los veintiocho enganches y publicaba trece ``CLASE AUSENTE`` sobre un
    porte completo. La forma de una llamada por símbolo es la que usa el resto
    del árbol (``crm/models/digest.py``, ``http_routing/models/ir_qweb.py``) y
    es la que se puede leer sin ejecutar.
    """
    # --- IrQweb → IrTemplateExpressions: directivas y enganches ----------
    chain_method(IrTemplateExpressions, '_compile_node', _compile_node)
    chain_method(IrTemplateExpressions, '_get_preload_attribute_xmlids',
                 _get_preload_attribute_xmlids, combine=extend_list)
    chain_method(IrTemplateExpressions, '_compile_directive_snippet',
                 _compile_directive_snippet)
    chain_method(IrTemplateExpressions, '_compile_directive_snippet_call',
                 _compile_directive_snippet_call)
    chain_method(IrTemplateExpressions, '_compile_directive_install',
                 _compile_directive_install)
    chain_method(IrTemplateExpressions, '_compile_directive_placeholder',
                 _compile_directive_placeholder)
    wrap_method(IrTemplateExpressions, '_directives_eval_order',
                _directives_eval_order)
    chain_method(IrTemplateExpressions, '_get_template_cache_keys',
                 _get_template_cache_keys, combine=_extend_cache_keys)

    # --- Los trece conversores -------------------------------------------
    # ``classmethod(...)`` envuelve cada función porque el conversor de
    # ``base`` declara sus métodos así; ver el docstring del módulo.
    chain_method(IrFieldConverter, 'attributes', classmethod(attributes),
                 combine=merge_dict)
    chain_method(IrFieldConverter, 'value_from_string',
                 classmethod(value_from_string))
    chain_method(IrFieldConverter, 'from_html', classmethod(from_html))

    chain_method(IrFieldConverterInteger, 'from_html',
                 classmethod(integer_from_html))

    chain_method(IrFieldConverterFloat, 'from_html',
                 classmethod(float_from_html))

    chain_method(IrFieldConverterMany2one, 'attributes',
                 classmethod(many2one_attributes), combine=merge_dict)
    chain_method(IrFieldConverterMany2one, 'from_html',
                 classmethod(many2one_from_html))

    chain_method(IrFieldConverterContact, 'attributes',
                 classmethod(contact_attributes), combine=merge_dict)
    chain_method(IrFieldConverterContact, 'get_record_to_html',
                 classmethod(get_record_to_html))

    chain_method(IrFieldConverterDate, 'attributes',
                 classmethod(date_attributes), combine=merge_dict)
    chain_method(IrFieldConverterDate, 'from_html',
                 classmethod(date_from_html))

    chain_method(IrFieldConverterDatetime, 'attributes',
                 classmethod(datetime_attributes), combine=merge_dict)
    chain_method(IrFieldConverterDatetime, 'from_html',
                 classmethod(datetime_from_html))

    chain_method(IrFieldConverterText, 'from_html',
                 classmethod(text_from_html))

    chain_method(IrFieldConverterSelection, 'from_html',
                 classmethod(selection_from_html))

    chain_method(IrFieldConverterHtml, 'attributes',
                 classmethod(html_attributes), combine=merge_dict)
    chain_method(IrFieldConverterHtml, 'from_html',
                 classmethod(html_from_html))

    chain_method(IrFieldConverterImage, 'from_html',
                 classmethod(image_from_html))
    chain_method(IrFieldConverterImage, 'load_local_url',
                 classmethod(load_local_url))
    chain_method(IrFieldConverterImage, 'load_remote_url',
                 classmethod(load_remote_url))

    chain_method(IrFieldConverterMonetary, 'from_html',
                 classmethod(monetary_from_html))

    chain_method(IrFieldConverterDuration, 'attributes',
                 classmethod(duration_attributes), combine=merge_dict)
    chain_method(IrFieldConverterDuration, 'from_html',
                 classmethod(duration_from_html))

    # ≙ ``local_url_re`` / ``redirect_url_re``, atributos de clase de
    # ``IrQwebFieldImage`` (``odoo19c: :480-481``).
    IrFieldConverterImage.local_url_re = local_url_re
    IrFieldConverterImage.redirect_url_re = redirect_url_re
