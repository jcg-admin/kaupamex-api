"""``website.rewrite`` + ``website.route`` — redirecciones y catálogo de rutas.

Adaptación de Odoo ``addons/website/models/website_rewrite.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3) — atribución y aviso de
licencia preservados (DEC-KX-03). Mismo nombre de archivo que la referencia
(tarea **#104**).

Contrato medido de la fuente (AST, 175 líneas): **2 clases** —
``WebsiteRoute`` (4 atributos de clase, 1 campo, 3 métodos) y
``WebsiteRewrite`` (2 atributos de clase, 8 campos, 9 métodos).

Porte BLOQUEADO — 11 de 12 símbolos

**11 métodos portados, 1 bloqueado** (``get_import_templates``; su arista
está en su sitio en la clase).

Divergencias transversales, declaradas una vez aquí
=====================================================

1. **El mapa de rutas es la URLconf de Django.** Donde la fuente lee
   ``ir_http._generate_routing_rules`` / ``routing_map().iter_rules()``
   (werkzeug), aquí se recorre ``get_resolver()`` con
   ``_iter_url_patterns`` — el mismo eje ya portado por #545 para
   ``_enumerate_pages``. Consecuencias método a método en sus docstrings.
2. **La URLconf no declara métodos HTTP por regla** — el filtro
   ``'GET' in methods`` de ``_refresh`` no tiene sobre qué operar; toda ruta
   enumerable se cataloga (superconjunto conservador: catalogar de más no
   rompe; catalogar de menos escondería rutas).
3. **``create``/``write`` → ``save``, ``unlink`` → ``delete``** — la
   divergencia CRUD ya declarada en B1 de ``website.py``. La invalidación de
   routing de la fuente corre en los tres, con la misma condición
   (308/404 antes o después del cambio).
4. **``@api.constrains`` sin motor** — ``_check_url_to`` corre dentro de
   ``save()`` (mismo mecanismo que ``_check_company_auto`` en otros portes):
   el invariante se sostiene donde el ORM escribe.
5. **El sentido del import es rewrite → website**, nunca al revés: este
   módulo importa ``_iter_url_patterns`` de ``website.py``, y ``website.py``
   consulta ``website.rewrite`` por el registro
   (``model_by_name('website.rewrite')`` ≙ su ``env['website.rewrite']``) —
   misma nota que ``website_page.py``.
"""
import logging
import re

import fields
import models
from django.urls import Resolver404, get_resolver

from addons.base.models import TimeStampedModel
from addons.website.models.website import _iter_url_patterns
from exceptions import ValidationError
from orm.domains import Domain, to_q
from tools.translate import _

logger = logging.getLogger(__name__)


class WebsiteRoute(TimeStampedModel):
    """``website.route`` — el catálogo de rutas servibles del sitio.

    Una fila por ruta de la URLconf; ``_refresh`` lo reconcilia contra el
    router real. Su consumidor es el selector de ``url_from`` del editor de
    redirecciones.
    """

    _name = 'website.route'
    _rec_name = 'path'
    _description = "All Website Route"
    _order = 'path'

    path = fields.Char(
        max_length=512, null=True, blank=True,
        help_text='La ruta, tal como la declara la URLconf (Odoo path, '
                  '"Route").',
    )

    class Meta:
        db_table = 'website_route'
        # ≙ ``_order = 'path'``.
        ordering = ['path']
        verbose_name = 'Ruta del sitio'
        verbose_name_plural = 'Rutas del sitio'

    def __str__(self):
        # ≙ ``_rec_name = 'path'``.
        return self.path or f'website.route#{self.pk}'

    @classmethod
    def _search_display_name(cls, operator, value):
        """≙ ``_search_display_name`` (``@api.model``, ``odoo19c: addons/website/models/website_rewrite.py:22-27``).

        Si el dominio por nombre no tiene resultados, refrescar el catálogo
        antes de devolverlo (comentario de la fuente).

        Divergencia declarada: sin el ``super()`` del protocolo de
        ``display_name`` del ORM de la fuente, el dominio se construye
        directo sobre ``path`` (que es el ``_rec_name``).
        """
        domain = Domain('path', operator, value)
        if not cls.objects.filter(to_q(domain, cls)).exists():
            cls._refresh()
        return domain

    @classmethod
    def name_search(cls, name='', domain=None, operator='ilike', limit=100):
        """≙ ``name_search`` (``@api.model @api.readonly``, ``:29-36``).

        Pares ``(id, path)`` cuyos nombres coinciden; si no hay ninguno,
        refresca el catálogo y reintenta — verbatim la mecánica de la fuente.

        Divergencia declarada: el ``domain`` extra se recibe como ``Q`` de
        Django o ``None``; el resultado es una lista de tuplas, no un
        recordset.
        """
        def _matches():
            queryset = cls.objects.all()
            if domain is not None:
                queryset = queryset.filter(domain)
            if name:
                queryset = queryset.filter(path__icontains=name)
            return [(route.pk, route.path)
                    for route in queryset.order_by('path')[:limit]]

        result = _matches()
        if not result:
            cls._refresh()
            result = _matches()
        return result

    @classmethod
    def _refresh(cls):
        """≙ ``_refresh`` (``odoo19c: website_rewrite.py:38-57``).

        Reconcilia el catálogo contra el router real: da de alta las rutas
        nuevas y borra las que ya no existen. Los dos ``logger.info`` con el
        conteo se conservan.

        Divergencias declaradas: (1) el router es la URLconf
        (divergencia 1 del módulo) — se enumeran las rutas literales que
        ``_iter_url_patterns`` produce; (2) el filtro por método GET no
        aplica (divergencia 2).
        """
        logger.debug("Refreshing website.route")
        paths = {route.path: route for route in cls.objects.all()}
        tocreate = []
        # La URLconf puede exponer la MISMA ruta literal más de una vez (dos
        # `include` que la montan). El catálogo guarda una fila por ruta, así
        # que el alta se deduplica: sin esto la segunda pasada volvía a dar de
        # alta las repetidas y el conteo crecía en cada refresco.
        vistos = set()
        for route, _rule, literal in _iter_url_patterns():
            if not literal:
                continue
            url = '/' + route
            if url in vistos:
                continue
            vistos.add(url)
            if url in paths:
                paths.pop(url)
            else:
                tocreate.append(cls(path=url))

        if tocreate:
            logger.info("Add %d website.route", len(tocreate))
            cls.objects.bulk_create(tocreate)

        if paths:
            stale = cls.objects.filter(path__in=list(paths.keys()))
            logger.info("Delete %d website.route", stale.count())
            stale.delete()


