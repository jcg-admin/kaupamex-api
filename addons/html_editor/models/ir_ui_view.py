"""``ir.ui.view`` extendido por ``html_editor`` — guardar lo que se editó.

Adaptación de ``odoo19c: addons/html_editor/models/ir_ui_view.py``
(555 líneas, LGPL-3 — copia + adaptación con atribución, DEC-KX-03).

**26 símbolos en la fuente: 25 portados, 1 bloqueado con sucesor.** Una
constante y veinticinco métodos.

Qué hace
========

Cuando alguien edita una página y pulsa guardar, lo que llega al servidor es
**HTML del navegador**: con clases de edición, con atributos ``data-oe-*``, y
con los campos de registro incrustados como nodos. Este archivo es lo que
deshace ese viaje:

1. **Limpia** lo que era andamiaje de edición y no contenido
   (``_get_cleaned_non_editing_attributes``).
2. **Extrae los campos incrustados** y los escribe en su registro real
   (``extract_embedded_fields`` → ``save_embedded_field``), devolviendo al
   documento el ``t-field`` que los representaba (``to_field_ref``).
3. **Extrae las zonas ``oe_structure``** y crea una vista heredada por cada
   una (``save_oe_structure``), para que la edición de una zona no reescriba
   la vista padre.
4. **Reemplaza la sección** del arch por la editada
   (``replace_arch_section``) y sólo escribe si de verdad cambió
   (``_are_archs_equal``).

Y el bloque de *snippets*: guardar uno nuevo con nombre único
(``save_snippet``), renombrarlo (``rename_snippet``) y borrarlo
(``delete_snippet``).

Qué pieza de este stack cubre cada delegación de la fuente
==========================================================

===============================  =====================================
Fuente delega en                 Aquí lo cubre
===============================  =====================================
``lxml`` (parseo, XPath,         **lxml** — el mismo, incluido
construcción de nodos)           ``html.html_parser.makeelement``
``hasclass()`` (extensión XPath  **lxml** — la misma expresión, escrita
propia de la referencia)         con ``contains(concat(' ', ...))``,
                                 que es lo que ``hasclass`` compila.
                                 Ver la divergencia 2.
almacén del arch por ``key``     **postgresql** vía **django** —
                                 ``arch_db``; ver la divergencia 1
herencia entre vistas por XPath  **lxml**, ya portado en
                                 ``base.IrUiView.apply_inheritance_specs``
``Domain`` del ORM               **django** — ``models.Q``, que es lo
                                 que ``website.website_domain`` ya
                                 devuelve en este árbol
``self.env['ir.ui.view']``       ``orm.registry.model_by_name``
``uuid``                         **cpython** — el mismo
===============================  =====================================

Divergencia 1 — ``arch`` → ``arch_db``, y por qué NO es un renombre
===================================================================

La fuente tiene tres campos: ``arch_db`` (la columna), ``arch`` y
``arch_base`` (dos calculados que le aplican la traducción por término).
``base`` de este árbol porta **la columna** y declara que la traducción por
campo no se porta. Así que ``self.arch`` de la fuente resuelve aquí a
``self.arch_db``: es el mismo dato, sin la capa de traducción que no existe.

Divergencia 2 — el colisión de nombre con ``Model.save``, y el sucesor
======================================================================

**Ésta es la divergencia que hay que leer entera.**

La fuente declara ``def save(self, value, xpath=None)`` sobre ``ir.ui.view``:
*"Update a view section"*. En Odoo ``save`` no significa nada para el ORM.

Aquí sí: ``base.IrUiView.save(*args, from_file=False, save_prev=True,
**kwargs)`` es **el método de persistencia de Django**, y este mismo árbol lo
declara como el puerto de ``create`` + ``write`` de la fuente. Colgar encima
la función de la fuente no la renombraría: **rompería toda escritura de vista
del árbol**, incluido el cargador de datos.

Resolución, en dos mitades:

- **El símbolo se porta con el nombre de la fuente.** La función
  :func:`save` de este módulo tiene su nombre, su firma —con el receptor
  explícito, que es lo que este idioma exige para una función que se cuelga— y
  su cuerpo entero.
- **El atributo instalado se llama ``save_from_html``**, porque el nombre
  ``save`` ya está ocupado por otro contrato en la misma clase. Es una
  colisión de espacio de nombres, no una elección de estilo: los dos métodos
  existen, hacen cosas distintas y ninguno sustituye al otro.

**Sucesor nombrado:** el consumidor de este método es la vista DRF
``/html_editor/…`` que el editor invoca al guardar una sección; su ruta la
declara ``controllers/urls.py`` de este addon. Se reporta al orquestador para
que el contrato publicado nombre ``save_from_html`` y no ``save``.

Divergencia 3 — la copia de traducciones por término, detenida
===============================================================

BLOQUEADO por ``orm.models.get_translation_dictionary`` — con
``_get_stored_translations``, ``env.cache.update_raw`` y el contexto
``prefetch_langs``, son las cuatro piezas de la traducción por término que
este árbol declara no portar. Medido 2026-09-02:
``grep -rnE "def (get_translation_dictionary|_get_stored_translations)"
--include=*.py src/orm/ src/addons/base/`` → 0 (las dos únicas apariciones
son la prosa de ``src/orm/models.py:1172-1173``, que declara la ausencia).
Sucesor: portar la traducción por término en ``src/orm`` + ``base``.

Es el único símbolo no portado. Copia las traducciones **por término** de un
campo a otro, y para eso necesita cinco piezas del ORM de la referencia que
este árbol declara no portar: ``field.translate`` invocable,
``get_translation_dictionary``, ``_get_stored_translations``,
``env.cache.update_raw`` y el contexto ``prefetch_langs``. ``base`` lo dice en
el docstring de su ``ir_ui_view.py``: *"la traducción por campo no se porta"*.

Construirlo aquí sería construir el mecanismo de traducción por término del
ORM entero dentro de un addon de editor, en el sitio equivocado.

**Sucesor nombrado:** portar la traducción por término de campo en
``src/orm`` + ``base`` (``translate`` invocable,
``get_translation_dictionary``, ``_get_stored_translations``) y entonces este
método. Se reporta al orquestador.

Lo que **sí** se porta es su llamador, ``_copy_custom_snippet_translations``:
parsea, busca el *snippet* a medida y delega. Con el bloqueo, delega en un
método que levanta ``NotImplementedError`` con el sucesor nombrado — que es lo
contrario de callar: quien lo invoque lo sabe en el acto, y quien lea el
árbol encuentra la arista.

Divergencia 4 — el parche a ``web.frontend_layout``
====================================================

El cuerpo de ``save`` de la fuente trae un bloque con un ``# TODO: in master,
remove this`` que parchea una vista concreta de ``website``. Se porta entero
—es conducta de la fuente, no ruido— con su comentario verbatim. Su condición
depende de cuatro ``key`` de ``website``; si esas vistas no están, el bloque
no hace nada, que es exactamente lo que hace allá.
"""
import copy
import logging
import uuid

