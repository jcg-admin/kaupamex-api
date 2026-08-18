"""Mixins del sitio — adaptación de ``odoo19c: website/models/mixins.py``.

Se portan dos: **el estado de publicación** y **la búsqueda del sitio**
(``website.searchable.mixin``, ``:327-408``, que consume la búsqueda B3 de
``website.py``). En la referencia viven en ``website``, no en ``product``, y
ese reparto es deliberado: un producto existe en el ERP aunque no esté en la
tienda. Quien dueña "esto se ve en el sitio" es el sitio.

Medido en las dos poblaciones que llevan el mixin
(``odoo-tools@622ddc2a``):

===========  ===========================================
Árbol        ``is_published``
===========  ===========================================
``odoo19c``  ``website/models/mixins.py:207``
``odoo18c``  el mismo ``_name``, consumido por
             ``website_sale/models/product_template.py``
===========  ===========================================

Qué **no** se porta y por qué
-----------------------------

La referencia declara cinco campos en el mixin; aquí sólo dos tienen sentido:

- ``is_published`` — **sí**: es el estado real.
- ``website_published`` — **sí**, como propiedad de sólo lectura. Allá es un
  ``related`` editable sobre ``is_published``; aquí no hay ``related``, así
  que se expone como alias legible y se escribe siempre sobre el campo real.
  Un alias escribible sin mecanismo que lo respalde sería dos fuentes de
  verdad para un booleano.
- ``can_publish`` / ``website_url`` / ``website_absolute_url`` — **no**: los
  tres son ``compute`` que dependen de piezas que este proyecto no tiene
  (el motor de permisos de publicación por grupo, y el enrutador QWeb que
  construye la URL del documento). Portar el campo sin su motor daría un
  valor siempre falso o siempre ``'#'`` — que es lo que la referencia pone
  como *placeholder*, no como respuesta.
"""
import re

from django.db import models

from addons.website.tools import text_from_html
from orm.domains import Domain, to_q
from orm.environments import is_su, sudo
from tools.sql import escape_psql


def order_expression_to_order_by(order):
    """Traduce la expresión de orden de la fuente a la lista de ``order_by``.

    La fuente pasa ``order`` como cadena SQL-like (``'name asc, id desc'``);
    aquí el consumidor es un queryset, así que cada término se traduce a la
    forma de Django (``'-id'`` para descendente). Cadena vacía o ``None``
    devuelven lista vacía: sin orden explícito, el queryset conserva el suyo.
    """
    if not order:
        return []
    order_by = []
    for part in order.split(','):
        bits = part.strip().split()
        if not bits:
            continue
        descending = len(bits) > 1 and bits[1].lower() == 'desc'
        order_by.append(f'-{bits[0]}' if descending else bits[0])
    return order_by


class WebsiteSearchableMixin:
    """≙ ``website.searchable.mixin`` (``odoo19c: website/models/mixins.py:327``).

    *"Mixin to be inherited by all models that need to searchable through
    website"* — verbatim de la fuente. Es un ``AbstractModel`` **sin campos**,
    así que aquí es un mixin plano de Python (mismo precedente que
    ``bus.listener.mixin``): no aporta columnas, sólo el contrato de búsqueda
    que ``Website._search_exact`` consume.

    **Divergencias declaradas (las tres, del mismo eje recordset→queryset):**

    1. Los métodos de la fuente son ``@api.model`` sobre un recordset; aquí
       son ``@classmethod`` y los resultados viajan como **lista de
       instancias**, no como recordset. Por eso ``_search_render_results``
       recibe ``results`` como primer parámetro explícito — en la fuente es
       el propio ``self``.
    2. ``extra`` recibe sólo ``search_term`` — la fuente le pasa
       ``(self.env, search_term)``, y aquí no hay ``env`` que pasar: el
       contexto vive en ``orm.environments``.
    3. El render lee por ``getattr`` en vez de ``read()``: admite properties
       (``StaticPage.url``) además de columnas, que es lo que este árbol usa
       donde la fuente usa campos ``compute``.
    """

    _name = 'website.searchable.mixin'
    _description = 'Website Searchable Mixin'

    @classmethod
    def _search_build_domain(cls, domain_list, search, fields, extra=None):
        """≙ ``_search_build_domain`` (``:332-352``).

        AND del dominio base con, por cada término del texto buscado, un OR
        de coincidencias parciales en cada campo. ``escape_psql`` va antes
        del ``ilike`` igual que en la fuente: nuestro ``condition_to_q``
        envuelve con ``%…%`` y pasa el patrón crudo a ``ILIKE`` (lookup
        ``sql_ilike``), así que los comodines que teclee el usuario deben
        llegar escapados.
        """
        domain = Domain.AND(domain_list)
        if search:
            for search_term in search.split(' '):
                subdomains = [Domain(field, 'ilike', escape_psql(search_term))
                              for field in fields]
                if extra:
                    subdomains.append(extra(search_term))
                domain &= Domain.OR(subdomains)
        return domain

    @classmethod
    def _search_get_detail(cls, website, order, options):
        """≙ ``_search_get_detail`` (``:354-376``) — abstracto, verbatim.

        Cada modelo buscable devuelve su receta: ``model``, ``base_domain``,
        ``search_fields``, ``fetch_fields``, ``mapping`` e ``icon``. Aquí
        ``model`` lleva **la clase del modelo**, no su nombre: #104 alineó
        ``website.page`` (que sí declara ``_name``), pero el interinato
        ``StaticPage`` sigue sin nombre y el consumidor
        (``Website._search_exact``) espera la clase — volver esta clave al
        nombre es de la tarea **#560** (absorción del interinato).
        """
        raise NotImplementedError()

    @classmethod
    def _search_fetch(cls, search_detail, search, limit, order):
        """≙ ``_search_fetch`` (``:378-390``)."""
        fields = search_detail['search_fields']
        base_domain = search_detail['base_domain']
        domain = cls._search_build_domain(
            base_domain, search, fields, search_detail.get('search_extra'))
        query = to_q(domain, cls)
        # ≙ ``model = self.sudo() if requires_sudo else self`` — el queryset
        # es perezoso, así que la evaluación ocurre DENTRO del bloque elevado.
        with sudo(bool(search_detail.get('requires_sudo')) or is_su()):
            queryset = cls.objects.filter(query)
            order_by = order_expression_to_order_by(
                search_detail.get('order', order))
            if order_by:
                queryset = queryset.order_by(*order_by)
            results = list(queryset[:limit]) if limit else list(queryset)
            count = (queryset.count()
                     if limit and limit == len(results) else len(results))
        return results, count

    @classmethod
    def _search_render_results(cls, results, fetch_fields, mapping, icon, limit):
        """≙ ``_search_render_results`` (``:392-407``).

        Prepara las filas para el autocompletado: valores de los campos
        pedidos más ``_fa`` (icono) y ``_mapping``. Los campos marcados
        ``html`` en el mapping se aplanan a texto con ``text_from_html``,
        deshaciendo antes el doble escape del editor cuando el campo es
        ``arch`` — mismo quirk que la fuente comenta.
        """
        results_data = []
        for record in results[:limit]:
            data = {field: getattr(record, field, None)
                    for field in fetch_fields}
            data['_fa'] = icon
            data['_mapping'] = mapping
            results_data.append(data)
        html_fields = [config['name'] for config in mapping.values()
                       if config.get('html')]
        for data in results_data:
            for html_field in html_fields:
                if data.get(html_field):
                    if html_field == 'arch':
                        # Deshacer el segundo escape de los nodos de texto
                        # del editor (wysiwyg _getEscapedElement).
                        data[html_field] = re.sub(
                            r'&amp;(?=\w+;)', '&', data[html_field])
                    data[html_field] = text_from_html(data[html_field], True)
        return results_data


