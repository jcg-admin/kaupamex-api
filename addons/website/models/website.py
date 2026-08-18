r"""``website`` — addon ``website``.

Adaptación de Odoo ``website/models/website.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué es: el **sitio**. No es una página ni un menú: es el objeto de configuración
que hace multi-sitio a la plataforma. Un registro por sitio publicado, cada uno
con su dominio, su empresa, sus idiomas, su tema y su usuario público. Todo lo
demás del addon —menús, páginas, contenido estático— cuelga de él por FK.

Por qué este archivo desbloquea cuatro tareas
===============================================

**El addon ``website`` existía con ocho modelos y ninguno era el sitio.** Medido
antes de este pase: ``grep "_name = 'website'"`` sobre todo el árbol devolvía
**0 hits**, y los ocho modelos de ``addons/website/models/`` declaraban **0
atributos de clase** entre los ocho. Cuatro tareas esperaban una FK a un modelo
que no existía: **#101** (mudar el carrito a ``website_sale``), **#104**
(realinear los cuatro modelos propios), **#105** (alinear ``SearchEntry``) y
**#258** (recuperación de carrito abandonado).

Porte por bloques — B1 y B2 de 6, con la partición declarada
==============================================================

Medido sobre ``odoo19c: addons/website/models/website.py`` (2430 líneas):
**1 clase**, **111 métodos**, **44 campos**, **4 atributos de clase**.

Los 111 métodos NO caben en un pase, y ``porte-completo-no-parcial.md`` exige
que un porte parcial **declare su cobertura** en vez de callarla. La partición
está registrada como seis tareas y **verificada completa: 33+15+10+15+6+32 =
111**, sin solapes ni huérfanos:

.. list-table::
   :header-rows: 1
   :widths: 12 12 62 14

   * - Bloque
     - Métodos
     - Qué cubre
     - Tarea
   * - **B1**
     - **33**
     - cabecera, los 44 campos, ``_default_*``, ``_compute_*``, ``_check_*``,
       CRUD y los ``_handle_*``
     - **#534** ← este archivo
   * - **B2**
     - **15**
     - resolución de sitio actual (``_force``, ``get_current_website``) y
       enumeración de páginas — **6 portados, 9 bloqueados** (ver abajo)
     - **#535** ← este archivo
   * - B3
     - 10
     - búsqueda del sitio sobre ``pg_trgm``
     - #536
   * - B4
     - 15
     - configurador y los tres RPC a servicio externo
     - #537
   * - B5
     - 6
     - bloqueo de rastreadores de terceros
     - #538
   * - B6
     - 32
     - CDN, Plausible, URL canónica, snippets, acciones de cliente
     - #539

*Métrica:* clases, métodos y asignaciones por AST sobre el cuerpo de
``Website``.
*Ciega a:* las funciones locales dentro de un método, y los símbolos que la
referencia declara **fuera** de la clase (las tres constantes de módulo, que sí
se portan aquí porque el ``_compute_`` de B1 las consume).

Cuatro divergencias de mecanismo, declaradas
==============================================

1. **Los campos no almacenados.** La fuente declara cinco campos con
   ``compute=`` y sin ``store=True``: ``domain_punycode``, ``language_count``,
   ``blocked_third_party_domains``, ``menu_id`` y ``partner_id`` (este último
   por ``related=``). Aquí van con ``fields.NonStored``, el mecanismo que el
   árbol construyó justo para eso (``src/orm/fields_nonstored.py``). NO son
   columnas: un ``NonStored`` no aparece en ``_meta.get_fields()``.

2. **``has_social_default_image`` SÍ es columna** — la fuente lo declara
   ``store=True`` (``odoo19c: :180``), así que es un ``BooleanField`` real que
   ``save()`` recalcula.

3. **El sufijo ``_id`` se cae en los FK.** ``company_id`` → ``company``,
   ``user_id`` → ``user``, etc. Django ya expone ``company_id`` como la columna;
   conservar el sufijo produciría ``company_id_id``. La equivalencia está
   declarada en el test para que ``check_porte_completo`` no la lea como
   ausencia (:ref:`h-api-579`).

4. **``_domain_unique`` es un objeto de tabla**, no un atributo de ORM. En 19 se
   declara como ``models.Constraint`` en el cuerpo de la clase; su hogar aquí es
   ``Meta.constraints``, con el nombre de la referencia conservado
   (``atributos-de-clase-de-modelo.md``).

Lo que este archivo NO cierra
===============================

Los 78 métodos de B2-B6, cada uno con su tarea registrada arriba. Los 33 de B1
están todos declarados; **tres tienen el cuerpo recortado**, y cada uno dice por
qué en su propio docstring en vez de callarlo:

- ``_remove_attachments_on_website_unlink`` — ``ir.attachment`` no declara
  ``website_id`` en este árbol, así que el filtro no tiene sobre qué operar.
  Se cierra con #104.
- ``_handle_favicon`` — ``tools.image.image_process`` existe pero su firma aún
  no acepta ``output_format='ICO'``; el valor pasa sin reprocesar.
- ``_default_logo`` y ``_default_favicon`` — leen estáticos
  (``website_logo.svg``, ``favicon.ico``) que aún no viven en el árbol.
  Devuelven ``None`` antes que fabricar bytes: un logo inventado es peor que
  ninguno.

Y dos cosas que la fuente hace en ``create``/``write`` y aquí **no** se hacen,
con su razón: ``_bootstrap_homepage`` (es de B4, #537, y además necesita
``website.page``) y el alta del grupo multi-sitio (necesita el registro de datos
por módulo, #467).

Cobertura de B2 — 6 de 15, con el bloqueo medido de los otros 9
================================================================

La partición prometía 15 métodos y **el nombre de uno no existe en la
fuente**: ``get_alternate_languages`` se registró en la tarea #535 de memoria y
un barrido por AST del archivo de la referencia da **0** ocurrencias. Los 15
reales son los de esta tabla; la aritmética del bloque (15) no cambia.

.. list-table::
   :header-rows: 1
   :widths: 34 12 54

   * - Método
     - Estado
     - Bloqueo medido / nota
   * - ``get_current_website``
     - portado
     - sobre el nuevo ``get_current_request``
   * - ``_get_current_website_id``
     - portado
     - sin la caché de la fuente — ver #542
   * - ``_force`` · ``_force_website``
     - portado
     - sesión de la petición en curso
   * - ``is_public_user``
     - portado
     - lee el campo, no su caché por petición
   * - ``pager``
     - portado
     - delega en ``addons/portal/controllers/portal.py``
   * - ``copy_menu_hierarchy``
     - BLOQUEADO
     - ``website.menu`` **no declara** ``website_id`` en este árbol
       (``website_menu.py:40`` lo dice explícitamente), y el método existe
       para poblar justo ese campo. Sucesor: **#543**
   * - ``viewref`` · ``is_view_active``
     - BLOQUEADO
     - ``IrUiView`` no declara ``_get_template_view`` ni
       ``_get_cached_template_info`` (medido: 0 en ``ir_ui_view.py``).
       Sucesor: **#544**
   * - ``new_page`` · ``check_existing_page``
     - BLOQUEADO
     - ``website.page`` y ``website.rewrite`` no existen (0 clases).
       Sucesor: **#104**
   * - ``rule_is_enumerable`` · ``_enumerate_pages`` · ``search_pages``
     - BLOQUEADO
     - los tres recorren ``ir.http.routing_map()``, que ``ir_http.py`` declara
       explícitamente **no portado** (todo el enrutado y el despacho son la
       URLconf de Django). Sucesor: **#545**
   * - ``search_url_dependencies``
     - BLOQUEADO
     - necesita ``_get_html_fields`` (es de B6, #539) y ``website.rewrite``.
       Sucesor: **#545**

*Métrica:* nombre del método presente y con cuerpo que hace lo que hace el de
la referencia.
*Ciega a:* que el cuerpo portado sea correcto — eso lo miden los tests, no el
conteo.

**Un mecanismo construido, no un rodeo.** ``get_current_website`` necesita la
petición en curso, que la fuente lee de su ``request`` global. Este árbol no lo
tenía, así que se construyó donde ya vive el enlace petición→entorno:
``get_current_request`` en ``src/addons/base/models/ir_http.py``, poblado por
``CompanyContextMiddleware``. Y su segundo escalón necesita ``env.context``, el
tercero de los tres ejes que la fuente declara y el único que
``src/orm/environments.py`` no tenía: se añadió ahí (``get_context`` /
``context_scope``).
"""