from addons.base.models.ir_ui_view import MOVABLE_BRANDING
from django.core.exceptions import ValidationError
from django.db import models as django_models
from lxml import etree, html
from orm.environments import get_current_user
from orm.model_classes import extend_model
from orm.registry import model_by_name

_logger = logging.getLogger(__name__)

EDITING_ATTRIBUTES = MOVABLE_BRANDING + [
    'data-oe-type',
    'data-oe-expression',
    'data-oe-translation-id',
    'data-note-id'
]

#: ≙ ``_inherit = 'ir.ui.view'`` (``odoo19c: :24``).
_inherit = 'ir.ui.view'

#: ≙ la extensión XPath ``hasclass(x)`` de la referencia, que compila a esto.
#: Se escribe una vez y se compone, en vez de repetir la fórmula en los cuatro
#: sitios que la usan — repetirla es cómo dos de ellos acaban difiriendo.
_HASCLASS = ("contains(concat(' ', normalize-space(@class), ' '), ' %s ')")


def _hasclass(name):
    """El predicado XPath de ``hasclass('<name>')``."""
    return _HASCLASS % name


def _get_cleaned_non_editing_attributes(self, attributes):
    """≙ ``_get_cleaned_non_editing_attributes`` (``odoo19c: :26-43``).

    Devuelve un mapeo nuevo de atributos -> valor sin las partes que no se
    guardan (branding, clases de edición, …). Las clases se limpian del lado
    del cliente antes de guardar, porque en su mayoría dependen de las
    opciones asociadas (así que no se supone que aquí se sepa cuáles quitar).

    :param attributes: un mapeo de atributos -> valor
    :return: un mapeo nuevo de atributos -> valor
    """
    attributes = {k: v for k, v in attributes if k not in EDITING_ATTRIBUTES}
    if 'class' in attributes:
        classes = attributes['class'].split()
        attributes['class'] = ' '.join(
            [c for c in classes if c != 'o_editable'])
    if attributes.get('contenteditable') == 'true':
        del attributes['contenteditable']
    return attributes