class WebsiteRewrite(TimeStampedModel):
    """``website.rewrite`` — una redirección o reescritura de URL del sitio."""

    _name = 'website.rewrite'
    _description = "Website rewrite"

    name = fields.Char(
        max_length=255,
        help_text='Nombre de la regla (Odoo name, required).',
    )
    website = fields.Many2one(
        'website.Website', on_delete=models.CASCADE, null=True, blank=True,
        db_index=True, related_name='rewrites',
        help_text='Sitio al que aplica; vacía = todos (Odoo website_id, '
                  "ondelete='cascade', index).",
    )
    active = fields.Boolean(
        default=True,
        help_text='Regla activa (Odoo active).',
    )
    url_from = fields.Char(
        max_length=1024, null=True, blank=True, db_index=True,
        help_text='URL de origen (Odoo url_from, "URL from", index).',
    )
    route = fields.Many2one(
        WebsiteRoute, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='rewrites',
        help_text='Ruta del catálogo de la que parte la regla (Odoo '
                  'route_id).',
    )
    url_to = fields.Char(
        max_length=1024, null=True, blank=True,
        help_text='URL de destino (Odoo url_to, "URL to").',
    )
    redirect_type = fields.Selection(
        [
            ('404', '404 Not Found'),
            ('301', '301 Moved permanently'),
            ('302', '302 Moved temporarily'),
            ('308', '308 Redirect / Rewrite'),
        ],
        max_length=3, default='302',
        help_text='Tipo de redirección/reescritura (Odoo redirect_type, '
                  '"Action"): 301 el navegador cachea la URL nueva; 302 no '
                  'la cachea; 404 retira una página/controlador; 308 renombra '
                  'un controlador — ambas URL sirven y la vieja redirige a '
                  'la nueva.',
    )
    sequence = fields.Integer(
        default=0,
        help_text='Orden de aplicación entre reglas (Odoo sequence).',
    )

    class Meta:
        db_table = 'website_rewrite'
        verbose_name = 'Reescritura de URL'
        verbose_name_plural = 'Reescrituras de URL'

    def __str__(self):
        return self.display_name

    def _onchange_route_id(self):
        """≙ ``_onchange_route_id`` (``@api.onchange('route_id')``, ``odoo19c: website_rewrite.py:85-88``).

        Divergencia declarada: sin motor de onchange en este ORM, lo invoca
        la capa API/formulario al cambiar la ruta — el efecto (sembrar ambos
        extremos con el ``path`` elegido) es el mismo.
        """
        self.url_from = self.route.path if self.route_id else None
        self.url_to = self.route.path if self.route_id else None

    def _check_url_to(self):
        """≙ ``_check_url_to`` (``@api.constrains``, ``odoo19c: website_rewrite.py:90-130``).

        El invariante de la regla; corre en ``save()`` (divergencia 4 del
        módulo). Los mensajes conservan el texto de la fuente vía el hook de
        traducción.

        Divergencias declaradas del caso 308: (1) «no puede apuntar a una
        página existente» se mide contra la URLconf
        (``get_resolver().resolve``), no contra ``routing_map()``; (2) la
        validación sintáctica final con ``werkzeug.routing.Map`` no se
        replica — werkzeug no es dependencia de este árbol; la forma de los
        parámetros ya quedó validada por los dos barridos de ``/<...>``.
        """
        rewrite = self
        if rewrite.redirect_type in ['301', '302', '308']:
            if not rewrite.url_to:
                raise ValidationError(_('"URL to" can not be empty.'))
            if not rewrite.url_from:
                raise ValidationError(_('"URL from" can not be empty.'))
            if rewrite.url_to.startswith('#') or rewrite.url_from.startswith('#'):
                raise ValidationError(_("URL must not start with '#'."))
            if rewrite.url_to.split('#')[0] == rewrite.url_from.split('#')[0]:
                raise ValidationError(
                    _("base URL of 'URL to' should not be same as 'URL from'."))

        if rewrite.redirect_type == '308':
            if not rewrite.url_to.startswith('/'):
                raise ValidationError(
                    _('"URL to" must start with a leading slash.'))
            for param in re.findall('/<.*?>', rewrite.url_from):
                if param not in rewrite.url_to:
                    raise ValidationError(_(
                        '"URL to" must contain parameter %s used in '
                        '"URL from".') % param)
            for param in re.findall('/<.*?>', rewrite.url_to):
                if param not in rewrite.url_from:
                    raise ValidationError(_(
                        '"URL to" cannot contain parameter %s which is not '
                        'used in "URL from".') % param)

            if rewrite.url_to == '/':
                raise ValidationError(_(
                    '"URL to" cannot be set to "/". To change the homepage '
                    'content, use the "Homepage URL" field in the website '
                    'settings or the page properties on any custom page.'))

            try:
                get_resolver().resolve(rewrite.url_to)
            except Resolver404:
                pass  # silent OK because destino libre: la 308 puede apuntarle
            else:
                raise ValidationError(
                    _('"URL to" cannot be set to an existing page.'))

    def _compute_display_name(self):
        """≙ ``_compute_display_name`` (``@api.depends('redirect_type')``, ``odoo19c: website_rewrite.py:132-135``)."""
        return f"{self.redirect_type} - {self.name}"

    def save(self, *args, **kwargs):
        """≙ ``create`` (``@api.model_create_multi``, ``:137-142``) +
        ``write`` (``:144-150``) — nombre CRUD divergente declarado
        (divergencia 3 del módulo).

        Corre el invariante (``_check_url_to``, divergencia 4) y, si el tipo
        antes o después del cambio altera el mapa (308/404), invalida el
        routing — misma condición en los dos lados que la fuente.
        """
        self._check_url_to()
        need_invalidate = self.redirect_type in ('308', '404')
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).first()
            if previous is not None:
                need_invalidate = (need_invalidate
                                   or previous.redirect_type in ('308', '404'))
        result = super().save(*args, **kwargs)
        if need_invalidate:
            self._invalidate_routing()
        return result

    def delete(self, *args, **kwargs):
        """≙ ``unlink`` (``odoo19c: website_rewrite.py:152-157``) — nombre
        CRUD divergente declarado (divergencia 3 del módulo)."""
        need_invalidate = self.redirect_type in ('308', '404')
        result = super().delete(*args, **kwargs)
        if need_invalidate:
            self._invalidate_routing()
        return result

    def _invalidate_routing(self):
        """≙ ``_invalidate_routing`` (``odoo19c: website_rewrite.py:159-165``).

        La fuente limpia la caché 'routing' en todos los workers porque sólo
        404 y 308 alteran el mapa (404 quita la entrada; 301/302 se sirven
        como fallback; 308 añade el alias). Aquí el mapa es la URLconf y su
        caché es el ``lru_cache`` de ``get_resolver`` — se limpia ése, que
        es el único routing cacheado que este árbol tiene; el middleware que
        sirva las 308/404 desde estas filas es la tarea **#562**.
        """
        get_resolver.cache_clear()

    def refresh_routes(self):
        """≙ ``refresh_routes`` (``odoo19c: website_rewrite.py:167-168``)."""
        WebsiteRoute._refresh()

    # ``get_import_templates`` (``@api.model``, ``:170-175``): BLOQUEADO por
    # ``website/static/xls/redirects_import_template.xlsx`` — el estático no
    # vive en este árbol (mismo criterio que ``_default_logo`` en
    # website.py: no se fabrica un asset que no existe, y la ruta llevaría
    # material del árbol de referencia a un endpoint del cliente).
