"""``ir.ui.view`` — lo que el addon del sitio le cuelga a la vista.

Adaptación de Odoo ``addons/website/models/ir_ui_view.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 542 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03). Mismo nombre de archivo que la
referencia (tarea **#565**; segunda cláusula de
``atributos-de-clase-de-modelo.md``).

Esto **no es un modelo**: es la *extensión* que ``website`` cuelga sobre el
``ir.ui.view`` que ya vive en ``src/addons/base/models/ir_ui_view.py``. La
fuente lo dice en su cabecera —``_inherit = ["ir.ui.view", …]`` sin declarar
tabla propia— y aquí lo expresa ``extend_model`` más el modelo lateral
``WebsiteViewInfo`` (D-1).

Contrato medido de la fuente (AST, una sola clase ``IrUiView``): **10
atributos de clase (2 de ORM + 8 campos) y 36 métodos**.

Porte BLOQUEADO — 12 de 36 símbolos

**12 métodos portados, 24 bloqueados**; cada bloqueado lleva su arista con la
forma fija en su propio sitio, más abajo. Las cuatro causas son:

.. warning::

   **Un conteo AST ingenuo dice 13 y se equivoca.** Este módulo define un
   ``save`` —el de ``WebsiteViewInfo``, que es ``Model.save`` de Django más el
   invariante de ``visibility``— y la fuente define **otro** ``save``, el del
   editor de arquitectura (``odoo19c: :484-507``). Comparten nombre y no son
   el mismo símbolo: el de la fuente sigue **bloqueado**, con su arista en el
   bloque (c). Es el "conteo generoso" que ``porte-completo-no-parcial.md``
   advierte — *un método cuenta como portado cuando hace lo que hace el de la
   referencia*, no cuando existe uno con nombre parecido.

- **la maquinaria COW/COU** (6 métodos) — copiar la vista genérica al escribir
  en contexto de un sitio. Necesita el clon de registro que este ORM no trae y
  la columna ``website_id`` **en la propia vista**, que D-1 desplaza a la tabla
  lateral;
- **el método base ausente** (12 métodos) — el cuerpo de la fuente es
  ``super()`` más un delta; sin la implementación de ``base`` sobre la que
  encadenar, instalar sólo el delta devolvería una respuesta parcial que nada
  delata;
- **la superficie del editor** (5 métodos) — guardar arquitectura desde el
  frontal, los ganchos de *snippet* y el ``noupdate`` del cargador de datos;
- **el registro por external ID** (1 método, #467).

Los 10 atributos de clase de la fuente
=======================================

.. list-table::
   :header-rows: 1
   :widths: 32 10 58

   * - Atributo (línea)
     - Estado
     - Forma aquí
   * - ``_name`` (``:16``)
     - portado
     - lo expresa el destino de ``extend_model('base', 'IrUiView', …)``
   * - ``_inherit`` (``:18``)
     - **parcial**
     - su primer elemento es ese mismo destino; el segundo,
       ``website.seo.metadata``, va abajo con su arista
   * - ``website_id`` (``:20``)
     - portado
     - ``WebsiteViewInfo.website`` (D-1) + propiedad ``website`` de lectura
   * - ``page_ids`` (``:21``)
     - **ya existía**
     - es el reverso de ``website.page.view``
       (``related_name='page_ids'``, portado por #104); un segundo
       ``One2many`` duplicaría la relación
   * - ``controller_page_ids`` (``:22``)
     - bloqueado
     - BLOQUEADO por ``website.controller.page`` — el modelo no existe en
       este árbol (misma arista que ``website_menu.py:87``). Sucesor:
       tarea **#565** deja el hueco; lo cierra quien porte ese modelo
   * - ``first_page_id`` (``:23``)
     - portado
     - ``fields.NonStored`` (``compute`` sin ``store``) alimentado por
       ``_compute_first_page_id``
   * - ``track`` (``:24``)
     - portado
     - ``WebsiteViewInfo.track`` (D-1) + propiedad ``track``
   * - ``visibility`` (``:25-33``)
     - portado
     - ``WebsiteViewInfo.visibility`` (D-1) + propiedad ``visibility``
   * - ``visibility_password`` (``:34``)
     - portado
     - ``WebsiteViewInfo.visibility_password`` (D-1) + propiedad
   * - ``visibility_password_display`` (``:35``)
     - portado
     - ``property(_get_pwd, _set_pwd)`` — el par ``compute``/``inverse`` de
       la fuente, con los dos métodos conservando su nombre (D-4)

Divergencias declaradas
========================

**D-1 — los cuatro campos con columna viven en una tabla lateral.** La fuente
añade ``website_id``, ``track``, ``visibility`` y ``visibility_password`` como
**columnas de ``ir_ui_view``**. Aquí ``ir.ui.view`` pertenece a la app
``base`` y este addon es la app ``website``: un campo colgado por
``extend_model(campos=…)`` sobre un modelo ajeno produce su ``AddField`` en
las migraciones de **la app del modelo**, no de la que lo cuelga —
``django/db/migrations/autodetector.py`` indexa cada operación por
``(app_label, model_name)`` del propio modelo. La migración caería en
``src/addons/base/migrations/``, fuera de este addon.

Por eso la forma es la que este árbol ya fija para la extensión *con columnas*
entre apps: **modelo RELATED uno-a-uno** (DEC-SALE-01), el mismo mecanismo de
``WebsiteSaleOrderInfo`` sobre ``sale.order`` y de los cuatro de
``account_payment/models/links.py``. La ausencia de fila significa
exactamente lo que en la fuente significa el vacío de esos cuatro campos: sin
sitio, sin seguimiento, pública y sin contraseña.

Coste real de la divergencia, y se declara porque no es cosmético: los cuatro
**no se pueden filtrar como columna de la vista**. Un
``Domain('visibility', '=', False)`` de la fuente se escribe aquí contra el
JOIN inverso —``view__website_info__visibility``— y tiene que contar además la
fila ausente. Los consumidores que lo hacen lo dejan escrito en su sitio
(``website.py::_enumerate_pages``, ``website_page.py::_search_get_detail``).

**D-2 — el ``compute`` devuelve el valor en vez de asignarlo al recordset.**
Misma divergencia 3 que ``website_page.py`` declara para sus cinco
``NonStored``: ``_compute_first_page_id`` **devuelve** la página en lugar de
escribir ``view.first_page_id = …`` sobre cada registro del recordset.

**D-3 — ``filter_duplicate`` recibe la colección.** La fuente es un método de
recordset (``self.filtered(…)``); aquí no hay recordset, así que es un
``classmethod`` que toma el iterable de vistas y devuelve una **lista**. Es la
misma traducción que ``WebsiteSearchableMixin`` ya declara para sus tres
métodos.

**D-4 — el ``inverse`` recibe el valor.** ``_set_pwd`` en la fuente lee
``r.visibility_password_display`` del caché de campos, porque el ORM ya guardó
ahí lo que se va a escribir. Sin ese caché, el *setter* recibe el valor
explícito. Los dos nombres se conservan verbatim (H-API-581: el guion bajo es
el contrato, no decoración).

**D-5 — el hash de contraseña sale de ``django.contrib.auth.hashers``.** La
fuente usa ``self.env.user._crypt_context()`` (passlib). Este árbol no tiene
ese método y sí el motor de hashing de Django, que es el que
``ResUsers.set_password`` / ``check_password`` ya usan
(``src/addons/base/models/res_users.py:345-356``). Adaptar el mecanismo al de
la plataforma es lo que ``porte-completo-no-parcial.md`` manda; inventar un
``_crypt_context`` sería un nombre sin motor detrás.

**D-6 — el 403 es ``exceptions.AccessError``.** La fuente levanta
``werkzeug.exceptions.Forbidden``; aquí ``AccessError`` **es**
``django.core.exceptions.PermissionDenied`` (``src/exceptions.py:77``), que el
manejador de DRF traduce a 403. La cadena
``'website_visibility_password_required'`` se conserva **verbatim** como
mensaje: es el discriminante que el frontal lee para pedir la contraseña.

**D-7 — sin ``tools.ormcache``.** Igual que en ``website_page.py``
(divergencia 5): ``_get_cached_visibility`` y la familia de plantillas
calculan siempre. La decisión de caché bajo *prefork* es la tarea #542.
"""
import logging