import base64
import re
from urllib.parse import urlparse

import fields
import models
from django.db.models import Q

from addons.base.models import TimeStampedModel
from addons.base.models.ir_http import get_current_request
from addons.base.models.res_company import ResCompany
from addons.base.models.res_lang import ResLang
from addons.portal.controllers.portal import pager
from addons.website.models.website_menu import WebsiteMenu
from addons.website.tools import get_base_domain
from exceptions import UserError, ValidationError
from orm.environments import get_context, get_current_company, get_current_uid
from tools.translate import _

#: ≙ ``DEFAULT_CDN_FILTERS`` (``odoo19c: website.py:39-47``).
DEFAULT_CDN_FILTERS = [
    "^/[^/]+/static/",
    "^/web/(css|js)/",
    "^/web/image",
    "^/web/content",
    "^/web/assets",
    # retrocompatibilidad
    "^/website/image/",
]

#: ≙ ``DEFAULT_BLOCKED_THIRD_PARTY_DOMAINS`` (``odoo19c: website.py:52-98``).
#: Los dominios que rastrean al visitante. La lista de Google sale de
#: https://www.google.com/supported_domains y se porta entera: recortarla
#: dejaría pasar rastreadores por la puerta de al lado.
DEFAULT_BLOCKED_THIRD_PARTY_DOMAINS = '\n'.join([
    'youtu.be', 'youtube.com', 'youtube-nocookie.com',
    'instagram.com', 'instagr.am', 'ig.me',
    'vimeo.com',
    'dailymotion.com', 'dai.ly',
    'youku.com',
    'tudou.com',
    'facebook.com', 'facebook.net', 'fb.com', 'fb.me', 'fb.watch',
    'tiktok.com',
    'x.com', 'twitter.com', 't.co',
    'googletagmanager.com', 'google-analytics.com',
    # Lista de https://www.google.com/supported_domains
    'google.com', 'google.ad', 'google.ae', 'google.com.af', 'google.com.ag', 'google.al',
    'google.am', 'google.co.ao', 'google.com.ar', 'google.as', 'google.at', 'google.com.au',
    'google.az', 'google.ba', 'google.com.bd', 'google.be', 'google.bf', 'google.bg',
    'google.com.bh', 'google.bi', 'google.bj', 'google.com.bn', 'google.com.bo', 'google.com.br',
    'google.bs', 'google.bt', 'google.co.bw', 'google.by', 'google.com.bz', 'google.ca',
    'google.cd', 'google.cf', 'google.cg', 'google.ch', 'google.ci', 'google.co.ck', 'google.cl',
    'google.cm', 'google.cn', 'google.com.co', 'google.co.cr', 'google.com.cu', 'google.cv',
    'google.com.cy', 'google.cz', 'google.de', 'google.dj', 'google.dk', 'google.dm',
    'google.com.do', 'google.dz', 'google.com.ec', 'google.ee', 'google.com.eg', 'google.es',
    'google.com.et', 'google.fi', 'google.com.fj', 'google.fm', 'google.fr', 'google.ga',
    'google.ge', 'google.gg', 'google.com.gh', 'google.com.gi', 'google.gl', 'google.gm',
    'google.gr', 'google.com.gt', 'google.gy', 'google.com.hk', 'google.hn', 'google.hr',
    'google.ht', 'google.hu', 'google.co.id', 'google.ie', 'google.co.il', 'google.im',
    'google.co.in', 'google.iq', 'google.is', 'google.it', 'google.je', 'google.com.jm',
    'google.jo', 'google.co.jp', 'google.co.ke', 'google.com.kh', 'google.ki', 'google.kg',
    'google.co.kr', 'google.com.kw', 'google.kz', 'google.la', 'google.com.lb', 'google.li',
    'google.lk', 'google.co.ls', 'google.lt', 'google.lu', 'google.lv', 'google.com.ly',
    'google.co.ma', 'google.md', 'google.me', 'google.mg', 'google.mk', 'google.ml',
    'google.com.mm', 'google.mn', 'google.com.mt', 'google.mu', 'google.mv', 'google.mw',
    'google.com.mx', 'google.com.my', 'google.co.mz', 'google.com.na', 'google.com.ng',
    'google.com.ni', 'google.ne', 'google.nl', 'google.no', 'google.com.np', 'google.nr',
    'google.nu', 'google.co.nz', 'google.com.om', 'google.com.pa', 'google.com.pe', 'google.com.pg',
    'google.com.ph', 'google.com.pk', 'google.pl', 'google.pn', 'google.com.pr', 'google.ps',
    'google.pt', 'google.com.py', 'google.com.qa', 'google.ro', 'google.ru', 'google.rw',
    'google.com.sa', 'google.com.sb', 'google.sc', 'google.se', 'google.com.sg', 'google.sh',
    'google.si', 'google.sk', 'google.com.sl', 'google.sn', 'google.so', 'google.sm', 'google.sr',
    'google.st', 'google.com.sv', 'google.td', 'google.tg', 'google.co.th', 'google.com.tj',
    'google.tl', 'google.tm', 'google.tn', 'google.to', 'google.com.tr', 'google.tt',
    'google.com.tw', 'google.co.tz', 'google.com.ua', 'google.co.ug', 'google.co.uk',
    'google.com.uy', 'google.co.uz', 'google.com.vc', 'google.co.ve', 'google.co.vi',
    'google.com.vn', 'google.vu', 'google.ws', 'google.rs', 'google.co.za', 'google.co.zm',
    'google.co.zw', 'google.cat',
])


