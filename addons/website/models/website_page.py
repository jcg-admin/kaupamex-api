"""``website.page`` — la página del sitio, delegando en ``ir.ui.view``.

Adaptación de Odoo ``addons/website/models/website_page.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3) — atribución y aviso de
licencia preservados (DEC-KX-03). Mismo nombre de archivo que la referencia
(tarea **#104**; segunda cláusula de ``atributos-de-clase-de-modelo.md``).

Contrato medido de la fuente (AST, 485 líneas): **2 clases**
(``PageCannotBeCached`` con 1 método; ``WebsitePage`` con **6 atributos de
clase, 14 campos y 22 métodos**).

Porte BLOQUEADO — 14 de 23 símbolos

**14 métodos portados, 9 bloqueados**; cada bloqueado lleva su arista con la
forma fija en el cuerpo de la clase. Los nueve comparten dos causas:

- El motor de render servidor (``request.render`` sobre QWeb, ``http.Response``
  con ``.time``) no existe en este árbol — las páginas se sirven por la capa
  DRF + React. Cae la familia de caché de respuesta completa.
- El registro de datos por external ID (#467) y el motor de grupos por
  external ID no están portados.

Divergencias transversales, declaradas una vez aquí
=====================================================

1. **``_inherits`` con la FK sin sufijo.** La fuente declara
   ``_inherits = {'ir.ui.view': 'view_id'}``; aquí la clave es ``view``
   porque el sufijo ``_id`` se cae en los FK (:ref:`h-api-579` — Django ya
   emite la columna ``view_id``; conservarlo produciría ``view_id_id``).
   Mismo criterio que ``ResUsers._inherits = {'res.partner': 'partner'}``.
   La delegación la instala ``WebsiteConfig.ready()`` con
   ``orm.inherits.apply_inherits`` — el mecanismo ya construido: la página
   expone ``name``, ``key``, ``arch_db``, ``priority`` … de su vista como
   propios.
2. **``website_id`` es FK real, no ``related``.** La fuente lo declara
   ``related='view_id.website_id', store=True`` porque su addon extiende
   ``ir.ui.view`` con ``website_id`` (la maquinaria COW de
   ``odoo19c: addons/website/models/ir_ui_view.py``). Esa extensión no está
   portada, así que el eje por sitio vive en la página misma; cuando la COW
   se porte, este campo puede volver a ``related``.
3. **Los ``compute`` sin ``store`` van con ``fields.NonStored``** (mismo
   mecanismo que los cinco de ``website.py``); el ``_compute_*`` devuelve el
   valor en vez de asignarlo al recordset.
4. **``create``/``write`` → ``save``, ``unlink`` → ``delete``** — la
   divergencia CRUD ya declarada en B1 de ``website.py``.
5. **Sin ``tools.ormcache``** — BLOQUEADO por ``tools.ormcache`` — la
   decisión de caché bajo prefork es la tarea #542; los métodos cacheados de
   la fuente que sí se portan calculan siempre.
6. **El sentido del import es página → website**, nunca al revés: este
   módulo importa ``Website``, y ``website.py`` consulta ``website.page``
   por el registro (``model_by_name('website.page')`` ≙ su
   ``env['website.page']``), igual que la fuente, donde ``website.py``
   tampoco importa a sus módulos hermanos.

Qué pasa con ``StaticPage`` / ``StaticContent`` (decisión de #104)
====================================================================

**Se conservan, con la absorción declarada como pendiente.** ``website.page``
es el modelo alineado con la referencia y absorbe *el papel* de ambos pares
propios, pero la absorción **de datos y consumidores** no cabe en este pase
sin pérdida:

- ``StaticPage``/``StaticPageVersion`` llevan un flujo editorial
  (DRAFT→PUBLISHED→ARCHIVED con historial) que ``website.page`` no tiene:
  su versionado en la referencia sale del COW de ``ir.ui.view``, que no está
  portado. Absorber hoy perdería el flujo de publicación.
- Ambos pares tienen consumidores REST vivos (``controllers/main.py``,
  ``static_content*.py``, serializers y tests de integración) cuyo contrato
  público no cambia en este pase.

Consecuencia: ninguna tabla se borra ni migra (cero pérdida de datos); los
consumidores **internos** de ``Website`` (``get_unique_path``,
``check_existing_page``) consultan ya ``website.page`` como primario y los
modelos propios como interinato — ver sus docstrings en ``website.py``. La
migración de los endpoints REST y del contenido es la tarea **#560**.
"""
import re
from collections import Counter