# ------------------------------------------------------
# Guardar desde html
# ------------------------------------------------------


def extract_embedded_fields(self, arch):
    """≙ ``extract_embedded_fields`` (``odoo19c: :50-52``)."""
    return arch.xpath('//*[@data-oe-model != "ir.ui.view"]')


def extract_oe_structures(self, arch):
    """≙ ``extract_oe_structures`` (``odoo19c: :54-56``)."""
    return arch.xpath(
        '//*[%s][contains(@id, "oe_structure")]' % _hasclass('oe_structure'))


def get_default_lang_code(self):
    """≙ ``get_default_lang_code`` (``odoo19c: :58-60``)."""
    return False


def save_embedded_field(self, el):
    """≙ ``save_embedded_field`` (``odoo19c: :62-85``).

    **Divergencia:** la fuente re-navega el registro con
    ``with_context(lang=...)`` cuando hay idioma por defecto. Este ORM no
    tiene contexto de idioma por registro (misma divergencia que
    ``http_routing`` declara), así que la escritura es directa; el idioma por
    defecto lo sigue decidiendo :func:`get_default_lang_code`, que es el
    enganche que ``website`` redefine.
    """
    Model = model_by_name(el.get('data-oe-model'))
    field_name = el.get('data-oe-field')

    name = 'ir.qweb.field.' + el.get('data-oe-type')
    converter = model_by_name(name) or model_by_name('ir.qweb.field')

    field = next((f for f in Model._meta.get_fields()
                  if getattr(f, 'name', None) == field_name), None)

    try:
        value = converter.from_html(Model, field, el)
        if value is not None:
            record = Model.objects.filter(
                pk=int(el.get('data-oe-id'))).first()
            if record is not None:
                setattr(record, field_name, value)
                record.save()

            if callable(getattr(field, 'translate', None)):
                self._copy_custom_snippet_translations(record, field_name)

    except (ValueError, TypeError):
        raise ValidationError(
            "Invalid field value for %(field_name)s: %(value)s" % {
                'field_name': getattr(field, 'verbose_name', field_name),
                'value': el.text_content().strip(),
            })


def save_oe_structure(self, el):
    """≙ ``save_oe_structure`` (``odoo19c: :87-116``)."""
    if el.get('id') in self.key:
        # No se hereda si la oe_structure ya tiene su propia vista heredera
        return False

    arch = etree.Element('data')
    xpath = etree.Element(
        'xpath',
        expr="//*[%s][@id='%s']" % (_hasclass('oe_structure'), el.get('id')),
        position="replace")
    arch.append(xpath)
    attributes = self._get_cleaned_non_editing_attributes(el.attrib.items())
    structure = etree.Element(el.tag, attrib=attributes)
    structure.text = el.text
    xpath.append(structure)
    for child in el.iterchildren(tag=etree.Element):
        structure.append(copy.deepcopy(child))

    vals = {
        'inherit_id': self,
        'name': '%s (%s)' % (self.name, el.get('id')),
        'arch_db': etree.tostring(arch, encoding='unicode'),
        'key': '%s_%s' % (self.key, el.get('id')),
        'type': 'qweb',
        'mode': 'extension',
    }
    vals.update(self._save_oe_structure_hook())
    oe_structure_view = model_by_name('ir.ui.view').objects.create(**vals)
    self._copy_custom_snippet_translations(oe_structure_view, 'arch_db')

    return True