import fields
import models
from django.contrib.auth import hashers

from addons.base.models import TimeStampedModel
from addons.base.models.ir_http import get_current_request
from addons.website.models.website import Website
from exceptions import AccessError, MissingError
from orm.environments import get_context, get_current_user
from orm.method_chain import chain_method, extend_list
from orm.model_classes import extend_model

#: ≙ ``_logger = logging.getLogger(__name__)`` (``odoo19c: :12``). La fuente lo
#: declara y **no lo usa** en este archivo (medido: una sola aparición); se
#: porta igual porque es parte de la cabecera del módulo, con el nombre sin
#: guion bajo que ``website.py`` ya fija en este addon.
logger = logging.getLogger(__name__)

#: ≙ el ``selection`` de ``visibility`` (``odoo19c: :26-31``), verbatim.
VISIBILITY_CHOICES = [
    ('', 'Public'),
    ('connected', 'Signed In'),
    ('restricted_group', 'Restricted Group'),
    ('password', 'With Password'),
]

#: El grupo que se salta el control de visibilidad (``odoo19c: :415``).
GROUP_WEBSITE_DESIGNER = 'website.group_website_designer'


class WebsiteViewInfo(TimeStampedModel):
    """Lo que ``website`` añade a ``ir.ui.view`` y **sí** tiene columna.

    Uno a uno con la vista: en la fuente son columnas de ``ir_ui_view``, así
    que no puede haber dos juegos para la misma vista. Ver D-1 del docstring
    del módulo para por qué es una tabla aparte y qué cuesta.

    Su ausencia significa *"esta vista es genérica, pública, sin contraseña y
    sin seguimiento"* — que es exactamente lo que los cuatro campos vacíos
    significan en la referencia.
    """

    view = models.OneToOneField(
        'base.IrUiView', on_delete=models.CASCADE,
        related_name='website_info',
        help_text='Vista a la que pertenece esta información (Odoo _inherit '
                  'ir.ui.view).',
    )
    website = fields.Many2one(
        Website, on_delete=models.CASCADE, null=True, blank=True,
        db_index=True, related_name='views',
        help_text='Sitio dueño de la vista; vacío = genérica, compartida por '
                  'todos (Odoo website_id, ondelete=cascade).',
    )
    track = fields.Boolean(
        default=False,
        verbose_name='Con seguimiento',
        help_text='Permite marcar una página del sitio como rastreable '
                  '(Odoo track).',
    )
    visibility = fields.Selection(
        max_length=16, choices=VISIBILITY_CHOICES, blank=True, default='',
        verbose_name='Visibilidad',
        help_text='Quién puede ver la página: pública, con sesión, con grupo '
                  'restringido o con contraseña (Odoo visibility).',
    )
    visibility_password = fields.Char(
        max_length=128, blank=True, default='',
        verbose_name='Contraseña de visibilidad',
        help_text='Hash de la contraseña con que se desbloquea la página '
                  '(Odoo visibility_password, groups=base.group_system, '
                  'copy=False).',
    )

    class Meta:
        db_table = 'website_ir_ui_view_info'
        ordering = ['view_id']
        verbose_name = 'Datos de sitio de la vista'
        verbose_name_plural = 'Datos de sitio de las vistas'

    def __str__(self):
        return 'Sitio — vista %s' % self.view_id

    @classmethod
    def from_db(cls, db, field_names, values):
        """Recuerda la ``visibility`` con que la fila llegó de la base.

        El disparador de la fuente es *"``visibility`` viene en el ``vals``"*,
        no *"se guardó la fila"*. Django no expone el ``vals`` de una escritura
        —``objects.create(view=v)`` y ``objects.create(view=v, visibility='')``
        producen la misma instancia—, así que el equivalente medible es
        **el valor cambió** respecto del persistido. Ver ``save()``.
        """
        instance = super().from_db(db, field_names, values)
        if field_names is not None and 'visibility' in field_names:
            instance._visibility_loaded = instance.visibility
        return instance

    _visibility_loaded = None

    def save(self, *args, **kwargs):
        """Escribe la fila y aplica el invariante de ``visibility``.

        ≙ la rama de ``website.page.write`` de la fuente
        (``odoo19c: website/models/website_page.py:188-190``)::

            if 'visibility' in vals:
                if vals['visibility'] != 'restricted_group':
                    vals['group_ids'] = False

        **Divergencia de sitio, declarada.** Allá la rama vive en la escritura
        de la *página* porque los dos campos le llegan por la delegación
        ``_inherits`` y viajan en el mismo ``vals``. Aquí ``visibility`` es
        columna de esta tabla y ``group_ids`` es el ``groups`` del ``ir.ui.view``
        **base** (``src/addons/base/models/ir_ui_view.py:229``): la página no
        los escribe nunca, así que el disparador de la fuente —"llegó
        ``visibility`` en el ``vals``"— sólo existe aquí, donde se escribe.

        Ponerlo en ``WebsitePage.save`` habría obligado a aplicarlo en cada
        guardado de página, sin señal de escritura, borrando grupos que la
        vista pudiera llevar por el control de acceso genérico —que en la
        referencia es otro asunto que el de la visibilidad—. El efecto se
        conserva; el sitio cambia.

        **El disparador es la escritura de ``visibility``, no el guardado.**
        La fuente entra al ``if`` sólo cuando la clave viaja en el ``vals``;
        aplicarlo en todo ``save()`` borraba los grupos de la vista al
        materializar la fila lateral con su visibilidad por defecto, que allá
        no es escritura de nada. Aquí eso se mide como *el valor cambió*
        respecto del persistido (ver ``from_db``), o como ``visibility``
        nombrada en un ``update_fields`` explícito — que es el caso en que
        quien escribe sí declara la clave.
        """
        update_fields = kwargs.get('update_fields')
        if update_fields is None and len(args) >= 4:
            update_fields = args[3]
        declared = update_fields is not None and 'visibility' in update_fields
        changed = self.visibility != (self._visibility_loaded or '')
        result = super().save(*args, **kwargs)
        if (declared or changed) and self.visibility != 'restricted_group' \
                and self.view_id:
            self.view.groups.clear()
        self._visibility_loaded = self.visibility
        return result