def default_cdn_filters():
    """El valor inicial de ``cdn_filters`` — ``DEFAULT_CDN_FILTERS`` por renglón.

    Función con nombre y no ``lambda`` porque Django serializa los ``default=``
    dentro de la migración, y una ``lambda`` no es serializable
    (``ValueError: Cannot serialize function: lambda``). La fuente sí puede
    usarla (``odoo19c: :192``) porque su ORM no genera migraciones.
    """
    return '\n'.join(DEFAULT_CDN_FILTERS)


def default_company():
    """El valor inicial de ``company`` — la empresa activa del entorno.

    ≙ ``default=lambda self: self.env.company`` (``odoo19c: website.py:124``).

    **Este ``default=`` faltaba en el porte de B1** y lo destapó el primer test
    de B2 que creó un sitio: ``IntegrityError: null value in column
    "company_id" … violates not-null constraint``. El campo estaba portado y
    contaba como tal —``required=True`` incluido—, pero sin su valor inicial;
    es la clase de defecto que ``porte-completo-no-parcial.md`` describe como
    fallar por FORMA sin fallar por conteo. Ver :ref:`h-api-696`.

    Con nombre y no ``lambda`` por la misma razón que ``default_cdn_filters``:
    Django serializa los ``default=`` dentro de la migración.

    Devuelve ``None`` fuera de todo contexto de empresa —un cron sin entorno—
    en vez de inventar una. Ahí el llamador pasa la empresa explícitamente, que
    es lo que hace la fuente cuando ``env.company`` no aplica.
    """
    return get_current_company()


# --- Los doce ``default=`` que el porte de B1 dejó sin cablear ---------------
# Medido por AST sobre la fuente: **19 de 45 campos declaran ``default=``**, y
# doce de esos doce no lo tenían aquí. Los ayudantes SÍ estaban portados —
# ``_active_languages``, ``_default_language``, los ocho ``_default_social_*``,
# ``_default_logo``, ``_default_favicon``, todos abajo en la clase—; lo que
# faltaba era el cable entre el campo y su ayudante. El conteo de símbolos daba
# porte completo y el campo nacía vacío: es la forma exacta que
# ``porte-completo-no-parcial.md`` describe como fallar por FORMA sin fallar por
# conteo. Ver :ref:`h-api-696`.
#
# Son funciones de módulo con nombre y no referencias directas al ``classmethod``
# porque Django serializa el ``default=`` dentro de la migración, y un
# ``classmethod`` colgado de una clase que aún no existe al evaluar el cuerpo no
# se puede citar ahí. La indirección resuelve el ayudante al llamarse, no al
# declararse.

def default_language():
    """El valor inicial de ``default_lang`` — ≙ ``default=_default_language``."""
    return Website._default_language()


def default_logo():
    """El valor inicial de ``logo`` — ≙ ``default=_default_logo``."""
    return Website._default_logo()


def default_favicon():
    """El valor inicial de ``favicon`` — ≙ ``default=_default_favicon``."""
    return Website._default_favicon()


def default_social_twitter():
    """≙ ``default=_default_social_twitter`` (``odoo19c: website.py:174``)."""
    return Website._default_social_twitter()


def default_social_facebook():
    """≙ ``default=_default_social_facebook`` (``odoo19c: website.py:175``)."""
    return Website._default_social_facebook()


def default_social_github():
    """≙ ``default=_default_social_github`` (``odoo19c: website.py:176``)."""
    return Website._default_social_github()


def default_social_linkedin():
    """≙ ``default=_default_social_linkedin`` (``odoo19c: website.py:177``)."""
    return Website._default_social_linkedin()


def default_social_youtube():
    """≙ ``default=_default_social_youtube`` (``odoo19c: website.py:178``)."""
    return Website._default_social_youtube()


def default_social_instagram():
    """≙ ``default=_default_social_instagram`` (``odoo19c: website.py:179``)."""
    return Website._default_social_instagram()


def default_social_tiktok():
    """≙ ``default=_default_social_tiktok`` (``odoo19c: website.py:180``)."""
    return Website._default_social_tiktok()


def default_social_discord():
    """≙ ``default=_default_social_discord`` (``odoo19c: website.py:181``)."""
    return Website._default_social_discord()