def _copy_custom_snippet_translations(self, record, html_field):
    """≙ ``_copy_custom_snippet_translations`` (``odoo19c: :118-135``).

    Dado un ``record`` y su campo HTML, detecta el uso de un *snippet* a
    medida y copia sus traducciones.
    """
    lang_value = getattr(record, html_field, None)
    if not lang_value or not lang_value.strip():
        return

    try:
        tree = html.fromstring(lang_value)
    except etree.ParserError as e:
        raise ValidationError(str(e))

    View = model_by_name('ir.ui.view')
    for custom_snippet_element in tree.xpath(
            '//*[%s]' % _hasclass('s_custom_snippet')):
        custom_snippet_name = custom_snippet_element.get('data-name')
        custom_snippet_view = View.objects.filter(
            name=custom_snippet_name).first()
        if custom_snippet_view:
            self._copy_field_terms_translations(
                custom_snippet_view, 'arch_db', record, html_field)


def _copy_field_terms_translations(self, records_from, name_field_from,
                                   record_to, name_field_to):
    """≙ ``_copy_field_terms_translations`` (``odoo19c: :137-216``).

    BLOQUEADO por ``orm.models.get_translation_dictionary`` — ver la
    divergencia 3 del docstring del módulo, con su medición y su sucesor.

    Copia las traducciones de términos de ``records_from.name_field_from`` a
    ``record_to.name_field_to`` para todos los idiomas activos, si el término
    en ``record_to.name_field_to`` está sin traducir.

    Ver la divergencia 3 del docstring del módulo: las cinco piezas de ORM que
    este cuerpo necesita —``field.translate`` invocable,
    ``get_translation_dictionary``, ``_get_stored_translations``,
    ``env.cache.update_raw`` y el contexto ``prefetch_langs``— no están
    portadas, y ``base`` declara que la traducción por campo no se porta.

    Levanta en vez de callar: un ``return`` silencioso haría que el *snippet*
    a medida se copiara sin traducciones y nadie lo notara hasta cambiar de
    idioma.
    """
    raise NotImplementedError(
        'html_editor._copy_field_terms_translations: la traducción por '
        'término de campo no está portada en este árbol (ver la divergencia '
        '3 del módulo). Sucesor: portar `translate` invocable, '
        '`get_translation_dictionary` y `_get_stored_translations` en '
        '`src/orm` + `base`.')


def _save_oe_structure_hook(self):
    """≙ ``_save_oe_structure_hook`` (``odoo19c: :218-220``)."""
    return {}


def _are_archs_equal(self, arch1, arch2):
    """≙ ``_are_archs_equal`` (``odoo19c: :222-236``)."""
    # Comparar las cadenas no valdría: el orden de los atributos no debe
    # importar
    if arch1.tag != arch2.tag:
        return False
    if arch1.text != arch2.text:
        return False
    if arch1.tail != arch2.tail:
        return False
    if arch1.attrib != arch2.attrib:
        return False
    if len(arch1) != len(arch2):
        return False
    return all(self._are_archs_equal(arch1, arch2)
               for arch1, arch2 in zip(arch1, arch2))


def _get_allowed_root_attrs(self):
    """≙ ``_get_allowed_root_attrs`` (``odoo19c: :238-240``)."""
    return ['style', 'class', 'target', 'href']


def replace_arch_section(self, section_xpath, replacement, replace_tail=False):
    """≙ ``replace_arch_section`` (``odoo19c: :242-270``)."""
    # la raíz de la sección de arch no se reemplaza: no es editable en sí
    # misma, sólo su contenido lo es de verdad.
    arch = etree.fromstring(self.arch_db.encode('utf-8'))
    # => se obtiene la raíz del reemplazo
    if not section_xpath:
        root = arch
    else:
        # se garantiza que hay una sola coincidencia
        [root] = arch.xpath(section_xpath)

    root.text = replacement.text

    # Hay que reemplazar algunos atributos por los cambios de estilo del
    # elemento raíz
    for attribute in self._get_allowed_root_attrs():
        if attribute in replacement.attrib:
            root.attrib[attribute] = replacement.attrib[attribute]
        elif attribute in root.attrib:
            del root.attrib[attribute]

    # Nota: tras una edición estándar, el tail *no debe* reemplazarse
    if replace_tail:
        root.tail = replacement.tail
    # se reemplazan todos los hijos
    del root[:]
    for child in replacement:
        root.append(copy.deepcopy(child))

    return arch