def _info_of(view):
    """La fila lateral de la vista, o ``None`` si no la tiene.

    Símbolo **nuestro**: la fuente lee ``view.visibility`` directamente porque
    allá la columna es de la vista. Existe por D-1, y se centraliza porque el
    acceso inverso de un ``OneToOneField`` ausente levanta en vez de devolver
    ``None``.

    **Una vista sin ``pk`` no tiene fila lateral, y leerla no es un error.**
    En la fuente los cuatro campos son columnas del propio registro, así que
    leerlos sobre uno en memoria devuelve su valor por defecto sin tocar la
    base. Aquí la consulta por FK levantaría ``ValueError: Model instances
    passed to related filters must be saved.`` — la lectura pasaría de
    devolver un defecto a reventar, que es una divergencia de conducta, no de
    mecanismo. El guard la cierra: sin ``pk``, no hay fila.
    """
    if view is None or view.pk is None:
        return None
    return WebsiteViewInfo.objects.filter(view=view).first()


def _info_for_write(view):
    """La fila lateral de la vista, creándola si no existe.

    Símbolo **nuestro** (D-1): escribir uno de los cuatro campos en la fuente
    es escribir una columna que siempre está; aquí puede haber que materializar
    la fila primero.
    """
    info, _created = WebsiteViewInfo.objects.get_or_create(view=view)
    return info