class WebsitePublishedMixin(models.Model):
    """≙ ``website.published.mixin`` (``odoo19c: website/models/mixins.py:201``).

    Abstracto: no crea tabla propia. Lo heredan los modelos que se muestran
    en la tienda (hoy ``ProductTemplate``).
    """

    is_published = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='Publicado',
        help_text='Visible en la tienda. Por defecto NO — igual que '
                  '_default_is_published de la referencia: dar de alta un '
                  'producto no es publicarlo.',
    )

    class Meta:
        abstract = True

    @property
    def website_published(self):
        """≙ ``website_published`` / ``_compute_website_published``
        (``:280``, ``:287-293``) — alias de lectura de ``is_published``.

        La referencia lo declara ``related=…, readonly=False``; aquí es sólo
        lectura (ver el docstring del módulo).
        """
        return self.is_published

    def website_publish_button(self):
        """≙ ``website_publish_button`` (``:230``): alterna y devuelve el valor.

        Se conserva el nombre de la referencia porque el verbo es el mismo —
        el botón de publicar/despublicar de la ficha.
        """
        self.is_published = not self.is_published
        self.save(update_fields=['is_published'])
        return self.is_published

    @classmethod
    def apply_to(cls, model):
        """Aplica la publicación a un modelo **ya definido** — ≙ ``_inherit``.

        Éste es el camino que un addon de sitio usa para publicar un modelo
        que **no le pertenece**, sin tocar su código. Es el análogo directo de
        lo que hace la referencia::

            # odoo19c: website_sale/models/product_template.py:34-42
            class ProductTemplate(models.Model):
                _name = 'product.template'
                _inherit = [… 'website.published.multi.mixin' …]

        Se llama desde el ``ready()`` del addon que declara la dependencia
        (``website_sale``), nunca desde el modelo destino: así ``product``
        queda **cerrado a modificación y abierto a extensión**, y no adquiere
        una razón de cambio que es del escaparate.

        Idempotente: si el campo ya está, no hace nada — ``ready()`` puede
        ejecutarse más de una vez en tests que recargan el registro de apps.
        """
        if not model._meta.get_fields():  # pragma: no cover - defensivo
            raise RuntimeError(
                f'{model.__name__} no está poblado todavía; apply_to debe '
                f'llamarse desde AppConfig.ready(), no en tiempo de import.')

        existing = {f.name for f in model._meta.get_fields()}
        if 'is_published' not in existing:
            field = cls._meta.get_field('is_published').clone()
            model.add_to_class('is_published', field)

        # Los métodos no son campos: se cuelgan directo. No se sobrescriben si
        # el modelo destino ya define los suyos.
        for name in ('website_published', 'website_publish_button'):
            if not hasattr(model, name):
                setattr(model, name, getattr(cls, name))