def to_field_ref(self, el):
    """≙ ``to_field_ref`` (``odoo19c: :272-281``)."""
    # se filtra la metainformación insertada en el documento
    attributes = {k: v for k, v in el.attrib.items()
                  if not k.startswith('data-oe-')}
    attributes['t-field'] = el.get('data-oe-expression')

    out = html.html_parser.makeelement(el.tag, attrib=attributes)
    out.tail = el.tail
    return out


def to_empty_oe_structure(self, el):
    """≙ ``to_empty_oe_structure`` (``odoo19c: :283-287``)."""
    out = html.html_parser.makeelement(el.tag, attrib=el.attrib)
    out.tail = el.tail
    return out


def _set_noupdate(self):
    """≙ ``_set_noupdate`` (``odoo19c: :289-291``).

    **Divergencia:** ``model_data_id`` depende de ``ir.model.data``, que
    ``base`` declara no portar como campo de la vista (su ``key`` sí se
    porta). El resolutor de la tabla **sí** existe
    (``IrModelData._xmlid_lookup``), así que la fila se localiza por su
    ``xml_id`` y se marca igual; si no hay fila, no hay nada que marcar, que
    es lo que la fuente hace con un ``mapped`` vacío.
    """
    IrModelData = model_by_name('ir.model.data')
    if IrModelData is None:
        return
    IrModelData.objects.filter(
        model='ir.ui.view', res_id=self.pk).update(noupdate=True)


def save(self, value, xpath=None):
    """≙ ``save`` (``odoo19c: :293-352``) — *"Update a view section"*.

    La sección de vista puede llevar campos incrustados que hay que escribir.

    Nota: el registro ``self`` puede no existir al guardar un campo
    incrustado.

    :param str xpath: xpath válido a la etiqueta a reemplazar

    **Se instala como** ``save_from_html`` — ver la divergencia 2 del
    docstring del módulo. El nombre de esta función es el de la fuente; el del
    atributo, no puede serlo.
    """
    arch_section = html.fromstring(
        value, parser=html.HTMLParser(encoding='utf-8'))

    if xpath is None:
        # el valor es un campo incrustado por sí solo, no una sección de vista
        self.save_embedded_field(arch_section)
        return

    for el in self.extract_embedded_fields(arch_section):
        self.save_embedded_field(el)

        # se devuelve el campo incrustado a su forma t-field
        el.getparent().replace(el, self.to_field_ref(el))

    for el in self.extract_oe_structures(arch_section):
        if self.save_oe_structure(el):
            # se vacía la oe_structure en la vista padre
            empty = self.to_empty_oe_structure(el)
            if el == arch_section:
                arch_section = empty
            else:
                el.getparent().replace(el, empty)

    # TODO: in master, remove this.
    # This bit of code patches a view. Patching of this view is necessary
    # for some xpath in the following views if the view
    # `website.footer_copyright_company_name` has been COW after:
    #   - `website.template_footer_mega`
    #   - `website.template_footer_mega_columns`
    #   - `website.template_footer_mega_links`
    # The patch consists of adding the class `col-md` to the divs with
    # `col-sm` in the footer of the view `web.frontend_layout`, which is
    # the grand-parent of `website.layout`
    if self.key in {
        'website.footer_copyright_company_name',
        'website.template_footer_mega',
        'website.template_footer_mega_columns',
        'website.template_footer_mega_links',
    }:
        ancestor = getattr(
            getattr(getattr(self, 'inherit_id', None), 'inherit_id', None),
            'inherit_id', None)
        if ancestor is not None:
            arch = etree.fromstring(ancestor.arch_db.encode('utf-8'))
            has_change = False
            for node in arch.xpath(
                    "//div[%s]//div[%s]" % (_hasclass('o_footer_copyright'),
                                            _hasclass('col-sm'))):
                if 'col-md' not in node.get('class'):
                    node.set('class', node.get('class') + ' col-md')
                    has_change = True
            if has_change:
                ancestor.arch_db = etree.tostring(arch, encoding='unicode')
                ancestor.save()

    new_arch = self.replace_arch_section(xpath, arch_section)
    old_arch = etree.fromstring(self.arch_db.encode('utf-8'))
    if not self._are_archs_equal(old_arch, new_arch):
        self._set_noupdate()
        self.arch_db = etree.tostring(new_arch, encoding='unicode')
        self.save()
        self._copy_custom_snippet_translations(self, 'arch_db')