# ══════════════════════════════════════════════════════════════════════════
#  Los 12 símbolos portados
# ══════════════════════════════════════════════════════════════════════════

def _get_pwd(self):
    """≙ ``_get_pwd`` (``@api.depends('visibility_password')``,
    ``odoo19c: :37-40``).

    Lo que se enseña en lugar de la contraseña: ocho asteriscos si hay una, y
    la cadena vacía si no. El ``sudo()`` de la fuente protege la lectura de
    ``visibility_password`` (declarado ``groups='base.group_system'``); aquí
    la fila lateral no lleva restricción por grupo —el motor de grupos por
    external ID es #467— así que la lectura es directa y **no se finge** un
    ``sudo`` que no recorta nada.
    """
    info = _info_of(self)
    return '********' if info and info.visibility_password else ''


def _set_pwd(self, value):
    """≙ ``_set_pwd`` (``odoo19c: :41-46``) — el ``inverse`` del par.

    Guarda el **hash** de lo que se escribió en el campo de presentación, y
    sólo para vistas QWeb, verbatim el ``if r.type == 'qweb'`` de la fuente.
    Un valor vacío borra el hash.

    Divergencias: **D-4** (el valor llega explícito, no por el caché de
    campos) y **D-5** (el hash sale de ``django.contrib.auth.hashers``, no de
    passlib). La relectura ``r.visibility = r.visibility`` de la fuente —cuyo
    comentario dice *"double check access"*— no se porta: su efecto es
    disparar el control de acceso por grupo del ORM al escribir, y ese motor
    es #467; una asignación a sí mismo sin él sería una línea sin conducta.
    """
    if self.type != 'qweb':
        return
    info = _info_for_write(self)
    info.visibility_password = hashers.make_password(value) if value else ''
    info.save(update_fields=['visibility_password'])


def _compute_first_page_id(self):
    """≙ ``_compute_first_page_id`` (``odoo19c: :48-51``).

    La primera ``website.page`` que usa esta vista, o ``None``. Divergencia
    **D-2**: devuelve el valor en vez de asignarlo sobre el recordset.
    """
    return self.page_ids.order_by('pk').first()


def get_view_hierarchy(self):
    """≙ ``get_view_hierarchy`` (``odoo19c: :245-255``).

    El árbol completo al que pertenece la vista: se sube hasta la raíz por
    ``inherit_id``, se listan sus hermanas —las que comparten ``key`` y no son
    ella— y se devuelve el árbol de la raíz.

    Divergencia declarada: la fuente usa ``search_read`` (recordset →
    diccionarios) y ``with_context(active_test=False)``; aquí es un
    ``values()`` sobre el queryset, que ya no filtra por ``active``, así que
    el contexto no hace falta.
    """
    top_level_view = self
    while top_level_view.inherit_id is not None:
        top_level_view = top_level_view.inherit_id
    sibling_views = list(
        type(self).objects
        .filter(key=top_level_view.key)
        .exclude(pk=top_level_view.pk)
        .values())
    return {
        'sibling_views': sibling_views,
        'hierarchy': top_level_view._build_hierarchy_datastructure(),
    }