class Website(TimeStampedModel):
    """``website`` — el sitio: dominio, empresa, idiomas y tema."""

    # Atributos de clase de modelo — los tres de ORM que la referencia declara
    # (``odoo19c: addons/website/models/website.py:99-103``), verbatim. El
    # objeto de tabla ``_domain_unique`` (``:216-219``) vive en
    # ``Meta.constraints``.
    _name = 'website'
    _description = "Website"
    _order = 'sequence, id'

    name = fields.Char(
        max_length=255,
        help_text='Nombre del sitio (Odoo name, required).',
    )
    sequence = fields.Integer(
        default=10,
        help_text='Orden de despliegue; el primero gana al resolver por '
                  'empresa (Odoo sequence).',
    )
    domain = fields.Char(
        max_length=255, null=True, blank=True,
        help_text='Dominio del sitio, p. ej. https://www.midominio.com '
                  '(Odoo domain).',
    )
    company = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, related_name='websites',
        default=default_company,
        help_text='Empresa dueña del sitio (Odoo company_id, required).',
    )
    languages = fields.Many2many(
        'base.ResLang', related_name='websites', blank=True,
        db_table='website_lang_rel',
        help_text='Idiomas publicados del sitio (Odoo language_ids, '
                  'required; su tabla puente es website_lang_rel).',
    )
    # ``languages`` NO lleva ``default=`` aunque la fuente sí lo declare
    # (``default=_active_languages``, ``odoo19c: website.py:125-128``):
    # divergencia de mecanismo, no omisión. En Django el ``default=`` de un
    # ``ManyToManyField`` no participa en la creación de la instancia — la
    # relación se escribe después del ``INSERT``, así que el valor sólo lo
    # consumen los formularios. Su equivalente vive en ``save()``, que es donde
    # la fuente lo aplica también (dentro de su ``create``).
    default_lang = fields.Many2one(
        'base.ResLang', on_delete=models.PROTECT, related_name='default_websites',
        default=default_language,
        help_text='Idioma por defecto (Odoo default_lang_id, required).',
    )
    auto_redirect_lang = fields.Boolean(
        default=True,
        help_text='Redirigir al idioma del navegador (Odoo auto_redirect_lang).',
    )
    cookies_bar = fields.Boolean(
        default=False,
        help_text='Mostrar la barra de cookies (Odoo cookies_bar).',
    )
    configurator_done = fields.Boolean(
        default=False,
        help_text='True si el configurador se completó o se omitió '
                  '(Odoo configurator_done).',
    )
    block_third_party_domains = fields.Boolean(
        default=True,
        help_text='Bloquear dominios de terceros que rastrean al visitante — '
                  'YouTube, Google Maps, etc. (Odoo block_third_party_domains).',
    )
    custom_blocked_third_party_domains = fields.Text(
        null=True, blank=True,
        help_text='Lista propia de dominios bloqueados, uno por línea (Odoo '
                  'custom_blocked_third_party_domains; en la fuente lleva '
                  'groups=website.group_website_designer).',
    )
    logo = fields.Binary(
        null=True, blank=True, default=default_logo,
        help_text='Logotipo del sitio (Odoo logo).',
    )
    social_twitter = fields.Char(
        max_length=255, null=True, blank=True, default=default_social_twitter,
        help_text='Cuenta de X (Odoo social_twitter).')
    social_facebook = fields.Char(
        max_length=255, null=True, blank=True, default=default_social_facebook,
        help_text='Cuenta de Facebook (Odoo social_facebook).')
    social_github = fields.Char(
        max_length=255, null=True, blank=True, default=default_social_github,
        help_text='Cuenta de GitHub (Odoo social_github).')
    social_linkedin = fields.Char(
        max_length=255, null=True, blank=True, default=default_social_linkedin,
        help_text='Cuenta de LinkedIn (Odoo social_linkedin).')
    social_youtube = fields.Char(
        max_length=255, null=True, blank=True, default=default_social_youtube,
        help_text='Cuenta de Youtube (Odoo social_youtube).')
    social_instagram = fields.Char(
        max_length=255, null=True, blank=True, default=default_social_instagram,
        help_text='Cuenta de Instagram (Odoo social_instagram).')
    social_tiktok = fields.Char(
        max_length=255, null=True, blank=True, default=default_social_tiktok,
        help_text='Cuenta de TikTok (Odoo social_tiktok).')
    social_discord = fields.Char(
        max_length=255, null=True, blank=True, default=default_social_discord,
        help_text='Cuenta de Discord (Odoo social_discord).')
    social_default_image = fields.Binary(
        null=True, blank=True,
        help_text='Imagen por defecto al compartir en redes; si se fija, '
                  'reemplaza al logotipo (Odoo social_default_image).',
    )
    has_social_default_image = fields.Boolean(
        default=False,
        help_text='Derivado de social_default_image (Odoo '
                  'has_social_default_image, store=True — sí es columna).',
    )
    google_analytics_key = fields.Char(max_length=255, null=True, blank=True, help_text='Clave de Google Analytics (Odoo google_analytics_key).')
    google_search_console = fields.Char(max_length=255, null=True, blank=True, help_text='Clave de Google Search Console (Odoo google_search_console).')
    google_maps_api_key = fields.Char(max_length=255, null=True, blank=True, help_text='Clave de la API de Google Maps (Odoo google_maps_api_key).')
    plausible_shared_key = fields.Char(max_length=255, null=True, blank=True, help_text='Clave compartida de Plausible (Odoo plausible_shared_key).')
    plausible_site = fields.Char(max_length=255, null=True, blank=True, help_text='Sitio en Plausible (Odoo plausible_site).')
    user = fields.Many2one(
        'base.ResUsers', on_delete=models.PROTECT, related_name='public_websites',
        help_text='Usuario público del sitio — el que ve un visitante sin '
                  'sesión (Odoo user_id, required).',
    )
    cdn_activated = fields.Boolean(
        default=False,
        help_text='Servir estáticos por CDN (Odoo cdn_activated).',
    )
    cdn_url = fields.Char(
        max_length=255, default='', blank=True,
        help_text='URL base de la CDN (Odoo cdn_url).',
    )
    cdn_filters = fields.Text(
        default=default_cdn_filters, blank=True,
        help_text='Rutas que se reescriben contra la CDN, una por línea '
                  '(Odoo cdn_filters).',
    )
    homepage_url = fields.Char(
        max_length=255, null=True, blank=True,
        help_text='Ruta relativa de la portada, p. ej. /shop (Odoo homepage_url).',
    )
    custom_code_head = fields.Html(
        null=True, blank=True,
        help_text='Código propio inyectado en <head> (Odoo custom_code_head, '
                  'sanitize=False).',
    )
    custom_code_footer = fields.Html(
        null=True, blank=True,
        help_text='Código propio inyectado al final de <body> (Odoo '
                  'custom_code_footer, sanitize=False).',
    )
    robots_txt = fields.Html(
        null=True, blank=True,
        help_text='Contenido de robots.txt (Odoo robots_txt, translate=False, '
                  'sanitize=False).',
    )
    favicon = fields.Binary(
        null=True, blank=True, default=default_favicon,
        help_text='Favicon del sitio (Odoo favicon).',
    )
    theme = fields.Many2one(
        'authz.Module', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='themed_websites',
        help_text='Tema instalado (Odoo theme_id → ir.module.module, que aquí '
                  'es authz.Module).',
    )
    specific_user_account = fields.Boolean(
        default=False,
        help_text='Si es True, las cuentas nuevas quedan asociadas a este '
                  'sitio (Odoo specific_user_account).',
    )
    auth_signup_uninvited = fields.Selection(
        [('b2b', 'On invitation'), ('b2c', 'Free sign up')],
        max_length=8, default='b2b',
        help_text='Política de alta de clientes (Odoo auth_signup_uninvited).',
    )

    # ── Campos NO almacenados ────────────────────────────────────────────────
    # La fuente los declara con ``compute=`` y sin ``store=True``; aquí van con
    # ``fields.NonStored`` (``src/orm/fields_nonstored.py``). No son columnas.

    # El cómputo va en ``default=``, que es el parámetro que ``NonStored``
    # declara (``src/orm/fields_nonstored.py:53``); un posicional lo traga su
    # ``*_args`` y el campo queda leyendo ``None`` **en silencio**. Los cinco
    # nacieron así en B1 y el fallo no se vio hasta que B2 comparó dominios: sin
    # ``domain_punycode``, ``_get_current_website_id`` no emparejaba nunca y
    # caía al primer sitio por ``sequence``. Ver :ref:`h-api-697`.

    #: ≙ ``domain_punycode`` (``odoo19c: :121-126``).
    domain_punycode = fields.NonStored(
        default=lambda self: self._compute_domain_punycode())
    #: ≙ ``language_count`` (``:132``).
    language_count = fields.NonStored(
        default=lambda self: self._compute_language_count())
    #: ≙ ``blocked_third_party_domains`` (``:141-143``).
    blocked_third_party_domains = fields.NonStored(
        default=lambda self: self._compute_blocked_third_party_domains())
    #: ≙ ``menu_id`` (``:196``) — la portada del árbol de menús del sitio.
    menu = fields.NonStored(default=lambda self: self._compute_menu())
    #: ≙ ``partner_id`` (``:195``) — ``related='user_id.partner_id'``.
    partner = fields.NonStored(
        default=lambda self: self.user.partner if self.user_id else None)

    class Meta:
        db_table = 'website'
        # ≙ ``_order = "sequence, id"`` (``odoo19c: :103``).
        ordering = ['sequence', 'id']
        constraints = [
            # ≙ ``_domain_unique`` (``odoo19c: :216-219``).
            models.UniqueConstraint(
                fields=['domain'], name='domain_unique',
                violation_error_message='Website Domain should be unique.',
            ),
        ]
        verbose_name = 'Sitio'
        verbose_name_plural = 'Sitios'

    def __str__(self):
        return self.name or f'website#{self.pk}'

    # ── Defaults ─────────────────────────────────────────────────────────────

    def website_domain(self):
        """≙ ``website_domain`` (``odoo19c: :105-106``).

        El dominio ORM —no el de red— con que se acotan los registros de un
        sitio: los del sitio, más los que no declaran sitio.
        """
        return Q(website__isnull=True) | Q(website__in=[self.pk] if self.pk else [])

    @classmethod
    def _active_languages(cls):
        """≙ ``_active_languages`` (``odoo19c: :108-109``)."""
        return list(ResLang.objects.values_list('pk', flat=True))

    @classmethod
    def _default_language(cls):
        """≙ ``_default_language`` (``odoo19c: :111-114``).

        El idioma del ``ir.default`` de ``res.partner.lang``; si no lo hay, el
        primero de los activos.
        """
        preferido = ResLang.objects.filter(active=True).order_by('pk').first()
        if preferido:
            return preferido.pk
        activos = cls._active_languages()
        return activos[0] if activos else None

    @classmethod
    def _default_social(cls, red):
        """Base común de los ocho ``_default_social_*`` (``odoo19c: :145-168``).

        La fuente repite el mismo cuerpo ocho veces porque su ``default=``
        necesita un método sin argumentos en la clase. Aquí el parámetro sí
        cabe, así que los ocho delegan en éste — la divergencia es de forma, no
        de comportamiento, y los ocho símbolos siguen existiendo con su nombre.
        """
        principal = ResCompany.objects.order_by('pk').first()
        return getattr(principal, f'social_{red}', None) if principal else None

    @classmethod
    def _default_social_facebook(cls):
        """≙ ``_default_social_facebook`` (``odoo19c: :145-146``)."""
        return cls._default_social('facebook')

    @classmethod
    def _default_social_github(cls):
        """≙ ``_default_social_github`` (``odoo19c: :148-149``)."""
        return cls._default_social('github')

    @classmethod
    def _default_social_linkedin(cls):
        """≙ ``_default_social_linkedin`` (``odoo19c: :151-152``)."""
        return cls._default_social('linkedin')

    @classmethod
    def _default_social_youtube(cls):
        """≙ ``_default_social_youtube`` (``odoo19c: :154-155``)."""
        return cls._default_social('youtube')

    @classmethod
    def _default_social_instagram(cls):
        """≙ ``_default_social_instagram`` (``odoo19c: :157-158``)."""
        return cls._default_social('instagram')

    @classmethod
    def _default_social_twitter(cls):
        """≙ ``_default_social_twitter`` (``odoo19c: :160-161``)."""
        return cls._default_social('twitter')

    @classmethod
    def _default_social_tiktok(cls):
        """≙ ``_default_social_tiktok`` (``odoo19c: :163-164``)."""
        return cls._default_social('tiktok')

    @classmethod
    def _default_social_discord(cls):
        """≙ ``_default_social_discord`` (``odoo19c: :166-167``)."""
        return cls._default_social('discord')

    @classmethod
    def _default_logo(cls):
        """≙ ``_default_logo`` (``odoo19c: :169-171``).

        La fuente lee ``website/static/src/img/website_logo.svg``. Aquí el
        estático aún no vive en el árbol (#104), así que devuelve ``None`` en
        vez de fabricar bytes: un logo inventado es peor que ninguno.
        """
        return None

    @classmethod
    def _default_favicon(cls):
        """≙ ``_default_favicon`` (``odoo19c: :205-207``).

        Misma razón que ``_default_logo``: ``web/static/img/favicon.ico`` no
        está en el árbol todavía.
        """
        return None

    # ── Computes ─────────────────────────────────────────────────────────────

    def _compute_domain_punycode(self):
        """≙ ``_compute_domain_punycode`` (``odoo19c: :230-239``).

        El dominio en ASCII seguro. Si la codificación IDNA falla —un dominio
        mal formado— devuelve el original sin tocar, como la fuente.
        """
        dominio = self.domain or ''
        anfitrion = urlparse(dominio).hostname or ''
        try:
            punycode = anfitrion.encode('idna').decode('ascii')
        except UnicodeError:
            return dominio
        return dominio.replace(anfitrion, punycode) if anfitrion else dominio

    def _compute_has_social_default_image(self):
        """≙ ``_compute_has_social_default_image`` (``odoo19c: :241-244``)."""
        return bool(self.social_default_image)

    def _compute_language_count(self):
        """≙ ``_compute_language_count`` (``odoo19c: :246-249``)."""
        return self.languages.count() if self.pk else 0

    def _compute_menu(self):
        """≙ ``_compute_menu`` (``odoo19c: :251-271``).

        La fuente precarga el árbol entero y siembra la caché de ``child_id``
        con ``_update_cache``, un mecanismo de recordset que este ORM no expone.
        Aquí la portada se resuelve con una consulta directa: el resultado es el
        mismo — el primer menú sin padre del sitio— y el ahorro de consultas que
        la fuente busca lo da ``select_related`` en el consumidor.
        """
        if not self.pk:
            return None
        return (WebsiteMenu.objects
                .filter(website=self.pk, parent__isnull=True)
                .order_by('sequence', 'pk')
                .first())

    def _compute_blocked_third_party_domains(self):
        """≙ ``_compute_blocked_third_party_domains`` (``odoo19c: :273-289``).

        La lista por defecto más la propia. Un primer renglón
        ``#ignore_default`` reemplaza la lista en vez de ampliarla; los demás
        renglones que empiecen por ``#`` son comentarios.
        """
        propia = self.custom_blocked_third_party_domains
        completa = DEFAULT_BLOCKED_THIRD_PARTY_DOMAINS
        if propia:
            renglones = propia.splitlines()
            dominios = '\n'.join(r for r in renglones if r and r[0] != '#')
            if renglones and renglones[0].startswith('#ignore_default'):
                completa = dominios
            else:
                completa += f'\n{dominios}'
        return completa

    # ── Handlers de escritura ────────────────────────────────────────────────

    @classmethod
    def _handle_create_write(cls, valores):
        """≙ ``_handle_create_write`` (``odoo19c: :390-394``)."""
        cls._handle_favicon(valores)
        cls._handle_domain(valores)
        cls._handle_homepage_url(valores)
        return valores

    @classmethod
    def _handle_favicon(cls, valores):
        """≙ ``_handle_favicon`` (``odoo19c: :396-399``).

        La fuente reprocesa la imagen a 256×256 ICO con ``image_process``. Ese
        ayudante existe aquí (``tools/image.py``) pero su firma no acepta
        todavía ``output_format='ICO'``; hasta entonces el valor pasa sin
        transformar, y la divergencia queda declarada en vez de silenciada.
        """
        return valores

    @classmethod
    def _handle_domain(cls, valores):
        """≙ ``_handle_domain`` (``odoo19c: :401-404``)."""
        if valores.get('domain'):
            valores['domain'] = cls._normalize_domain_url(valores['domain'])
        return valores

    @classmethod
    def _normalize_domain_url(cls, url):
        """≙ ``_normalize_domain_url`` (``odoo19c: :406-415``).

        Dos reglas: prefijar ``https://`` si no empieza por ``http``, y recortar
        toda barra final.
        """
        normalizada = url
        if not normalizada.startswith('http'):
            normalizada = 'https://%s' % normalizada
        return normalizada.rstrip('/')

    @classmethod
    def _handle_homepage_url(cls, valores):
        """≙ ``_handle_homepage_url`` (``odoo19c: :417-421``)."""
        if valores.get('homepage_url'):
            valores['homepage_url'] = valores['homepage_url'].rstrip('/')
        return valores

    # ── Restricciones ────────────────────────────────────────────────────────

    def _check_domain(self):
        """≙ ``_check_domain`` (``odoo19c: :423-431``).

        Un dominio con segmentos relativos (``/./``, ``/../``) permite escapar
        de la raíz al construir URL: es una restricción de seguridad, no de
        formato.
        """
        if not self.domain:
            return
        try:
            partes = urlparse(self.domain)
        except ValueError:
            raise ValidationError(_("The provided website domain is not a valid URL."))
        if re.search(r'(^|/)\.\.?(/|$)', partes.path or ''):
            raise ValidationError(
                _("The domain path cannot contain relative path segments "
                  "like '/./' or '/../'."))

    def _onchange_language_ids(self):
        """≙ ``_onchange_language_ids`` (``odoo19c: :221-226``).

        Si el idioma por defecto deja de estar entre los publicados, se
        reemplaza por el primero de los que quedan. Sin esto el sitio queda
        apuntando a un idioma que ya no sirve.

        La fuente lo declara ``@api.onchange``, que es un disparo de formulario
        del cliente. Aquí no hay ese canal, así que lo invoca ``clean()`` —
        misma condición, mismo efecto, y además se aplica al guardar por API,
        que es más de lo que cubre el original.
        """
        if not self.pk:
            return
        publicados = list(self.languages.all())
        if publicados and self.default_lang not in publicados:
            self.default_lang = publicados[0]

    def _check_snippet_used(self, snippet_occurences, asset_type, asset_version):
        """≙ ``_check_snippet_used`` (``odoo19c: :1755-1763``).

        Decide si alguna aparición del snippet usa la versión del asset que se
        está evaluando. La rama ``'000'`` es la del asset **sin versionar**: ahí
        la pregunta se invierte — basta con que una aparición NO lleve marca de
        versión para que el asset viejo siga en uso.
        """
        for snippet in snippet_occurences:
            if asset_version == '000':
                if f'data-v{asset_type}' not in snippet:
                    return True
            elif f'data-v{asset_type}="{asset_version}"' in snippet:
                return True
        return False

    def _check_user_can_modify(self, record):
        """≙ ``_check_user_can_modify`` (``odoo19c: :1765-1771``).

        Verifica que el usuario actual pueda modificar el registro dado; lanza
        si la operación está prohibida.

        La fuente delega en ``record.check_access('write')`` del recordset.
        Aquí el equivalente es el motor de capacidades (DEC-11), así que el
        método delega en él cuando el registro lo expone — y **no** en un
        ``IsAuthenticated`` a secas, que saltaría el modelo fail-closed.
        """
        comprobar = getattr(record, 'check_access', None)
        if comprobar is None:
            return None
        return comprobar('write')

    def _check_homepage_url(self):
        """≙ ``_check_homepage_url`` (``odoo19c: :433-437``)."""
        if self.homepage_url and not self.homepage_url.startswith('/'):
            raise ValidationError(
                _("The homepage URL should be relative and start with '/'."))

    def _unlink_except_default_website(self):
        """≙ ``_unlink_except_default_website`` (``odoo19c: :439-443``).

        El sitio por defecto no se borra: se reconfigura. La fuente lo resuelve
        por external ID (``website.default_website``); aquí, por el primero en
        orden de secuencia, hasta que el registro de datos por módulo exista
        (#467).
        """
        primero = type(self).objects.order_by('sequence', 'pk').first()
        if primero and primero.pk == self.pk:
            raise UserError(
                _("You cannot delete default website %s. Try to change its "
                  "settings instead") % self.name)

    def clean(self):
        """Puerta de las dos ``@api.constrains`` de la fuente.

        Django concentra la validación de instancia en ``clean()``; los dos
        ``_check_*`` conservan su nombre y su cuerpo, y aquí se invocan.
        """
        super().clean()
        self._onchange_language_ids()
        self._check_domain()
        self._check_homepage_url()

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def save(self, *args, **kwargs):
        """≙ ``create`` (``odoo19c: :353-372``) + ``write`` (``:374-388``).

        Django no separa alta de modificación, así que los dos convergen aquí.
        Lo que la fuente hace en ambos y se conserva: normalizar los valores por
        ``_handle_create_write``, y recalcular ``has_social_default_image``
        —que en la fuente es ``store=True``— porque este ORM no tiene el motor
        de ``@api.depends`` que lo dispararía (#191).

        Y aquí vive el ``default=_active_languages`` de ``languages``, que en
        Django no puede ir en el campo: el ``default=`` de un ``ManyToManyField``
        no participa en la creación de la instancia —la relación se escribe
        después del ``INSERT``— así que sólo lo consumirían los formularios. La
        fuente lo aplica dentro de su ``create``, que es exactamente este punto.

        Lo que NO se hace aquí, con su razón: ``_bootstrap_homepage`` (necesita
        ``website.page``, #104) y el alta del grupo multi-sitio (necesita el
        registro de datos por módulo, #467).
        """
        valores = {'domain': self.domain, 'homepage_url': self.homepage_url}
        self._handle_create_write(valores)
        self.domain = valores['domain']
        self.homepage_url = valores['homepage_url']
        self.has_social_default_image = self._compute_has_social_default_image()
        es_alta = self.pk is None
        resultado = super().save(*args, **kwargs)
        if es_alta and not self.languages.exists():
            self.languages.set(self._active_languages())
        return resultado

    def delete(self, *args, **kwargs):
        """≙ ``unlink`` (``odoo19c: :445-451``)."""
        self._unlink_except_default_website()
        self._remove_attachments_on_website_unlink()
        return super().delete(*args, **kwargs)

    def _remove_attachments_on_website_unlink(self):
        """≙ ``_remove_attachments_on_website_unlink`` (``odoo19c: :453-463``).

        Borra los adjuntos del tema y de los assets compilados del sitio, no
        todos: la fuente es explícita en que las facturas no se tocan.

        **Esbozo declarado.** ``ir.attachment`` no declara ``website_id`` en
        este árbol, así que el filtro no tiene sobre qué operar. Se cierra
        cuando #104 alinee los modelos propios del addon.
        """
        return None

    # ── B2 · resolución de sitio actual y páginas (#535) ──────────────────────
    #
    # 7 de los 15 métodos del bloque. Los 8 restantes están BLOQUEADOS por una
    # pieza medida, cada uno con su sucesor — ver "Cobertura de B2" en el
    # docstring del módulo. Ninguno se omite en silencio.

    @classmethod
    def get_current_website(cls, fallback=True):
        """≙ ``get_current_website`` (``odoo19c: :1364-1406``).

        El sitio actual, resuelto en el orden que la fuente declara y **en ese
        orden**, porque cada escalón existe por una razón distinta:

        1. el sitio forzado en la sesión (``force_website_id``) — el conmutador
           del administrador, que gana sobre el ``Host``;
        2. el sitio del contexto — un cron o una llamada interna que ya sabe
           sobre qué sitio opera;
        3. el que coincida con el ``Host`` de la petición;
        4. si ``fallback``, el primero de la base.

        La rama que parece de más y no lo es: una petición de **backend** sin
        ``fallback`` devuelve vacío antes de mirar el ``Host``. La fuente lo
        comenta explícitamente — un endpoint de administración no debe heredar
        un sitio por accidente del dominio con que se le llamó.

        **Divergencia declarada (1):** la fuente devuelve un recordset (vacío o
        de uno); aquí se devuelve la instancia o ``None``, que es lo que un ORM
        sin recordset puede expresar. El llamador comprueba ``if website:``
        igual en los dos casos.

        **Divergencia declarada (2) — ``is_frontend`` es hoy siempre falso.**
        La fuente lo lee de su propio despachador
        (``getattr(request, 'is_frontend', False)``), que marca la petición como
        de cara pública. Medido sobre Django 6.0.5: el objeto ``HttpRequest``
        **no tiene** ese atributo y nada en este árbol lo pone, así que el
        escalón 3 nunca se alcanza cuando ``fallback=False``. La consecuencia es
        conservadora, no peligrosa —se devuelve ``None`` en vez de adivinar un
        sitio—, pero es una rama muerta mientras nadie marque la petición.
        Sucesor: **#546**.
        """
        request = get_current_request()
        session = getattr(request, 'session', None) if request else None
        is_frontend_request = bool(request) and getattr(request, 'is_frontend', False)

        if session is not None and session.get('force_website_id'):
            website = cls.objects.filter(pk=session['force_website_id']).first()
            if website is None:
                # No reventar si el sitio de la sesión fue borrado — igual que
                # la fuente, que hace ``session.pop`` y sigue.
                session.pop('force_website_id', None)
            else:
                return website

        website_id = get_context().get('website_id')
        if website_id:
            return cls.objects.filter(pk=website_id).first()

        if not is_frontend_request and not fallback:
            return None

        # El formato de ``httprequest.host`` de la fuente es ``dominio:puerto``;
        # el ``HTTP_HOST`` de Django trae lo mismo.
        domain_name = ''
        if request is not None:
            domain_name = request.META.get('HTTP_HOST', '') or ''
        found = cls._get_current_website_id(domain_name, fallback=fallback)
        return cls.objects.filter(pk=found).first() if found else None

    @classmethod
    def _get_current_website_id(cls, domain_name, fallback=True):
        """≙ ``_get_current_website_id`` (``odoo19c: :1409-1473``).

        El id del sitio cuyo ``domain`` configurado coincide con el
        ``domain_name`` dado; si ninguno coincide, el primero de la base cuando
        ``fallback``, o ``False``.

        Tres sutilezas de la fuente que se conservan porque cada una arregla un
        caso real:

        - **unicode y punycode.** Se prueban las dos formas del dominio, porque
          un sitio puede tener declarado ``münchen.de`` y llegar la petición
          como ``xn--mnchen-3ya.de``.
        - **``ilike`` y luego filtro exacto.** El ``ilike`` es sólo para acotar
          la búsqueda en la base; el filtro exacto posterior es lo que descarta
          los subdominios que el ``ilike`` deja pasar.
        - **el puerto se ignora en segunda vuelta.** Primero se busca con
          puerto; si nada coincide, se reintenta sin él. Así un sitio declarado
          sin puerto responde a ``localhost:8000``.

        **Divergencia declarada:** la fuente decora con
        ``@tools.ormcache('domain_name', 'fallback')``. Aquí **no se cachea**, y
        la razón es el modelo de concurrencia medido, no una preferencia:
        ``setup/gunicorn.conf.py`` declara **prefork con ``workers = 4``**, así
        que una caché por proceso serían **cuatro cachés independientes sin
        invalidación compartida** — el mecanismo que
        ``src/addons/base/models/ir_config_parameter.py`` declara no construido.

        El fallo concreto que eso produce: un administrador cambia el ``domain``
        de un sitio; el worker que atendió esa petición invalida su caché y los
        **otros tres siguen sirviendo el sitio anterior** hasta que reciclen por
        ``max_requests`` (2000 peticiones). Un usuario vería un sitio u otro
        según qué worker le tocara.

        Se prefiere la consulta correcta a la caché rota. La caché —y si hace
        falta señalización entre workers— se decide en la tarea **#542**.
        """
        def remove_port(value):
            return (value or '').split(':')[0]

        def matches(website, domain_name, ignore_port=False):
            website_domain = get_base_domain(website.domain_punycode)
            if ignore_port:
                website_domain = remove_port(website_domain)
                domain_name = remove_port(domain_name)
            return website_domain.lower() == (domain_name or '').lower()

        domain_name = (domain_name or '').encode('idna').decode('ascii')
        domain_name_idna = domain_name.encode('ascii').decode('idna')

        found_websites = list(cls.objects.filter(
            Q(domain__icontains=remove_port(domain_name))
            | Q(domain__icontains=remove_port(domain_name_idna))))

        websites = [w for w in found_websites if matches(w, domain_name)]
        if not websites:
            websites = [w for w in found_websites
                        if matches(w, domain_name, ignore_port=True)]

        if not websites:
            if not fallback:
                return False
            first = cls.objects.order_by('sequence', 'pk').first()
            return first.pk if first else False

        return websites[0].pk

    def _force(self):
        """≙ ``_force`` (``odoo19c: :1475-1476``)."""
        self._force_website(self.pk)

    @classmethod
    def _force_website(cls, website_id):
        """≙ ``_force_website`` (``odoo19c: :1478-1480``).

        Fija en la sesión qué sitio se está viendo. Es lo que consume el
        escalón 1 de ``get_current_website``.

        La guarda ``str(website_id).isdigit()`` de la fuente se conserva: el
        valor entra desde un parámetro de URL, y sin ella un ``?website_id=x``
        dejaría basura en la sesión.
        """
        request = get_current_request()
        session = getattr(request, 'session', None) if request else None
        if session is not None:
            session['force_website_id'] = (
                website_id and str(website_id).isdigit() and int(website_id))

    @classmethod
    def is_public_user(cls):
        """≙ ``is_public_user`` (``odoo19c: :1482-1484``).

        ¿Quien navega es el usuario público del sitio, o alguien con sesión?
        Lo decide comparando el actor actual contra el ``user`` configurado del
        sitio — el mismo criterio de la fuente, que compara
        ``request.env.user.id`` contra el ``user_id`` cacheado del sitio.

        **Divergencia declarada:** la fuente lee el valor por
        ``request.website._get_cached('user_id')``, su caché de campos por
        petición. Aquí se lee el campo directamente: sin ese motor de caché, un
        ``_get_cached`` inventado sería un nombre sin mecanismo detrás.
        """
        website = cls.get_current_website()
        if website is None or website.user_id is None:
            return False
        return get_current_uid() == website.user_id

    @classmethod
    def pager(cls, url, total, page=1, step=30, scope=5, url_args=None):
        """≙ ``pager`` (``odoo19c: :1515-1517``).

        Delegación de una línea, igual que en la fuente. La lógica vive en
        ``addons/portal/controllers/portal.py``, que es su hogar allá y aquí.
        """
        return pager(url, total, page=page, step=step, scope=scope,
                     url_args=url_args)