def _view_get_inherited_children(self, view):
    """≙ ``_view_get_inherited_children`` (``odoo19c: :354-359``).

    **Divergencia:** la fuente lee ``no_primary_children`` y
    ``__views_get_original_hierarchy`` del contexto del entorno. Este ORM no
    tiene ese contexto; los dos viajan como argumentos del recorrido, que es
    lo que :func:`_views_get` hace explícito.
    """
    return list(view.inherit_children_ids.all())


def _views_get(self, view_id, get_children=True, bundles=False, root=True,
               visited=None, original_hierarchy=None,
               no_primary_children=False):
    """≙ ``_views_get`` (``odoo19c: :364-411``).

    Para una vista ``view_id`` dada, devuelve:

    * la vista misma (empezando por su ancestro más alto)
    * todas las que heredan de ella, activas o no — pero no las hijas
      opcionales de una hija desactivada
    * todas las que llama (por ``t-call``)

    :returns: lista de ``ir.ui.view``
    """
    View = model_by_name('ir.ui.view')
    if isinstance(view_id, View):
        view = view_id
    else:
        view = View._get_template_view(view_id, raise_if_not_found=False)
    if view is None:
        _logger.warning("Could not find view object with view_id '%s'",
                        view_id)
        return []

    if visited is None:
        visited = []
    if original_hierarchy is None:
        original_hierarchy = []
    while root and view.inherit_id:
        original_hierarchy.append(view.pk)
        view = view.inherit_id

    views_to_return = [view]

    if view.arch_db and view.arch_db.strip():
        node = etree.fromstring(view.arch_db)
        xpath = "//t[@t-call]"
        if bundles:
            xpath += "| //t[@t-call-assets]"
        for child in node.xpath(xpath):
            called_view = View._get_template_view(
                child.get('t-call', child.get('t-call-assets')),
                raise_if_not_found=False)
            if called_view is None:
                continue
            if called_view not in views_to_return \
                    and called_view.pk not in visited:
                for extra in self._views_get(
                        called_view, get_children=get_children,
                        bundles=bundles,
                        visited=visited + [v.pk for v in views_to_return],
                        original_hierarchy=original_hierarchy,
                        no_primary_children=no_primary_children):
                    if extra not in views_to_return:
                        views_to_return.append(extra)

    if not get_children:
        return views_to_return

    extensions = self._view_get_inherited_children(view)
    if no_primary_children:
        extensions = [e for e in extensions
                      if e.mode != 'primary' or e.pk in original_hierarchy]

    # Las hijas se devuelven en un orden determinista, sea cual sea su
    # aplicabilidad
    for extension in sorted(extensions, key=lambda v: v.pk):
        # sólo se devuelven las nietas opcionales si esta hija está activa
        if extension.pk not in visited:
            for ext_view in self._views_get(
                    extension, get_children=extension.active, root=False,
                    visited=visited + [v.pk for v in views_to_return],
                    original_hierarchy=original_hierarchy,
                    no_primary_children=no_primary_children):
                if ext_view not in views_to_return:
                    views_to_return.append(ext_view)
    return views_to_return