def _build_hierarchy_datastructure(self):
    """≙ ``_build_hierarchy_datastructure`` (``odoo19c: :257-270``).

    El árbol de herencia de la vista como diccionarios anidados, con las
    siete claves de la fuente y en su orden. ``website_name`` sale de la fila
    lateral (D-1): sin fila, la vista es genérica y la clave vale ``False``,
    igual que allá cuando ``website_id`` está vacío.
    """
    inherit_children = [
        child._build_hierarchy_datastructure()
        for child in self.inherit_children_ids.all()
    ]
    info = _info_of(self)
    website = info.website if info else None
    return {
        'id': self.pk,
        'name': self.name,
        'inherit_children': inherit_children,
        'arch_updated': self.arch_updated,
        'website_name': website.name if website else False,
        'active': self.active,
        'key': self.key,
    }


def filter_duplicate(cls, views):
    """≙ ``filter_duplicate`` (``odoo19c: :287-311``).

    *"Filter current recordset only keeping the most suitable view per
    distinct key"* — verbatim el criterio de la fuente:

    * fuera de contexto de sitio se quedan **sólo las genéricas**;
    * dentro de un sitio, las suyas, más las genéricas cuya ``key`` no tenga
      ya una específica.

    Divergencia **D-3**: recibe el iterable y devuelve una lista.
    """
    current_website_id = get_context().get('website_id')
    view_list = list(views)
    website_of = {view.pk: _info_of(view) for view in view_list}

    def website_id_of(view):
        info = website_of.get(view.pk)
        return info.website_id if info else None

    if not current_website_id:
        return [view for view in view_list if not website_id_of(view)]

    specific_views_keys = {
        view.key for view in view_list
        if website_id_of(view) == current_website_id and view.key
    }
    most_specific_views = []
    for view in view_list:
        website_id = website_id_of(view)
        # Específica: entra si es del sitio actual, y se ignora si es de otro.
        if website_id and website_id == current_website_id:
            most_specific_views.append(view)
        # Genérica: entra sólo si, para el sitio actual, no hay una específica
        # con la misma ``key``.
        elif not website_id and view.key not in specific_views_keys:
            most_specific_views.append(view)
    return most_specific_views


def _get_cached_template_prefetched_keys(cls):
    """≙ ``_get_cached_template_prefetched_keys`` (``odoo19c: :363-365``).

    Los tres campos que el addon del sitio suma a los que ``base`` publica
    (``id``, ``key``, ``active``). Se instala con ``combine=extend_list``, que
    es el ``super() + [...]`` de la fuente: primero lo que ya había, después
    lo del addon.

    ``base`` ya lo dejaba anotado como punto de extensión
    (``src/addons/base/models/ir_ui_view.py:427-433``).

    **``'active'`` sale repetido, y es fiel.** ``base`` ya lo publica
    (``['id', 'key', 'active']``) y la fuente vuelve a añadirlo, así que allá
    la lista resultante es
    ``['id', 'key', 'active', 'active', 'visibility', 'track']`` —
    ``odoo19c: odoo/addons/base/models/ir_ui_view.py:1121-1122`` frente a
    ``odoo19c: addons/website/models/ir_ui_view.py:364``. Se conserva: quien
    la deduplique estará divergiendo de la referencia, no arreglando nada.
    """
    return ['active', 'visibility', 'track']


def _get_template_domain(cls, xmlids):
    """≙ ``_get_template_domain`` (``odoo19c: :370-383``).

    Estrecha el dominio de ``base`` al sitio del contexto: *"try to get the id
    of the specific view for that website, but fallback to the id of the
    generic view if there is no specific. If no website_id is in the context,
    every view with a website will be filtered out"*.

    Divergencia **D-1**: el ``('website_id','in',(False, ctx))`` de la fuente
    es aquí una condición sobre el JOIN inverso, y la fila **ausente** es el
    caso genérico —``website_info__isnull=True``—, no un ``NULL`` de columna.
    Se instala con ``combine`` de conjunción, que es el ``&`` de la fuente.
    """
    website_id = get_context().get('website_id')
    generic = models.Q(website_info__isnull=True)
    if not website_id:
        return generic
    return generic | models.Q(website_info__website_id=website_id)