import fields
import models
from django.utils import timezone

from addons.base.models import TimeStampedModel
from addons.base.models.ir_http import IrHttp
from addons.base.models.ir_ui_view import IrUiView
from addons.website.models.mixins import (
    WebsitePublishedMixin,
    WebsiteSearchableMixin,
    order_expression_to_order_by,
)
from addons.website.models.website import Website
from addons.website.models.website_menu import WebsiteMenu
from addons.website.tools import text_from_html
from orm.domains import Domain, to_q
from orm.environments import get_context, is_su, sudo


class PageCannotBeCached(Exception):
    """≙ ``PageCannotBeCached`` (``odoo19c: addons/website/models/website_page.py:19-21``).

    La señal con que la familia de caché de respuesta corta el camino
    cacheado. Se porta verbatim aunque su consumidor
    (``_get_response_cached``) siga bloqueado: es el contrato de esa familia
    y no depende de ninguna pieza ausente.
    """

    def __init__(self, result):
        self.result = result


def _translate_order(order):
    """Traduce la expresión de orden de la fuente al queryset de la página.

    ``name`` es columna del delegado (``ir.ui.view``), no de esta tabla; el
    queryset lo alcanza por el JOIN de la FK (``view__name``). El resto de
    los términos pasa por ``order_expression_to_order_by`` sin cambios.
    """
    translated = []
    for term in order_expression_to_order_by(order):
        descending = term.startswith('-')
        bare = term.lstrip('-')
        if bare == 'name':
            bare = 'view__name'
        translated.append(('-' if descending else '') + bare)
    return translated