def get_related_views(self, key, bundles=False):
    """≙ ``get_related_views`` (``odoo19c: :413-425``).

    Devuelve la información de las vistas que heredan de la plantilla ``key``
    (activas o no). Con ``bundles=True`` devuelve también los *bundles* de
    recursos.

    **Divergencia:** ``active_test=False`` y el borrado de ``lang`` del
    contexto son claves del entorno de la fuente. Aquí el recorrido de
    :func:`_views_get` ya no filtra por ``active`` —lo pasa como argumento— y
    no hay contexto de idioma, así que las dos claves no tienen receptor.
    """
    views = self._views_get(key, bundles=bundles)
    actor = get_current_user()
    user_groups = set(actor.groups.all()) if actor is not None else set()
    return [v for v in views
            if not v.groups.exists()
            or user_groups.intersection(v.groups.all())]


# --------------------------------------------------------------------------
# Guardado de snippets
# --------------------------------------------------------------------------


def _get_snippet_addition_view_key(self, template_key, key):
    """≙ ``_get_snippet_addition_view_key`` (``odoo19c: :431-433``)."""
    return '%s.%s' % (template_key, key)


def _snippet_save_view_values_hook(self):
    """≙ ``_snippet_save_view_values_hook`` (``odoo19c: :435-437``)."""
    return {}


def _find_available_name(self, name, used_names):
    """≙ ``_find_available_name`` (``odoo19c: :439-445``)."""
    attempt = 1
    candidate_name = name
    while candidate_name in used_names:
        attempt += 1
        candidate_name = f"{name} ({attempt})"
    return candidate_name


def save_snippet(self, name, arch, template_key, snippet_key, thumbnail_url,
                 website_id=None, model=None, field=None, res_id=None):
    """≙ ``save_snippet`` (``odoo19c: :447-528``).

    Guarda el arch de un *snippet* nuevo para que aparezca con el nombre dado
    al usar la plantilla de *snippets* indicada.

    :param name: el nombre del snippet a guardar
    :param arch: la estructura html del snippet a guardar
    :param template_key: la clave de la vista que agrupa todos los snippets
        en la que el snippet guardado debe aparecer
    :param snippet_key: la clave (sin la parte de módulo) que identifica el
        snippet del que procede el guardado
    :param thumbnail_url: la url de la miniatura a usar al mostrar el snippet

    **Divergencia:** los cuatro datos que la fuente lee del contexto
    (``website_id``, ``model``, ``field``, ``resId``) llegan aquí como
    argumentos con valor por defecto. Es el mismo dato por la vía de este
    stack: la vista DRF los recibe del cliente y los pasa.
    """
    View = model_by_name('ir.ui.view')
    app_name = template_key.split('.')[0]
    snippet_key = '%s_%s' % (snippet_key, uuid.uuid4().hex)
    full_snippet_key = '%s.%s' % (app_name, snippet_key)

    # se busca un nombre disponible
    Website = model_by_name('website')
    website_domain = django_models.Q()
    if Website is not None and website_id:
        current_website = Website.objects.filter(pk=website_id).first()
        if current_website is not None:
            website_domain = current_website.website_domain()
    used_names = list(
        View.objects.filter(django_models.Q(name__startswith=name)
                            & website_domain).values_list('name', flat=True))
    name = self._find_available_name(name, used_names)

    # de html a xml, para añadir '/' al final de las etiquetas autocerradas
    # como br, ...
    arch_tree = html.fromstring(arch)
    attributes = self._get_cleaned_non_editing_attributes(
        arch_tree.attrib.items())
    for attr in list(arch_tree.attrib):
        if attr in attributes:
            arch_tree.attrib[attr] = attributes[attr]
        else:
            del arch_tree.attrib[attr]
    xml_arch = etree.tostring(arch_tree, encoding='unicode')
    new_snippet_view_values = {
        'name': name,
        'key': full_snippet_key,
        'type': 'qweb',
        'arch_db': xml_arch,
    }
    new_snippet_view_values.update(self._snippet_save_view_values_hook())
    custom_snippet_view = View.objects.create(**new_snippet_view_values)
    if field == 'arch':
        # Caso especial para `arch`, que es una especie de related (por un
        # compute) de `arch_db` pero que aloja contenido XML/HTML siendo un
        # campo char. Eso confunde a la llamada a get_translation_dictionary,
        # que devuelve XML en vez de cadenas.
        field = 'arch_db'
    if model and field and res_id:
        source = model_by_name(model).objects.filter(pk=int(res_id)).first()
        if source is not None:
            self._copy_field_terms_translations(
                source, field, custom_snippet_view, 'arch_db')

    custom_section = View.objects.filter(key=template_key).first()
    snippet_addition_view_values = {
        'name': name + ' Block',
        'key': self._get_snippet_addition_view_key(template_key, snippet_key),
        'inherit_id': custom_section,
        'type': 'qweb',
        'arch_db': """
            <data inherit_id="%s">
                <xpath expr="//snippets[@id='snippet_custom']" position="inside">
                    <t t-snippet="%s" t-thumbnail="%s"/>
                </xpath>
            </data>
        """ % (template_key, full_snippet_key, thumbnail_url),
    }
    snippet_addition_view_values.update(self._snippet_save_view_values_hook())
    View.objects.create(**snippet_addition_view_values)
    return name