def _get_template_order(cls):
    """≙ ``_get_template_order`` (``odoo19c: :393-394``).

    Antepone el sitio al orden de ``base``: entre dos vistas con la misma
    ``key``, gana la del sitio. En PostgreSQL el ``ASC`` deja los nulos al
    final, así que la genérica queda detrás de la específica — el mismo efecto
    que el ``"website_id asc, …"`` de la fuente.

    Divergencia de forma ya declarada por ``base``: se devuelve la tupla que
    consume ``order_by``, no la cadena SQL. Se instala con ``combine`` de
    concatenación (lo nuevo delante, como la interpolación de la fuente).
    """
    return ('website_info__website_id',)


def _fetch_template_views(cls, ids_or_xmlids):
    """≙ ``_fetch_template_views`` (``odoo19c: :385-391``).

    Añade el sitio al mensaje de las plantillas que no se encontraron —
    *"%(error)s (website: %(website_id)s)"*, verbatim.

    Divergencia de forma: ``chain_method`` llama primero a esta función y
    después a la de ``base``, así que lo que se calcula aquí es **el dato
    nuevo** (el sitio del contexto) y la fusión la hace el ``combine``, que
    recibe el diccionario ya resuelto por ``base``. La fuente lo escribe al
    revés porque su ``super()`` corre dentro del cuerpo.
    """
    return get_context().get('website_id')


def _add_website_to_missing(website_id, data):
    """``combine`` de :func:`_fetch_template_views` — reescribe los ausentes.

    Símbolo **nuestro**: es la mitad del método de la fuente que corre
    *después* del ``super()``. Se separa porque el encadenado de este árbol
    invierte el orden (ver el docstring de arriba).
    """
    for key in list(data):
        if isinstance(data[key], MissingError):
            data[key] = MissingError(
                '%s (website: %s)' % (data[key], website_id))
    return data


def _get_cached_visibility(self):
    """≙ ``_get_cached_visibility`` (``odoo19c: :396-401``).

    La visibilidad que declara la vista, levantando el error que la resolución
    de plantilla haya dejado en el dict. Sin ``ormcache`` (**D-7**): el
    ``_get_cached_template_info`` de ``base`` calcula siempre.
    """
    info = type(self)._get_cached_template_info(self.pk, _view=self)
    if info['error']:
        raise info['error']
    return info['visibility']


def _handle_visibility(self, do_raise=True):
    """≙ ``_handle_visibility`` (``odoo19c: :402-436``).

    *"Check the visibility set on the main view and raise 403 if you should
    not have access. Order is: Public, Connected, Has group, Password"* —
    verbatim. Sólo mira el contenido principal; las demás vistas que se
    invoquen siguen disponibles.

    El ``self.sudo()`` de la fuente eleva para poder leer
    ``visibility_password`` (restringido por grupo allá). Aquí la fila lateral
    no lleva ese recorte —el motor de grupos por external ID es #467— y la
    elevación no cambiaría nada, así que **no se finge** (mismo criterio que
    ``_get_pwd``).

    Divergencias **D-5** (hash por ``hashers``) y **D-6** (``AccessError``,
    con la cadena discriminante intacta). Y una rama declarada:

    El tramo ``if visibility not in ('password', 'connected')`` de la fuente
    —el que llama a ``self._check_view_access()`` y traduce su ``AccessError``
    a un 403— está BLOQUEADO por ``ir.ui.view._check_view_access`` — ``base``
    no lo porta y el motor de grupos por external ID que lo alimenta es #467.
    Sin él, ``restricted_group`` no recorta y la vista se sirve; con el motor,
    el tramo vuelve tal cual. Sucesor: tarea **#565** lo deja anotado, lo
    cierra quien porte ``_check_view_access``.
    """
    error = False
    request = get_current_request()
    visibility = self._get_cached_visibility()
    user = get_current_user()
    is_designer = bool(user and user.has_group(GROUP_WEBSITE_DESIGNER))

    if visibility and not is_designer:
        session = getattr(request, 'session', None) if request else None
        unlocked = list(session.get('views_unlock', [])) if session else []
        if visibility == 'connected' and Website.is_public_user():
            error = AccessError('Forbidden')
        elif visibility == 'password' and (
                Website.is_public_user() or self.pk not in unlocked):
            pwd = _password_from(request)
            info = _info_of(self)
            stored = info.visibility_password if info else ''
            if pwd and stored and hashers.check_password(pwd, stored):
                unlocked.append(self.pk)
                if session is not None:
                    session['views_unlock'] = unlocked
            else:
                error = AccessError('website_visibility_password_required')

    if error:
        if do_raise:
            raise error
        return False
    return True


def _password_from(request):
    """La contraseña que trae la petición — ≙ ``request.params.get(…)``.

    Símbolo **nuestro**: la fuente lee ``request.params``, el diccionario
    unificado de werkzeug. En Django los parámetros llegan repartidos entre
    ``POST`` y ``GET``, y el orden replica al de aquél: el cuerpo gana sobre
    la cadena de consulta.
    """
    if request is None:
        return None
    for source in ('POST', 'GET'):
        params = getattr(request, source, None)
        if params and params.get('visibility_password'):
            return params.get('visibility_password')
    return None