class WebsitePage(WebsiteSearchableMixin, WebsitePublishedMixin,
                  TimeStampedModel):
    """``website.page`` — una URL del sitio cuyo contenido es una vista.

    La página no *tiene* el contenido: **delega** en ``ir.ui.view`` por
    ``_inherits`` y aporta lo suyo — la URL, el sitio, la indexación y la
    fecha de publicación (ver el docstring del módulo, divergencia 1).

    ``_inherit`` se declara verbatim (``atributos-de-clase-de-modelo.md``:
    nombra la extensión aunque el mixin aún no exista). De los tres:
    ``website.searchable.mixin`` y el estado de publicación están portados en
    ``mixins.py`` (aquí la variante simple — la «multi» sólo añade el
    ``website_id`` que esta clase redefine, igual que la fuente comenta);
    ``website.page_options.mixin`` no existe — BLOQUEADO por
    ``website.page_options.mixin`` — sus campos (``visibility``,
    ``group_ids``, ``track``, ``header_*``) y las ramas que los consumen
    quedan fuera hasta su porte.
    """

    _name = 'website.page'
    # La fuente escribe {'ir.ui.view': 'view_id'}; la clave es la FK nuestra
    # (sufijo _id suprimido, divergencia 1 del módulo).
    _inherits = {'ir.ui.view': 'view'}
    _inherit = [
        'website.published.multi.mixin',
        'website.searchable.mixin',
        'website.page_options.mixin',
    ]
    _description = 'Page'
    _order = 'website_id'

    #: ≙ ``_CACHE_DURATION`` (``:36``) — vigencia de una entrada de caché, en
    #: segundos. Su consumidor (``_get_response``) sigue bloqueado; la
    #: constante se porta porque es parte de la cabecera de la clase.
    _CACHE_DURATION = 3600

    # Ayudante propio, NO atributo de ORM de la fuente: la traducción de la
    # expresión de orden al queryset; lo consumen ``_search_fetch`` y
    # ``Website._get_website_pages`` (que resuelve este modelo por registro).
    _translate_order = staticmethod(_translate_order)

    url = fields.Char(
        max_length=1024,
        help_text='Ruta de la página, p. ej. /acerca-de (Odoo url, '
                  'required; el largo es el max_length del slugify de la '
                  'fuente).',
    )
    view = fields.Many2one(
        'base.IrUiView', on_delete=models.CASCADE, db_index=True,
        related_name='page_ids', db_column='view_id',
        help_text='La vista que da el contenido (Odoo view_id, required, '
                  'ondelete=cascade). Es la FK de la delegación _inherits.',
    )
    # ``view_write_uid`` (``related='view_id.write_uid'``, ``:41-42``):
    # BLOQUEADO por ``ir.ui.view.write_uid`` — TimeStampedModel no lleva
    # columnas de autor de auditoría; el campo llega cuando el par
    # write_uid/create_uid se porte a base.
    website_indexed = fields.Boolean(
        default=True,
        help_text='Aparece en el sitemap y para los buscadores (Odoo '
                  'website_indexed, "Is Indexed").',
    )
    date_publish = fields.Datetime(
        null=True, blank=True,
        help_text='Fecha de publicación programada; antes de ella la página '
                  'no es visible (Odoo date_publish).',
    )
    # ``menu_ids`` es el reverso del FK ``page`` de ``website.menu``
    # (``related_name='menu_ids'``) — mismo nombre que el One2many de la
    # fuente (``:48``).
    is_new_page_template = fields.Boolean(
        default=False,
        help_text='La página se ofrece como plantilla en "+Nueva", categoría '
                  'Personalizadas (Odoo is_new_page_template).',
    )
    website = fields.Many2one(
        'website.Website', on_delete=models.CASCADE, null=True, blank=True,
        db_index=True, related_name='pages',
        help_text='Sitio dueño de la página; vacía = genérica, visible en '
                  'todos (Odoo website_id; aquí FK real — divergencia 2 del '
                  'módulo).',
    )

    # ── Campos NO almacenados (compute sin store, divergencia 3) ────────────

    #: ≙ ``is_in_menu`` (``:49``).
    is_in_menu = fields.NonStored(
        default=lambda self: self._compute_website_menu())
    #: ≙ ``is_homepage`` (``:50``).
    is_homepage = fields.NonStored(
        default=lambda self: self._compute_is_homepage())
    #: ≙ ``is_visible`` (``:51``).
    is_visible = fields.NonStored(
        default=lambda self: self._compute_visible())

    class Meta:
        db_table = 'website_page'
        # ≙ ``_order = 'website_id'`` (``:33``).
        ordering = ['website_id']
        verbose_name = 'Página del sitio'
        verbose_name_plural = 'Páginas del sitio'

    def __str__(self):
        return self.url or f'website.page#{self.pk}'

    # ── related sobre el delegado ───────────────────────────────────────────

    @property
    def view_write_date(self):
        """≙ ``view_write_date`` (``related='view_id.write_date'``, ``:43-44``).

        ``write_date`` de la referencia es ``updated_at`` en
        ``TimeStampedModel`` — la equivalencia ya declarada por el porte de
        B1 de ``website.py``.
        """
        return self.view.updated_at if self.view_id else None

    @property
    def arch(self):
        """≙ ``arch`` (``related='view_id.arch', readonly=False``, ``:56``).

        En la fuente ``arch`` es el campo calculado de la vista sobre
        ``arch_db``; aquí la vista almacena directamente ``arch_db``, así que
        el related aterriza en esa columna. Escribible, como la fuente
        (``readonly=False``); el eje ``depends_context=('website_id',)`` es
        de la COW no portada (divergencia 2 del módulo).
        """
        return self.view.arch_db if self.view_id else None

    @arch.setter
    def arch(self, value):
        self.view.arch_db = value

    @property
    def website_url(self):
        """≙ ``_compute_website_url`` (``:77-80``) — la URL pública ES ``url``.

        El comentario de la fuente: el cómputo existe para que el mixin
        publique ``page.url`` y no otra cosa.
        """
        return self._compute_website_url()

    # ── computes ────────────────────────────────────────────────────────────

    def _compute_is_homepage(self):
        """≙ ``_compute_is_homepage`` (``odoo19c: website_page.py:58-61``).

        Divergencia declarada: sin sitio actual resoluble (fuera de toda
        petición y sin sitios en la base) no hay portada que comparar —
        ``False`` en vez de reventar.
        """
        current_website = Website.get_current_website()
        if current_website is None:
            return False
        return self.url == (
            current_website.homepage_url
            or (self.website_id == current_website.pk and '/'))

    def _compute_visible(self):
        """≙ ``_compute_visible`` (``:63-67``)."""
        return bool(self.website_published and (
            not self.date_publish or self.date_publish < timezone.now()))

    def _compute_website_menu(self):
        """≙ ``_compute_website_menu`` (``@api.depends('menu_ids')``, ``:70-72``)."""
        if not self.pk:
            return False
        return self.menu_ids.exists()

    def _compute_website_url(self):
        """≙ ``_compute_website_url`` (``@api.depends('url')``, ``:77-80``)."""
        return self.url

    # ``_compute_can_publish`` (``:82-89``): BLOQUEADO por
    # ``website.group_website_designer`` — resolver el grupo exige el
    # registro de datos por external ID (#467; mismo criterio que
    # ``_should_remove_third_party_trackers`` de website.py). El campo
    # ``can_publish`` tampoco está en el mixin portado (ver mixins.py).

    @classmethod
    def _get_most_specific_pages(cls, pages, website=None):
        """≙ ``_get_most_specific_pages`` (``odoo19c: website_page.py:91-112``).

        De un conjunto con posibles duplicados genérica/específica por URL,
        las más específicas: gana la del sitio; la genérica sólo cuenta si su
        ``key`` no fue clonada (el caso COW comentado en la fuente).

        Divergencias declaradas: (1) recordset → lista de instancias (patrón
        del mixin de búsqueda); (2) el ``website_id`` del contexto se acepta
        también como argumento explícito — el eje de contexto existe
        (``orm.environments.get_context``) pero el llamador de este árbol ya
        tiene el sitio en la mano; (3) ``key`` se lee por el JOIN de la
        delegación (``view__key``).
        """
        if website is None:
            context_website_id = get_context().get('website_id')
            if context_website_id:
                website = Website.objects.filter(
                    pk=context_website_id).first()
            else:
                website = Website.get_current_website()
        scope = cls.objects.all()
        if website is not None:
            scope = scope.filter(website.website_domain())
        page_keys_counts = Counter(
            scope.values_list('view__key', flat=True))

        selected_ids = set()
        previous_page = None
        # Un solo recorrido sobre la lista ordenada específica-primero
        # (comentario de la fuente).
        for page in sorted(pages, key=lambda p: (p.url, not p.website_id)):
            if (
                (not previous_page or page.url != previous_page.url)
                and (page.website_id or page_keys_counts[page.key] == 1)
            ):
                selected_ids.add(page.pk)
            previous_page = page
        return [page for page in pages if page.pk in selected_ids]

    def copy_data(self, default=None):
        """≙ ``copy_data`` (``odoo19c: website_page.py:114-125``).

        Los valores con que se clona la página. Divergencias declaradas:
        (1) instancia → un dict, no ``vals_list``; (2) ``view.copy({...})``
        de la fuente es aquí un clon campo a campo — el ORM no trae
        ``copy()``, mismo criterio que ``Website.copy_menu_hierarchy``; la
        clave nueva sale de ``get_unique_key`` porque la derivación COW de la
        fuente vive en su extensión de ``ir.ui.view`` (divergencia 2 del
        módulo).
        """
        values = {
            'view': self.view,
            'url': self.url,
            'website': self.website,
            'website_indexed': self.website_indexed,
            'date_publish': self.date_publish,
            'is_published': self.is_published,
            'is_new_page_template': self.is_new_page_template,
        }
        if not default:
            return values
        if not default.get('view'):
            current_website = Website.get_current_website()
            source_view = self.view
            new_key = current_website.get_unique_key(
                source_view.key.split('.')[-1] or IrHttp.slugify(
                    default.get('name') or source_view.name or ''))
            new_view = IrUiView.objects.create(
                name=default.get('name') or source_view.name,
                model=source_view.model,
                type=source_view.type,
                priority=source_view.priority,
                mode=source_view.mode,
                inherit_id=source_view.inherit_id,
                key=new_key,
                arch_db=source_view.arch_db,
            )
            values['view'] = new_view
        for field_name in ('url', 'website', 'website_indexed', 'date_publish',
                           'is_published', 'is_new_page_template', 'name'):
            if field_name in default:
                values[field_name] = default[field_name]
        # ``name`` pertenece a la vista; si ya se aplicó al clon, no viaja
        # como campo de la página.
        values.pop('name', None)
        if 'url' not in default:
            values['url'] = Website.get_current_website().get_unique_path(
                self.url)
        return values

    @classmethod
    def clone_page(cls, page_id, page_name=None, clone_menu=True):
        """≙ ``clone_page`` (``@api.model``, ``odoo19c: website_page.py:127-146``).

        Clona una página por identificador; devuelve la URL del clon.
        El menú se clona sólo si el clon quedó en el mismo sitio (el caso
        genérica→específica de la fuente no arrastra el menú).

        Divergencia declarada: ``key`` de ``website.menu`` es campo propio y
        único — el clon deriva la suya de la página nueva, mismo criterio que
        ``Website.copy_menu_hierarchy``.
        """
        page = cls.objects.get(pk=int(page_id))
        current_website = Website.get_current_website()
        copy_param = {
            'name': page_name or page.name,
            'website': current_website,
        }
        if page_name:
            url = '/' + IrHttp.slugify(page_name, max_length=1024, path=True)
            copy_param['url'] = current_website.get_unique_path(url)

        new_page = cls.objects.create(**page.copy_data(copy_param))
        if clone_menu and new_page.website_id == page.website_id:
            menu = WebsiteMenu.objects.filter(page=page).first()
            if menu:
                # Si la página clonada tiene menú, se clona también.
                WebsiteMenu.objects.create(
                    name=new_page.name,
                    route=new_page.url,
                    sequence=menu.sequence,
                    new_window=menu.new_window,
                    parent=menu.parent,
                    website=menu.website,
                    page=new_page,
                    key=f'{menu.key}-p{new_page.pk}',
                )
        return new_page.url

    def delete(self, *args, **kwargs):
        """≙ ``unlink`` (``odoo19c: website_page.py:148-162``) — nombre CRUD
        divergente declarado (divergencia 4 del módulo).

        Al borrar la página, el ORM no borra su vista (la FK apunta página →
        vista); se borra aquí, sólo si ninguna otra página la usa y no tiene
        vistas hijas — verbatim el criterio de la fuente. El
        ``clear_cache('templates')`` final es del ormcache no portado
        (#542, divergencia 5).
        """
        view = self.view if self.view_id else None
        result = super().delete(*args, **kwargs)
        if view is not None and not view.page_ids.exists() \
                and not view.inherit_children_ids.exists():
            view.delete()
        return result

    def save(self, *args, **kwargs):
        """≙ ``write`` (``odoo19c: website_page.py:164-195``) — nombre CRUD
        divergente declarado (divergencia 4 del módulo).

        En una edición (no en el alta): si la URL cambió, se re-slugifica, se
        hace única, se propaga a los menús de la página y se sincroniza la
        portada del sitio; si el nombre cambió, la ``key`` de la vista se
        rederiva única. La rama ``visibility``/``group_ids`` de la fuente
        pertenece al mixin ausente — BLOQUEADO por
        ``website.page_options.mixin`` — y el ``clear_cache`` final es del
        ormcache no portado (#542).
        """
        previous = None
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).first()

        if previous is not None:
            new_url = '/' + IrHttp.slugify(
                self.url or '', max_length=1024, path=True)
            if previous.url != new_url:
                current_website = Website.get_current_website()
                if current_website is not None:
                    new_url = current_website.get_unique_path(new_url)
                    self.menu_ids.update(route=new_url)
                    # Sincronizar la portada del sitio (verbatim la mecánica
                    # de la fuente sobre _handle_homepage_url).
                    normalized = {'homepage_url': previous.url}
                    Website._handle_homepage_url(normalized)
                    if current_website.homepage_url == normalized['homepage_url']:
                        current_website.homepage_url = new_url
                        current_website.save(update_fields=['homepage_url'])
                self.url = new_url

            if previous.name != self.name:
                current_website = Website.get_current_website()
                if current_website is not None:
                    self.view.key = current_website.get_unique_key(
                        IrHttp.slugify(self.name or ''))
                    self.view.save(update_fields=['key'])

        return super().save(*args, **kwargs)

    # ``get_website_meta`` (``:197-199``): BLOQUEADO por
    # ``ir.ui.view.get_website_meta`` — la extensión website de la vista
    # (metadatos OG/SEO del addon website sobre ir.ui.view) no está portada.

    @classmethod
    def _search_get_detail(cls, website, order, options):
        """≙ ``_search_get_detail`` (``@api.model``, ``odoo19c: website_page.py:202-240``).

        La receta de búsqueda de las páginas. Divergencias declaradas:

        - ``model`` lleva la clase, no el nombre (divergencia 1 del bloque
          B3 de ``website.py``; el registro por nombre ya resuelve
          ``website.page``, pero el consumidor ``_search_exact`` espera la
          clase).
        - Los campos del delegado se buscan por el JOIN (``view.name``,
          ``view.arch_db``) — el ``to_q`` de dominios traduce el punto.
        - El refuerzo por grupo/diseñador (``has_group``) — BLOQUEADO por
          ``website.group_website_designer`` — sin registro de grupos por
          external ID (#467) el default conservador es aplicar SIEMPRE el
          recorte del público: publicada e indexada.
        - Los escalones ``visibility``/``group_ids`` — BLOQUEADO por
          ``website.page_options.mixin`` — los campos no existen.
        """
        with_description = options.get('displayDescription')
        # La lectura de website.page exige sudo también aquí (comentario de
        # la fuente).
        requires_sudo = True
        domain = []
        if website is not None:
            # ≙ ``website.website_domain()``, en forma de dominio para que
            # ``Domain.AND`` del mixin lo componga: las del sitio más las
            # genéricas.
            domain.append(Domain.OR([
                Domain('website_id', '=', False),
                Domain('website_id', '=', website.pk),
            ]))
        domain.append(Domain('is_published', '=', True))
        domain.append(Domain('website_indexed', '=', True))

        search_fields = ['view.name', 'url']
        fetch_fields = ['id', 'name', 'url']
        mapping = {
            'name': {'name': 'name', 'type': 'text', 'match': True},
            'website_url': {'name': 'url', 'type': 'text', 'truncate': False},
        }
        if with_description:
            search_fields.append('view.arch_db')
            fetch_fields.append('arch')
            mapping['description'] = {
                'name': 'arch', 'type': 'text', 'html': True, 'match': True}
        return {
            'model': cls,
            'base_domain': domain,
            'requires_sudo': requires_sudo,
            'search_fields': search_fields,
            'fetch_fields': fetch_fields,
            'mapping': mapping,
            'icon': 'fa-file-o',
        }

    @classmethod
    def _search_fetch(cls, search_detail, search, limit, order):
        """≙ ``_search_fetch`` (``@api.model``, ``odoo19c: website_page.py:242-301``).

        No sirve el ``_search_fetch`` del mixin: la búsqueda debe ocurrir
        sólo entre las páginas más específicas (comentario de la fuente).

        Divergencias declaradas: (1) la consulta SQL sobre traducciones de
        ``arch_db`` no aplica — el campo no es JSONB traducido aquí, así que
        el ``ilike`` del dominio ya lo cubre; (2) el filtro por ``ir.rule``
        de ``filter_page`` no se replica — el ACL de lectura corre en la capa
        DRF (``HasCapability``), no en el modelo; (3) el chequeo de que los
        términos aparezcan en el TEXTO (no en los tags XML) sí se porta.
        """
        with_description = 'description' in search_detail['mapping']
        search_fields = search_detail['search_fields']
        base_domain = Domain.AND(search_detail['base_domain'])
        domain = cls._search_build_domain(
            [base_domain], search, search_fields,
            search_detail.get('search_extra'))
        with sudo(bool(search_detail.get('requires_sudo')) or is_su()):
            order_by = _translate_order(search_detail.get('order', order))
            queryset = cls.objects.filter(to_q(domain, cls))
            if order_by:
                queryset = queryset.order_by(*order_by)
            results = cls._get_most_specific_pages(list(queryset))

            def filter_page(page):
                if search and with_description:
                    # El match pudo caer en un tag XML; confirmar que los
                    # términos aparecen en el texto (verbatim la mecánica).
                    text = '%s %s %s' % (
                        page.name, page.url, text_from_html(page.arch or ''))
                    pattern = '|'.join(
                        re.escape(term) for term in search.split())
                    return bool(
                        re.findall('(%s)' % pattern, text, flags=re.I)
                    ) if pattern else False
                return True

            results = [page for page in results if filter_page(page)]
        return results[:limit], len(results)

    # ``action_page_debug_view`` (``:302-308``): BLOQUEADO por
    # ``ir.actions.act_window`` — la acción de ventana y el ``env.ref`` del
    # formulario se resuelven por external ID (#467).

    # ── caché de respuesta (la familia, ``:314-485``) ───────────────────────
    #
    # Cuatro de sus seis piezas están BLOQUEADAS por ``request.render`` — el
    # render servidor QWeb (``http.Response`` con ``.time``, el reescrito de
    # csrf_token en el HTML cacheado) no existe: las páginas se sirven por la
    # capa DRF + React. Sucesor: #488 (el marco de cliente/servidor sin
    # decidir), que es donde esa decisión vive. Método a método:
    #
    # - ``_allow_to_use_cache`` (``:314``) — BLOQUEADO por
    #   ``request.params``/``_is_public`` de su ``http.Request`` — además del
    #   render, lee el usuario público por petición.
    # - ``_post_process_response_from_cache`` (``:333``) — BLOQUEADO por
    #   ``http.Response`` — reescribe csrf en el cuerpo cacheado.
    # - ``_get_cache_key`` (``:349``) — BLOQUEADO por ``tools.ormcache`` —
    #   la clave sólo existe para esa caché (#542).
    # - ``_get_response`` (``:357``), ``_get_response_cached`` (``:408``),
    #   ``_get_response_raw`` (``:426``) — BLOQUEADOS por ``request.render``
    #   — construyen la respuesta HTML servidor.

    @classmethod
    def _allow_cache_insertion(cls, layout):
        """≙ ``_allow_cache_insertion`` (``@api.model``, ``odoo19c: website_page.py:326-331``).

        ¿La página puede insertarse en la caché a partir del layout ya
        renderizado? La fuente responde ``True`` incondicional — es el gancho
        que las extensiones sobreescriben.
        """
        return True

    @classmethod
    def _get_page_info(cls, request):
        """≙ ``_get_page_info`` (``@api.model``, ``odoo19c: website_page.py:467-485``).

        La página que responde a la ruta pedida: primero la específica del
        sitio (``order='website_id asc'`` — en PostgreSQL el ASC pone los
        NULL al final, así que la específica gana), después el reintento
        case-insensitive.

        Divergencias declaradas: (1) sin el ``tools.ormcache`` (#542,
        divergencia 5 del módulo); (2) ``request`` es el ``HttpRequest`` de
        Django — la ruta sale de ``request.path`` y el sitio de
        ``get_current_website``, no de ``request.website``; (3)
        ``group_ids`` pertenece al mixin ausente — BLOQUEADO por
        ``website.page_options.mixin`` — la clave se sirve vacía para
        conservar el contrato del dict.
        """
        req_page = request.path
        current_website = Website.get_current_website()
        queryset = cls.objects.all()
        if current_website is not None:
            queryset = queryset.filter(current_website.website_domain())

        # Primero la página específica del sitio.
        page = queryset.filter(url=req_page).order_by('website_id').first()
        if page is None:
            # Búsqueda case-insensitive.
            page = (queryset.filter(url__iexact=req_page)
                    .order_by('website_id').first())

        if page is not None:
            return {
                'id': page.pk,
                'url': page.url,
                'view_id': page.view_id,
                'group_ids': [],
            }
        return None