def rename_snippet(self, name, view_id, template_key):
    """≙ ``rename_snippet`` (``odoo19c: :530-538``)."""
    View = model_by_name('ir.ui.view')
    snippet_view = View.objects.filter(pk=view_id).first()
    key = snippet_view.key.split('.')[1]
    custom_key = self._get_snippet_addition_view_key(template_key, key)
    snippet_addition_view = View.objects.filter(key=custom_key).first()
    if snippet_addition_view:
        snippet_addition_view.name = name + ' Block'
        snippet_addition_view.save()
    snippet_view.name = name
    snippet_view.save()


def delete_snippet(self, view_id, template_key):
    """≙ ``delete_snippet`` (``odoo19c: :540-546``)."""
    View = model_by_name('ir.ui.view')
    snippet_view = View.objects.filter(pk=view_id).first()
    key = snippet_view.key.split('.')[1]
    custom_key = self._get_snippet_addition_view_key(template_key, key)
    View.objects.filter(
        django_models.Q(key=custom_key) | django_models.Q(pk=view_id)
    ).delete()


def apply_html_editor_extensions():
    """Cuelga los veinticinco métodos sobre ``base.IrUiView`` — ≙ ``_inherit``.

    ``save`` se instala como ``save_from_html``: ver la divergencia 2.
    """
    # El destino se escribe **literal** y no por la constante: ver la nota de
    # ``ir_attachment.py`` — ``extend_model`` es una declaración estática y una
    # variable la vuelve ilegible para ``check_porte_completo``.
    extend_model(
        'ir.ui.view',
        metodos={
            '_get_cleaned_non_editing_attributes':
                _get_cleaned_non_editing_attributes,
            'extract_embedded_fields': extract_embedded_fields,
            'extract_oe_structures': extract_oe_structures,
            'get_default_lang_code': get_default_lang_code,
            'save_embedded_field': save_embedded_field,
            'save_oe_structure': save_oe_structure,
            '_copy_custom_snippet_translations':
                _copy_custom_snippet_translations,
            '_copy_field_terms_translations': _copy_field_terms_translations,
            '_save_oe_structure_hook': _save_oe_structure_hook,
            '_are_archs_equal': _are_archs_equal,
            '_get_allowed_root_attrs': _get_allowed_root_attrs,
            'replace_arch_section': replace_arch_section,
            'to_field_ref': to_field_ref,
            'to_empty_oe_structure': to_empty_oe_structure,
            '_set_noupdate': _set_noupdate,
            'save_from_html': save,
            '_view_get_inherited_children': _view_get_inherited_children,
            '_views_get': _views_get,
            'get_related_views': get_related_views,
            '_get_snippet_addition_view_key': _get_snippet_addition_view_key,
            '_snippet_save_view_values_hook': _snippet_save_view_values_hook,
            '_find_available_name': _find_available_name,
            'save_snippet': save_snippet,
            'rename_snippet': rename_snippet,
            'delete_snippet': delete_snippet,
        },
    )