# ══════════════════════════════════════════════════════════════════════════
#  Las propiedades de lectura de los cuatro campos laterales (D-1)
# ══════════════════════════════════════════════════════════════════════════

def _website_property(self):
    """``website_id`` de la fuente (``:20``), en lectura desde la fila lateral."""
    info = _info_of(self)
    return info.website if info else None


def _track_property(self):
    """``track`` de la fuente (``:24``); sin fila lateral, ``False``."""
    info = _info_of(self)
    return info.track if info else False


def _visibility_property(self):
    """``visibility`` de la fuente (``:25``); sin fila lateral, ``''`` (pública)."""
    info = _info_of(self)
    return info.visibility if info else ''


def _visibility_password_property(self):
    """``visibility_password`` de la fuente (``:34``); sin fila lateral, ``''``."""
    info = _info_of(self)
    return info.visibility_password if info else ''


# ══════════════════════════════════════════════════════════════════════════
#  Los 24 símbolos NO portados — una arista por cada uno
# ══════════════════════════════════════════════════════════════════════════
#
# (a) La maquinaria COW / COU — 6 símbolos.
#
#   ``create`` (``:53-79``), ``write`` (``:92-168``), ``unlink`` (``:213-235``),
#   ``_load_records_write_on_cow`` (``:170-176``),
#   ``_create_all_specific_views`` (``:178-211``) y
#   ``_create_website_specific_pages_for_view`` (``:237-244``):
#   BLOQUEADOS por ``ir.ui.view.website_id`` — la copia-al-escribir opera sobre
#   la columna del sitio **en la propia vista** (busca la específica por
#   ``('website_id','=',ctx)``, la crea con ``copy()`` conservando la ``key``, y
#   reengancha el árbol de hijas). D-1 desplaza esa columna a la tabla lateral y
#   este ORM no trae el clon de registro, así que el mecanismo no tiene sobre
#   qué operar. Sucesor: tarea **#565** lo deja anotado; lo cierra quien decida
#   si la columna vuelve a ``ir_ui_view`` (migración en ``base``) o si la COW se
#   reescribe contra la fila lateral.
#
# (b) El método de ``base`` sobre el que encadenar no existe — 12 símbolos.
#     El cuerpo de la fuente es ``super()`` más un delta; instalar sólo el delta
#     devolvería una respuesta parcial sin que nada lo delate.
#
#   ``_compute_display_name`` (``:80-91``):
#     BLOQUEADO por ``ir.ui.view._compute_display_name`` — ``base`` sólo trae
#     ``__str__`` y no hay ``display_name``.
#   ``get_related_views`` (``:272-286``):
#     BLOQUEADO por ``ir.ui.view.get_related_views``.
#   ``_view_get_inherited_children`` (``:313-317``):
#     BLOQUEADO por ``ir.ui.view._view_get_inherited_children``.
#   ``_get_inheriting_views_domain`` (``:318-328``):
#     BLOQUEADO por ``ir.ui.view._get_inheriting_views_domain``.
#   ``_get_inheriting_views`` (``:329-337``):
#     BLOQUEADO por ``ir.ui.view._get_inheriting_views`` — ``base`` trae
#     ``inheriting_views``, que resuelve el árbol de una vista dada y **no** es
#     el mismo símbolo (otra firma, otro consumidor).
#   ``_get_template_minimal_cache_keys`` (``:366-368``):
#     BLOQUEADO por ``ir.ui.view._get_template_minimal_cache_keys``.
#   ``render_public_asset`` (``:437-445``):
#     BLOQUEADO por ``ir.ui.view.render_public_asset``.
#   ``_render_template`` (``:447-457``):
#     BLOQUEADO por ``ir.ui.view._render_template`` — el motor de render QWeb
#     no está en este árbol (las páginas se sirven por DRF + React).
#   ``get_default_lang_code`` (``:458-465``):
#     BLOQUEADO por ``ir.ui.view.get_default_lang_code``.
#   ``_read_template_keys`` (``:466-467``):
#     BLOQUEADO por ``ir.ui.view._read_template_keys``.
#   ``_update_field_translations`` (``:532-533``):
#     BLOQUEADO por ``ir.ui.view._update_field_translations``.
#   ``_get_base_lang`` (``:535-541``):
#     BLOQUEADO por ``ir.ui.view._get_base_lang``.
#
# (c) La superficie del editor — 5 símbolos.
#
#   ``save`` (``:484-507``):
#     BLOQUEADO por ``ir.ui.view.save``.
#   ``_save_oe_structure_hook`` (``:470-475``):
#     BLOQUEADO por ``ir.ui.view._save_oe_structure_hook``.
#   ``_snippet_save_view_values_hook`` (``:525-531``):
#     BLOQUEADO por ``ir.ui.view._snippet_save_view_values_hook``.
#   ``_get_allowed_root_attrs`` (``:508-523``):
#     BLOQUEADO por ``ir.ui.view._get_allowed_root_attrs``.
#   ``_set_noupdate`` (``:476-483``):
#     BLOQUEADO por ``ir.ui.view._set_noupdate`` — y su condición, el
#     ``noupdate`` del cargador de datos, tampoco existe.
#
# (d) El registro por external ID — 1 símbolo.
#
#   ``_get_filter_xmlid_query`` (``:338-362``):
#     BLOQUEADO por ``ir.model.data`` — la consulta une ``ir_model_data`` con
#     las vistas específicas por ``key``; el registro de datos por external ID
#     es la tarea #467.
#
# Y el segundo elemento del ``_inherit`` de la cabecera (``:18``):
#   BLOQUEADO por ``website.seo.metadata`` — el mixin de metadatos SEO/OG vive
#   en ``odoo19c: website/models/mixins.py:20-159`` y **no** en este archivo;
#   #561 portó de ese módulo sólo el par de opciones de página. De él viene
#   ``get_website_meta``, que ``website_page.py:510`` atribuye hoy a esta
#   extensión. Sucesor: quien porte ``website.seo.metadata``.


def apply_website_ir_ui_view_extensions():
    """Cuelga sobre ``ir.ui.view`` lo que el sitio le añade — ≙ ``_inherit``.

    Se invoca desde ``WebsiteConfig.ready()``: en tiempo de import el registro
    de modelos aún no está poblado.

    El destino se nombra con el par de Django y no con ``'ir.ui.view'`` porque
    el nombre punteado exige que el modelo ya esté cargado; el par no
    (``resolve_model_key``). ``base.IrUiView`` **sí** declara su ``_name``, así
    que las dos formas resolverían — se usa el par por ser el que no depende
    del orden de import, que es la trampa que H-API-577 midió.

    Los cuatro encadenados con ``combine`` son los únicos cuyo método existe en
    ``base``; los otros ocho portados se instalan tal cual porque son símbolos
    nuevos que el addon del sitio introduce.
    """
    extend_model('base', 'IrUiView', campos={
        # ``compute='_compute_first_page_id'`` sin ``store`` (``:23``). D-2.
        'first_page_id': fields.NonStored(
            default=_compute_first_page_id,
            help_text='Primera página enlazada a esta vista (Odoo '
                      'first_page_id, compute sin store).',
        ),
    }, metodos={
        '_get_pwd': _get_pwd,
        '_set_pwd': _set_pwd,
        '_compute_first_page_id': _compute_first_page_id,
        'get_view_hierarchy': get_view_hierarchy,
        '_build_hierarchy_datastructure': _build_hierarchy_datastructure,
        'filter_duplicate': classmethod(filter_duplicate),
        '_get_cached_visibility': _get_cached_visibility,
        '_handle_visibility': _handle_visibility,
    }, propiedades={
        'website': _website_property,
        'track': _track_property,
        'visibility': _visibility_property,
        'visibility_password': _visibility_password_property,
    }, luego=_chain_template_hooks)


def _chain_template_hooks(model):
    """Encadena los cuatro ganchos de plantilla que ``base`` sí declara.

    Van por ``luego`` y no por ``metodos`` porque los cuatro necesitan un
    ``combine`` —el ``super() + delta`` de la fuente— y ``extend_model`` no lo
    expone en su bloque de métodos. La quinta línea instala el par
    ``compute``/``inverse`` como ``property``, que tampoco cabe en
    ``propiedades`` (ése instala sólo lectura).
    """
    chain_method(model, '_get_cached_template_prefetched_keys',
                 classmethod(_get_cached_template_prefetched_keys),
                 combine=extend_list)
    chain_method(model, '_get_template_domain',
                 classmethod(_get_template_domain),
                 combine=lambda new, previous: previous & new)
    chain_method(model, '_get_template_order',
                 classmethod(_get_template_order),
                 combine=lambda new, previous: tuple(new) + tuple(previous))
    chain_method(model, '_fetch_template_views',
                 classmethod(_fetch_template_views),
                 combine=_add_website_to_missing)
    # ``visibility_password_display`` (``:35``) — el par compute/inverse.
    if not isinstance(getattr(model, 'visibility_password_display', None),
                      property):
        model.visibility_password_display = property(_get_pwd, _set_pwd)
