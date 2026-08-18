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

Porte por bloques — B1 a B6 de 6, con la partición declarada
==============================================================

Medido sobre ``odoo19c: addons/website/models/website.py`` (2430 líneas):
**1 clase**, **111 métodos**, **44 campos**, **4 atributos de clase**.

Los 111 métodos NO caben en un pase, y ``porte-completo-no-parcial.md`` exige
que un porte parcial **declare su cobertura** en vez de callarla. La partición
se registró como seis tareas con la aritmética **33+15+10+15+6+32 = 111**;
tres bloques se re-midieron al ejecutarlos — B4 dio 21 (no 15), B5 dio 8
(no 6) y B6 dio 42 (no 32), cada uno con su nota en la tabla — así que las
cifras de la tabla son las medidas, y la suma original queda como la
estimación registrada. Las cifras medidas de los bloques suman más de 111
porque los bloqueados de B2/B4 se cuentan dos veces: en su bloque y en B6,
que por definición es «lo que la clase aún no declara por nombre»:

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
   * - **B4**
     - **21** (re-medido; la estimación decía 15)
     - configurador y los tres RPC a servicio externo — **12 portados,
       9 bloqueados** (ver el banner del bloque B4)
     - **#537** ← este archivo
   * - **B5**
     - **8** (re-medido; la partición decía 6)
     - bloqueo de rastreadores de terceros — **8 portados**. Los dos
       ayudantes de la lista (``:291-301``) no estaban en los 33 declarados
       de B1 (medido: 0 hits de ``_get_blocked_third_party_domains_list``
       antes de este pase), así que se portan aquí, donde está su consumidor
     - **#538** ← este archivo
   * - **B6**
     - **42** (re-medido; la partición decía 32)
     - CDN, Plausible, URL canónica, snippets, acciones de cliente, cachés
       y campos HTML — el bloque de cierre: por AST, la fuente declara 111
       métodos y este árbol declaraba 75 al abrirlo. De los 42: **19
       portados aquí**, **7 bloqueados** (banner del bloque B6; eran 11 —
       #545 cerró después los 4 de enumeración sobre la URLconf), **3
       cubiertos con nombre divergente** desde B1 (``create``/``write`` →
       ``save``, ``unlink`` → ``delete``) y **9 del configurador que siguen
       bloqueados en el banner de B4** (sin cambio)
     - **#539** ← este archivo

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

Los seis bloques están abiertos y cerrados con su cobertura declarada: lo que
queda vivo son los **bloqueados** — 9 del configurador (banner de B4) y 4 de
B6 (banner de B6), cada uno con su sucesor; #545 cerró los 4 de enumeración
de páginas que aquí se contaban como heredados de B2, y **#104** cerró
``new_page`` (el heredado de B2), ``get_website_page_ids`` y
``_get_website_pages`` al portar ``website.page``/``website.rewrite``.
Los 33 de B1
están todos declarados; **tres tienen el cuerpo recortado**, y cada uno dice por
qué en su propio docstring en vez de callarlo:

- ``_remove_attachments_on_website_unlink`` — ``ir.attachment`` no declara
  ``website_id`` en este árbol, así que el filtro no tiene sobre qué operar.
  #104 no lo cubrió (su alcance fueron los modelos del addon, no la extensión
  de attachments); sucesor: tarea **#563**.
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

Cobertura de B2 — el bloqueo medido, método a método
======================================================

(B6 desbloqueó ``search_url_dependencies`` al portar ``_get_html_fields``;
la fila correspondiente lo registra.)

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
     - portado
     - desbloqueado por **#543**, que añadió ``website_id`` a
       ``website.menu``; la clave única ``key`` (campo propio, la fuente no
       lo tiene) se deriva por sitio al clonar
   * - ``viewref`` · ``is_view_active``
     - portado
     - sobre ``_get_template_view`` / ``_get_cached_template_info`` que
       **#544** portó a ``IrUiView``
   * - ``new_page``
     - portado (#104)
     - ``website.page`` existe; el template se resuelve por la ``key`` de
       la vista (≙ xml_id) en vez de external ID — ver su docstring. Con
       esta fila el bloque queda sin filas abiertas
   * - ``check_existing_page``
     - portado (#545 + #104)
     - la mitad de routing corre sobre la URLconf de Django
       (``get_resolver().resolve``); la mitad de ``website.rewrite`` la
       cerró #104 (escalón 2 del docstring)
   * - ``rule_is_enumerable`` · ``_enumerate_pages`` · ``search_pages``
     - portado (#545)
     - los tres leen la URLconf de Django (``get_resolver()``) en vez del
       ``routing_map()`` werkzeug; las divergencias de mecanismo —el
       protocolo ``generate`` de los converters, el ``sitemap`` callable—
       van declaradas método a método en sus docstrings
   * - ``search_url_dependencies``
     - portado (B6)
     - lo desbloqueó ``_get_html_fields`` de #539. La mención a
       ``website.rewrite`` de esta fila era imprecisa: el método de la
       fuente (``:1297-1358``) no lo toca — medido al abrir B6

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
import fnmatch
import hashlib
import inspect
import logging
import re
import uuid
from collections import defaultdict
from urllib.parse import urlparse, urlsplit

import fields
import models
import requests
from django.apps import apps
from django.urls import Resolver404, URLPattern, URLResolver, get_resolver
# ``RoutePattern`` distingue una ruta literal de ``path()`` de un regex de
# ``re_path()`` — interno de Django leído en el paquete instalado
# (``django/urls/resolvers.py:314``), no de memoria.
from django.urls.resolvers import RoutePattern
from django.utils import timezone
from django.utils.safestring import mark_safe
from lxml import etree, html

from addons.base.models import TimeStampedModel
from addons.base.models.ir_asset import IrAsset
from addons.base.models.ir_http import get_current_request
from addons.base.models.ir_ui_view import IrUiView
from addons.base.models.res_company import ResCompany
from addons.base.models.res_lang import ResLang
from addons.portal.controllers.portal import pager
from addons.website.models.ir_http import IrHttp
from addons.website.models.mixins import WebsiteSearchableMixin
from addons.website.models.static_page import StaticPage
from addons.website.models.website_menu import WebsiteMenu
from addons.website.tools import (
    get_base_domain, similarity_score, text_from_html,
)
import release
from addons.base.models.ir_config_parameter import SystemParameter
from exceptions import AccessError, UserError, ValidationError
from modules.db import has_trigram
from orm.domains import Domain, to_q
from orm.models_transient import TransientModel
from orm.registry import model_by_name, name_of
from tools.sql import escape_psql
from tools.urls import urljoin
# ``connection`` sale del espejo del entorno, no de Django crudo: es el
# ``env.cr`` de la referencia, y ``orm.environments`` lo re-exporta a
# propósito (su tabla de mapeo lo declara).
from orm.environments import (
    connection, context_scope, get_context, get_current_company,
    get_current_uid, is_su, sudo,
)
from tools.translate import _

#: ≙ ``logger = logging.getLogger(__name__)`` de la fuente (``odoo19c: :36``);
#: lo consume la advertencia de ``_enumerate_pages`` sobre rutas sin
#: declaración de sitemap.
logger = logging.getLogger(__name__)

# ≙ ``DEFAULT_WEBSITE_ENDPOINT`` / ``DEFAULT_OLG_ENDPOINT``
# (``odoo19c: :49-50``). La fuente apunta a ``https://website.api.odoo.com``
# y ``https://olg.api.odoo.com`` — los servicios SaaS de Odoo. Esta
# plataforma L0 no los llama (#416): el default es vacío y el operador
# declara el suyo en ``ir.config_parameter`` (``website.website_api_endpoint``
# / ``website.olg_api_endpoint``). Sin endpoint, el RPC corta con
# ``AccessError`` y los llamadores degradan como en la fuente.
DEFAULT_WEBSITE_ENDPOINT = ''
DEFAULT_OLG_ENDPOINT = ''

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
        return (models.Q(website__isnull=True)
                | models.Q(website__in=[self.pk] if self.pk else []))

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
        este árbol, así que el filtro no tiene sobre qué operar. #104 alineó
        los modelos propios del addon pero no la extensión de attachments;
        sucesor: tarea **#563**.
        """
        return None

    # ── B2 · resolución de sitio actual y páginas (#535) ──────────────────────
    #
    # Los 15 métodos del bloque están declarados con cuerpo — la última fila
    # abierta (``new_page``) la cerró **#104** al portar ``website.page``.
    # Historia del desbloqueo: 7 se portaron al abrir el bloque, #543/#544
    # abrieron 3, B6 uno (``search_url_dependencies``, al portar
    # ``_get_html_fields``), #545 los 4 de enumeración sobre la URLconf y
    # #104 el último (su método vive en la sección de este bloque, abajo).

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

        **Divergencia declarada (2) — ``is_frontend`` ya tiene mecanismo,
        pero ninguna vista lo declara todavía.** #546 (H-API-695) lo cableó:
        ``CompanyContextMiddleware`` estampa el default ``False`` y su
        ``process_view`` copia a la petición la declaración
        ``is_frontend = True`` de la vista despachada — el análogo del
        ``routing.get('website', False)`` de la fuente. Medido tras el porte:
        **0** vistas del árbol declaran el atributo, así que el escalón 3
        sigue sin alcanzarse con ``fallback=False`` hasta que el barrido
        **#550** marque las vistas públicas. La consecuencia mientras tanto
        es conservadora: ``None`` en vez de adivinar un sitio.
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
            models.Q(domain__icontains=remove_port(domain_name))
            | models.Q(domain__icontains=remove_port(domain_name_idna))))

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

    # ── B2 — la enumeración de páginas que #545 desbloqueó ───────────────────
    #
    # El eje entero: el ``routing_map()`` de la fuente es un mapa werkzeug
    # cuyas reglas se introspectan (``rule.endpoint.routing``, converters con
    # ``generate``). Aquí el mapa de rutas es la **URLconf de Django**
    # (``django.urls.get_resolver()``) y «regla» se lee sobre
    # ``URLPattern``/``URLResolver`` — la recorre ``_iter_url_patterns``
    # (función de módulo, abajo). El análogo de ``routing.get('website')``
    # es el atributo ``is_frontend = True`` de la vista, el mecanismo que
    # #546 cableó en ``CompanyContextMiddleware``. Cada divergencia de
    # mecanismo se declara en el docstring del método que la sufre.

    def rule_is_enumerable(self, rule):
        """≙ ``rule_is_enumerable`` (``odoo19c: :1519-1544``).

        ¿Se pueden generar consultas GET sensatas para esta regla? Aquí
        ``rule`` es un ``django.urls.URLPattern``. Las condiciones de la
        fuente, una a una:

        - ``'GET' in methods`` → si la vista declara ``http_method_names``
          (CBV/DRF), debe incluir ``get``; una FBV sin declaración admite
          GET — mismo default que el ``or ['GET']`` de la fuente.
        - ``routing['auth'] in ('none', 'public')`` y
          ``routing.get('website', False)`` → el atributo
          ``is_frontend = True`` de la vista (#546): es la única declaración
          por-vista de «cara pública» que la URLconf conoce, y subsume los
          dos ejes — una vista de backend o de API no lo declara.
        - ``routing['type'] == 'http'`` → **divergencia declarada**: el eje
          http/json-rpc no existe en Django; toda vista es HTTP.
        - ``hasattr(converter, 'generate')`` → **divergencia declarada**:
          ningún converter de ``path()`` sabe enumerar registros (convierten
          un valor, no generan la población), así que una ruta con
          converters no es enumerable hasta que exista ese protocolo.
        - la firma sin argumentos requeridos sin converter → portado con
          ``inspect.signature`` sobre el callback, saltando ``request`` como
          la fuente salta ``self``; ``default_args`` del patrón cuenta como
          valor provisto.

        Una regla de ``re_path()`` tampoco es enumerable: su patrón no es
        una URL literal que ``_enumerate_pages`` pueda construir (el
        ``rule.build`` de werkzeug no tiene análogo sobre un regex).
        """
        if not isinstance(rule, URLPattern):
            return False
        if not isinstance(rule.pattern, RoutePattern):
            return False
        owner = _view_owner(rule.callback)
        methods = [method.upper()
                   for method in (getattr(owner, 'http_method_names', None)
                                  or ['GET'])]
        if 'GET' not in methods:
            return False
        if not getattr(owner, 'is_frontend', False):
            return False
        if rule.pattern.converters:
            return False

        # No listar rutas con argumentos sin default ni converter (fuente).
        sign = inspect.signature(rule.callback)
        params = list(sign.parameters.values())[1:]  # saltar request
        supported_kinds = (inspect.Parameter.POSITIONAL_ONLY,
                           inspect.Parameter.POSITIONAL_OR_KEYWORD)
        provided = set(rule.pattern.converters) | set(rule.default_args or {})
        return all(p.name in provided for p in params
                   if p.kind in supported_kinds
                   and p.default is inspect.Parameter.empty)

    def _enumerate_pages(self, query_string=None, force=False):
        """≙ ``_enumerate_pages`` (``odoo19c: :1546-1668``).

        Las páginas disponibles del sitio: primero los registros de página,
        después los controladores enumerables de la URLconf. Generador,
        como la fuente.

        **Mitad de páginas — ``website.page`` desde #104, más el interinato
        ``StaticPage``.** La enumeración primaria es la de la fuente:
        ``website.page`` filtrado por ``website_indexed``, publicación y
        ``date_publish``, con la ``priority`` de la vista (vía la delegación)
        y el ``lastmod`` como el mayor de ``updated_at``/``view_write_date``
        (≙ ``write_date``/``view_write_date``). El filtro
        ``('visibility', '=', False)`` es del mixin ausente — BLOQUEADO por
        ``website.page_options.mixin`` — y no tiene sobre qué operar.
        Después se enumera ``StaticPage`` — el interinato que #104 conserva
        (decisión en ``website_page.py``); sin ``force`` sólo cuentan las
        que tienen versión publicada.

        **Mitad de controladores — la URLconf.** Divergencias declaradas:

        - el ``sitemap`` de la fuente es una clave de routing; aquí es un
          atributo de la vista (mismo canal que ``is_frontend``).
          ``sitemap = False`` excluye la ruta, igual que allá. Un ``sitemap``
          **callable** se salta: su protocolo (``func(env, rule, qs)``
          generando locs con converters werkzeug) no está portado — la ruta
          dinámica que lo necesite lo declara cuando exista el protocolo de
          generación (misma pieza que los converters de
          ``rule_is_enumerable``).
        - la generación por converters (``convitems``, ``converter.generate``,
          ``sitemap_qs2dom``) no se porta — sin protocolo ``generate`` no hay
          población que producir, así que una ruta parametrizada no emite
          URLs.
        - el ``with_context(lang=self.default_lang_id.code)`` vive dentro de
          las dos ramas no portadas (sitemap callable y generación); no hay
          dónde aplicarlo todavía.

        La advertencia de la fuente ante un controlador enumerable sin
        declaración de sitemap se conserva (``logger.warning``), y también
        ``_norm`` (normaliza la barra final preservando ``/``) y la
        deduplicación por ``url_set``.
        """
        # ==== páginas (website.page; StaticPage como interinato) ====
        # '/' ya está en la URLconf, así que tendrá su entrada por la mitad
        # de controladores (comentario de la fuente, mismo motivo). El
        # ``('view_id', '!=', False)`` del dominio de la fuente es invariante
        # aquí: la FK es NOT NULL.
        page_model = model_by_name('website.page')
        pages_queryset = page_model.objects.exclude(url='/')
        if not force:
            pages_queryset = pages_queryset.filter(
                website_indexed=True, is_published=True)
            pages_queryset = pages_queryset.filter(
                models.Q(date_publish__isnull=True)
                | models.Q(date_publish__lte=timezone.now()))
        if query_string:
            pages_queryset = pages_queryset.filter(
                url__contains=query_string)
        current_website = self.get_current_website()
        if current_website is not None:
            pages_queryset = pages_queryset.filter(
                current_website.website_domain())
        for page in page_model._get_most_specific_pages(
                list(pages_queryset), website=current_website):
            record = {'loc': page.url, 'id': page.pk, 'name': page.name}
            if page.priority != 16:
                record['priority'] = min(round(page.priority / 32.0, 1), 1)
            last_dates = [d for d in (page.updated_at, page.view_write_date)
                          if d]
            if last_dates:
                record['lastmod'] = max(last_dates).date()
            yield record

        for page in StaticPage.objects.all():
            url = page.url
            if url == '/':
                continue
            if not force and page.current_version is None:
                continue
            if query_string and query_string not in url:
                continue
            record = {'loc': url, 'id': page.pk, 'name': page.title}
            if page.updated_at:
                record['lastmod'] = page.updated_at.date()
            yield record

        # ==== controladores ====
        url_set = set()

        def _norm(url):
            # Normaliza la barra final preservando '/' (ayudante de la
            # fuente, verbatim).
            return '/' if url == '/' else url.rstrip('/')

        for route, rule, literal in _iter_url_patterns():
            owner = _view_owner(rule.callback)
            sitemap_value = getattr(owner, 'sitemap', None)
            if sitemap_value is False:
                continue
            if callable(sitemap_value):
                # Protocolo de generación no portado — ver el docstring.
                continue

            if not literal or not self.rule_is_enumerable(rule):
                continue

            # Avisar sólo si la declaración de sitemap está ausente
            # (conducta legacy de la fuente).
            if not hasattr(owner, 'sitemap'):
                logger.warning(
                    'No Sitemap value provided for controller %s (%s)',
                    rule.callback, route)

            url = _norm('/' + route)
            if query_string and query_string not in url:
                continue

            pattern = (query_string
                       and '*%s*' % '*'.join(query_string.split('/')))
            if not query_string or fnmatch.fnmatch(url.lower(), pattern):
                if url in url_set:
                    continue
                url_set.add(url)
                yield {'loc': url}

    def search_pages(self, needle=None, limit=None):
        """≙ ``search_pages`` (``odoo19c: :1714-1721``).

        Las páginas cuya URL matchea el ``needle`` slugificado, hasta
        ``limit``.

        Divergencia declarada: la fuente llama
        ``self.env['ir.http']._slugify``; aquí el porte de ``base`` lo
        declara como ``slugify`` (despromoción preexistente de
        ``src/addons/base/models/ir_http.py:211``, anterior a este pase —
        familia de :ref:`h-api-581`, barrido #337). Se consume el nombre que
        existe; el renombre pertenece a ese archivo, no a éste.
        """
        name = IrHttp.slugify(needle, max_length=50, path=True)
        res = []
        for page in self._enumerate_pages(query_string=name, force=True):
            res.append(page)
            if len(res) == limit:
                break
        return res

    def check_existing_page(self, page):
        """≙ ``check_existing_page`` (``odoo19c: :1723-1768``).

        ¿La página existe para el sitio actual? Heurística, no perfectamente
        confiable — el mismo aviso de la fuente. Los tres escalones de la
        fuente, ya portados (#545 trajo el tercero; **#104** cerró los dos
        primeros al portar ``website.page`` y ``website.rewrite``):

        1. **Registro de página** — ``website.page`` con esa ``url`` vía
           ``_get_website_pages``. El ``('view_id', '!=', False)`` de la
           fuente es invariante aquí: la FK ``view`` es NOT NULL. El
           interinato ``StaticPage`` cuenta como segundo paso mientras sus
           consumidores REST vivan (decisión de #104 — ver el docstring de
           ``website_page.py``).
        2. **Redirecciones** — un ``website.rewrite`` 301/302 con ese
           ``url_from`` cuenta como existente; por simplicidad no se sigue
           el destino (comentario de la fuente). La 308 entra por este mismo
           filtro — en la fuente aparece después, como el
           ``RequestRedirect`` que lanza su router; el resolver de Django no
           redirige, así que su mitad de datos se consulta aquí.
        3. **El mapa de rutas** — el ``router.test``/``router.match`` de la
           fuente es aquí ``get_resolver().resolve(page)``: sin match
           (``Resolver404``) la página no existe; con match, existe.

        Divergencias declaradas del escalón 3: (a) el resolver de Django no
        redirige — el análogo del ``RequestRedirect`` werkzeug
        (``APPEND_SLASH``) vive en ``CommonMiddleware``, no en la
        resolución; la 308 de datos ya se cubrió en el escalón 2; (b) la
        validación por registro de los args del match (``rule.build`` +
        ``MissingError`` + el descarte por ``website_id`` ajeno) depende de
        los model converters, que la URLconf no tiene — un match resuelto se
        acepta sin materializar registros.
        """
        # 1) Registro de página (website.page; StaticPage como interinato).
        if self._get_website_pages(domain=Domain('url', '=', page), limit=1):
            return True
        if any(existing.url == page for existing in StaticPage.objects.all()):
            return True

        # 2) website.rewrite 301/302 (más la 308 — ver el docstring).
        rewrite_model = model_by_name('website.rewrite')
        current_website = self.get_current_website()
        redirects = rewrite_model.objects.filter(
            url_from=page, redirect_type__in=('301', '302', '308'))
        if current_website is not None:
            redirects = redirects.filter(current_website.website_domain())
        if redirects.exists():
            return True

        # 3) Si ninguna regla matchea la página, no existe.
        try:
            get_resolver().resolve(page)
        except Resolver404:
            return False
        return True

    def get_website_page_ids(self):
        """≙ ``get_website_page_ids`` (``odoo19c: :1670-1705``).

        IDs de ``website.page`` agrupados por sitio, reducidos a las páginas
        más específicas. Portado por **#104**.

        Divergencias declaradas:

        - El gate ``has_group('website.group_website_restricted_editor')``
          con su ``AccessError`` — BLOQUEADO por
          ``website.group_website_restricted_editor`` — resolver el grupo
          exige el registro de datos por external ID (#467; mismo criterio
          que ``_should_remove_third_party_trackers``). La autorización de
          este árbol corre en la capa DRF (``HasCapability``, fail-closed),
          que es quien expone el método.
        - El recordset vacío/inexistente de la fuente es aquí la instancia
          sin ``pk``: devuelve todas las páginas bajo la clave ``None``. Una
          instancia guardada devuelve su propio mapa de un sitio.
        - ``Domain('url', '!=', False)`` es invariante aquí: ``url`` es NOT
          NULL, así que no se re-declara.
        - El ``sudo()`` de la fuente es el estado por defecto de este ORM
          (el manager no aplica ACL de lectura).
        """
        page_model = model_by_name('website.page')
        if not self.pk:
            return {None: list(
                page_model.objects.values_list('id', flat=True))}
        pages = list(page_model.objects.filter(self.website_domain()))
        most_specific = page_model._get_most_specific_pages(
            pages, website=self)
        return {self.pk: [page.pk for page in most_specific]}

    @classmethod
    def _get_website_pages(cls, domain=None, order='name', limit=None):
        """≙ ``_get_website_pages`` (``odoo19c: :1707-1712``).

        Las páginas del sitio actual que cumplen el dominio, reducidas a las
        más específicas. Portado por **#104**.

        Divergencias declaradas: (1) recordset → lista de instancias;
        (2) el ``order='name'`` por defecto ordena una columna del delegado
        — la traduce ``_translate_order`` de ``website.page`` al JOIN de la
        delegación (``view__name``); (3) el ``sudo()`` de la fuente es el
        estado por defecto de este ORM.
        """
        page_model = model_by_name('website.page')
        website = cls.get_current_website()
        queryset = page_model.objects.all()
        if domain is not None:
            queryset = queryset.filter(to_q(domain, page_model))
        if website is not None:
            queryset = queryset.filter(website.website_domain())
        order_by = page_model._translate_order(order)
        if order_by:
            queryset = queryset.order_by(*order_by)
        if limit:
            queryset = queryset[:limit]
        return page_model._get_most_specific_pages(
            list(queryset), website=website)

    def new_page(self, name=False, add_menu=False,
                 template='website.default_page', ispage=True, namespace=None,
                 page_values=None, menu_values=None, sections_arch=None,
                 page_title=None):
        """≙ ``new_page`` (``odoo19c: :1164-1238``).

        Crea una página nueva del sitio: clona la vista plantilla, deriva la
        URL y la clave únicas, crea el ``website.page`` y, si se pide, su
        menú. Desbloqueado por **#104** (``website.page`` existe); el
        escalón del template quedó resuelto sin external ID (abajo).

        Divergencias declaradas:

        - ``self.env.ref(template)`` (external ID, #467) se resuelve por la
          ``key`` de la vista: en la referencia las vistas QWeb del sitio
          llevan ``key = xml_id``, así que la misma cadena localiza la misma
          vista sin registro de datos (es el criterio con que ``key`` se
          portó a ``ir.ui.view``). Sin plantilla con esa clave corta con
          ``UserError`` — la fuente revienta en el ``ref``.
        - ``template_record.copy({...})`` es un clon campo a campo (el ORM
          no trae ``copy()``; mismo criterio que ``copy_menu_hierarchy``).
          El ``website_id`` del contexto que la fuente pasa al clon es de la
          COW de ``ir.ui.view`` no portada (divergencia 2 de
          ``website_page.py``); el eje por sitio queda en la página.
        - ``'track': True`` del ``default_page_values`` — BLOQUEADO por
          ``website.page_options.mixin`` — el campo es de ese mixin.
        - El menú se busca/crea por ``route`` (≙ su ``url``) y lleva la
          ``key`` derivada — campo propio único de ``website.menu``.
        """
        template_module = namespace if namespace else template.split('.')[0]
        page_url = '/' + IrHttp.slugify(name or '', max_length=1024, path=True)
        page_url = self.get_unique_path(page_url)
        page_key = IrHttp.slugify(name or '')
        result = {'url': page_url}

        if not name:
            name = 'Home'
            page_key = 'home'

        page_model = model_by_name('website.page')
        template_record = IrUiView.objects.filter(key=template).first()
        if template_record is None:
            raise UserError(
                _('No hay vista plantilla con la clave %s') % template)
        arch = template_record.arch_db
        if sections_arch:
            tree = html.fromstring(arch)
            wrap = tree.xpath('//div[@id="wrap"]')[0]
            for section in html.fromstring(f'<wrap>{sections_arch}</wrap>'):
                wrap.append(section)
            arch = etree.tostring(tree, encoding="unicode")
        key = self.get_unique_key(page_key, template_module)
        view = IrUiView.objects.create(
            name=page_title or name,
            model=template_record.model,
            type=template_record.type,
            priority=template_record.priority,
            mode=template_record.mode,
            inherit_id=template_record.inherit_id,
            key=key,
            arch_db=arch.replace(template, key),
            # ≙ ``view.arch_fs = False``: el clon no procede de un archivo.
            arch_fs='',
        )
        result['view_id'] = view.pk

        current_website = self.get_current_website()
        page = None
        if ispage:
            default_page_values = {
                'url': page_url,
                # «quitar si hay un solo sitio, ¿o no?» — comentario de la
                # fuente, conservado.
                'website': current_website,
                'view': view,
            }
            if page_values:
                default_page_values.update(page_values)
            page = page_model.objects.create(**default_page_values)
            result['page_id'] = page.pk
        if add_menu:
            menu = WebsiteMenu.objects.filter(
                route=page_url, website=current_website).first()
            if not menu:
                default_menu_values = {
                    'name': name,
                    'route': page_url,
                    'parent': current_website.menu if current_website else None,
                    'page': page,
                    'website': current_website,
                    'key': '%s-w%s' % (
                        page_key or 'home',
                        current_website.pk if current_website else 0),
                }
                if menu_values:
                    default_menu_values.update(menu_values)
                menu = WebsiteMenu.objects.create(**default_menu_values)
            result['menu_id'] = menu.pk
        return result

    # ── B2 — los tres que la tanda #543/#544 desbloqueó ──────────────────────

    def copy_menu_hierarchy(self, top_menu):
        """≙ ``copy_menu_hierarchy`` (``odoo19c: :1147-1161``).

        Clona el árbol de menús plantilla (los de ``website=None``) para este
        sitio. La fuente lo hace con ``menu.copy({...})``; aquí se clona campo
        a campo porque el ORM no trae ``copy()``.

        **Divergencia declarada:** ``key`` es campo propio (la fuente no lo
        tiene) y es único, así que el clon deriva la suya por sitio
        (``<key>-w<id>``). El nombre del menú raíz usa la misma plantilla
        traducible que la fuente.
        """
        def copy_menu(menu, parent_menu):
            new_menu = WebsiteMenu.objects.create(
                name=menu.name,
                route=menu.route,
                sequence=menu.sequence,
                new_window=menu.new_window,
                web_icon=menu.web_icon,
                key=f'{menu.key}-w{self.pk}',
                parent=parent_menu,
                website=self,
            )
            for submenu in menu.child.all():
                copy_menu(submenu, new_menu)

        new_top_menu = WebsiteMenu.objects.create(
            name=_('Top Menu for Website %s') % self.pk,
            route=top_menu.route,
            sequence=top_menu.sequence,
            new_window=top_menu.new_window,
            web_icon=top_menu.web_icon,
            key=f'{top_menu.key}-w{self.pk}',
            website=self,
        )
        for submenu in top_menu.child.all():
            copy_menu(submenu, new_top_menu)
        return new_top_menu

    @classmethod
    def viewref(cls, view_id, raise_if_not_found=True):
        """≙ ``viewref`` (``odoo19c: :1487-1501``).

        Dado un xml_id o un id de vista, la vista correspondiente — mirando
        también las archivadas, igual que la fuente
        (``sudo().with_context(active_test=False)``).
        """
        if not isinstance(view_id, (int, str)):
            raise ValueError(
                'Expecting a string or an integer, not a %s.' % type(view_id))
        with sudo(), context_scope(active_test=False):
            return IrUiView._get_template_view(
                view_id, raise_if_not_found=raise_if_not_found)

    @classmethod
    def is_view_active(cls, key):
        """≙ ``is_view_active`` (``odoo19c: :1503-1507``).

        ``True`` si está activa, ``False`` si no, ``None`` si no existe.
        """
        with context_scope(active_test=False):
            return IrUiView._get_cached_template_info(key).get('active')

    # ── B3 (#536) — búsqueda del sitio ───────────────────────────────────────
    #
    # Los 10 métodos de ``odoo19c: :1987-2355``, sobre tres piezas de soporte
    # portadas en este mismo pase: ``website.searchable.mixin`` (mixins.py),
    # ``escape_psql`` (``tools/sql.py``) y ``has_trigram``
    # (``modules/db.py``). Divergencias transversales del bloque, declaradas
    # una vez aquí:
    #
    # 1. ``search_details['model']`` lleva la CLASE del modelo, no su nombre
    #    (ver el docstring de ``_search_get_detail`` del mixin; vuelve al
    #    nombre con #104).
    # 2. El SQL del enumerador por trigramas se construye con el cursor del
    #    entorno + ``quote_name`` — la clase ``SQL`` componible ya está
    #    portada (#549 resuelto, :ref:`h-api-698`; migrar este rodeo es
    #    opcional) y ``unaccent`` sigue sin cablear (#98), así que las
    #    comparaciones no normalizan acentos.
    # 3. La rama ``field.translate`` del enumerador NO se porta: ningún campo
    #    declara ``translate=True`` porque el almacenamiento jsonb de
    #    traducciones es la tarea **#333**; la rama llega con él.

    @classmethod
    def _search_build_domain(cls, domain_list, search, fields_list, extra=None):
        """≙ ``_search_build_domain`` (``odoo19c: :1987-2007``).

        La fuente duplica el cuerpo con el comentario *"just like
        website.searchable.mixin"*; aquí se delega en el mixin en vez de
        copiarlo — misma semántica, una sola implementación.
        """
        return WebsiteSearchableMixin._search_build_domain(
            domain_list, search, fields_list, extra)

    @staticmethod
    def _search_text_from_html(html_fragment):
        """≙ ``_search_text_from_html`` (``odoo19c: :2009-2019``).

        El texto plano de un fragmento HTML. NO poda nodos técnicos — ese es
        el contrato de ``tools.text_from_html``, su casi-homónimo; la fuente
        mantiene los dos separados y aquí también.
        """
        # lxml exige un único elemento raíz.
        tree = etree.fromstring(
            '<p>%s</p>' % html_fragment, etree.XMLParser(recover=True))
        return ' '.join(tree.itertext())

    def _search_get_details(self, search_type, order, options):
        """≙ ``_search_get_details`` (``odoo19c: :2021-2033``).

        La fuente consulta ``website.page``. Aquí sigue sirviendo
        ``StaticPage`` — el interinato que #104 conserva (decisión en
        ``website_page.py``): sus consumidores REST y sus tests viven sobre
        él. La receta de ``website.page`` ya existe
        (``WebsitePage._search_get_detail``), pero su cableado a este flujo
        está BLOQUEADO por ``_trigram_enumerate_words`` — los enumeradores
        de palabras construyen su SQL sobre columnas de la tabla del modelo,
        y los campos de búsqueda de la página cruzan el JOIN de la
        delegación (``view.name``). Sucesor: tarea **#564**.
        """
        result = []
        if search_type in ('pages', 'all'):
            result.append(StaticPage._search_get_detail(self, order, options))
        return result

    def _search_with_fuzzy(self, search_type, search, limit, order, options):
        """≙ ``_search_with_fuzzy`` (``odoo19c: :2035-2064``)."""
        fuzzy_term = False
        search_details = self._search_get_details(search_type, order, options)
        if search and options.get('allowFuzzy', True):
            fuzzy_term = self._search_find_fuzzy_term(search_details, search)
            if fuzzy_term:
                count, results = self._search_exact(
                    search_details, fuzzy_term, limit, order)
                if fuzzy_term.lower() == search.lower():
                    fuzzy_term = False
            else:
                count, results = self._search_exact(
                    search_details, search, limit, order)
        else:
            count, results = self._search_exact(
                search_details, search, limit, order)
        return count, results, fuzzy_term

    def _search_exact(self, search_details, search, limit, order):
        """≙ ``_search_exact`` (``odoo19c: :2066-2089``)."""
        all_results = []
        total_count = 0
        for search_detail in search_details:
            model = search_detail['model']
            results, count = model._search_fetch(
                search_detail, search, limit, order)
            search_detail['results'] = results
            total_count += count
            search_detail['count'] = count
            all_results.append(search_detail)
        return total_count, all_results

    def _search_render_results(self, search_details, limit):
        """≙ ``_search_render_results`` (``odoo19c: :2091-2112``).

        La fuente llama al método SOBRE el recordset de resultados; aquí los
        resultados son una lista, así que viajan como primer argumento al
        classmethod del mixin (divergencia 1 del mixin).
        """
        for search_detail in search_details:
            model = search_detail['model']
            search_detail['results_data'] = model._search_render_results(
                search_detail['results'],
                search_detail['fetch_fields'],
                search_detail['mapping'],
                search_detail['icon'],
                limit,
            )
        return search_details

    def _search_find_fuzzy_term(self, search_details, search,
                                limit=1000, word_list=None):
        """≙ ``_search_find_fuzzy_term`` (``odoo19c: :2114-2143``).

        La palabra disponible más parecida al término buscado. Los tres
        atajos de la fuente se conservan verbatim: sin fuzzy para menos de 4
        caracteres, para frases, ni para términos con 80 %+ de dígitos.

        El despacho por capacidad replica el ``registry.has_trigram`` de la
        fuente: se sondea ``pg_proc`` en cada llamada (``modules/db.py``) —
        sin registry persistente no hay dónde memorizarlo, y la sonda es una
        consulta al catálogo.
        """
        if (len(search) < 4 or ' ' in search
                or len(re.findall(r'\d', search)) / len(search) >= 0.8):
            return search
        search = search.lower()
        words = set()
        best_score = 0
        best_word = None
        with connection.cursor() as cr:
            trigram_ready = has_trigram(cr)
        enumerate_words = (self._trigram_enumerate_words if trigram_ready
                           else self._basic_enumerate_words)
        for word in word_list or enumerate_words(search_details, search, limit):
            if search in word:
                return search
            if word[0] == search[0] and word not in words:
                similarity = similarity_score(search, word)
                if similarity > best_score:
                    best_score = similarity
                    best_word = word
                words.add(word)
        return best_word

    def _search_get_indirect_fields(self, fields_list, model):
        """≙ ``_search_get_indirect_fields`` (``odoo19c: :2145-2180``).

        Los campos punteados (``relacion.campo``) entre los pedidos, con su
        detalle: campo directo, indirecto, comodel y —para las inversas— la
        FK del comodel que apunta de vuelta (el
        ``_description_relation_field`` de la fuente, que aquí es
        ``rel.field.name`` de Django).
        """
        indirect_fields = {}
        meta_fields = {f.name: f for f in model._meta.get_fields()}
        for field_path in fields_list:
            field_parts = field_path.split('.')
            if len(field_parts) != 2:
                continue
            direct, indirect = field_parts
            direct_field = meta_fields.get(direct)
            if direct_field is None or not getattr(
                    direct_field, 'is_relation', False):
                continue
            comodel = direct_field.related_model
            if comodel is None:
                continue
            comodel_fields = {f.name: f for f in comodel._meta.get_fields()}
            cofield = None
            if direct_field.one_to_many:
                # La FK del comodel hacia este modelo — ≙ el
                # ``_description_relation_field`` del One2many.
                cofield = direct_field.field.name
                if cofield not in comodel_fields:
                    continue
            if indirect in comodel_fields:
                indirect_fields[field_path] = {
                    'direct': direct,
                    'indirect': indirect,
                    'comodel': comodel,
                    'cofield': cofield,
                }
        return indirect_fields

    @staticmethod
    def _mapped_indirect_values(records, indirect_field):
        """Los valores de un campo punteado sobre una lista de instancias.

        Es el ``records.mapped(indirect_field)`` de la fuente, escrito sobre
        ``getattr``: el tramo directo puede ser un registro (FK) o un manager
        (inversa/M2M), y el indirecto se lee sobre lo que salga.
        """
        for record in records:
            related = getattr(record, indirect_field['direct'], None)
            if related is None:
                continue
            if hasattr(related, 'all'):
                for co_record in related.all():
                    yield getattr(co_record, indirect_field['indirect'], None)
            else:
                yield getattr(related, indirect_field['indirect'], None)

    def _trigram_enumerate_words(self, search_details, search, limit):
        """≙ ``_trigram_enumerate_words`` (``odoo19c: :2182-2295``).

        Enumera las palabras candidatas restringiendo a los registros con
        ``word_similarity()`` distinta de cero — que es lo que hace barato el
        fuzzy: la base preselecciona por trigrama y Python sólo puntúa lo que
        sobrevive. Requiere la extensión ``pg_trgm``
        (``website/migrations/0005``).

        El SQL se arma con ``quote_name`` + parámetros (divergencia 2 del
        bloque); el ``SET LOCAL`` del umbral es transaccional, igual que en
        la fuente.
        """
        def get_similarity_subquery(model, fields_list, id_column,
                                    rel_table='', rel_joinkey=''):
            """El subquery de mayor similitud por registro — ≙ el interno
            homónimo de la fuente, con joins para inversas y M2M."""
            quote = connection.ops.quote_name
            table = quote(model._meta.db_table)
            params = []
            similarity_terms = []
            for field_name in fields_list:
                column = quote(model._meta.get_field(field_name).column)
                similarity_terms.append(
                    f'word_similarity(%s, {table}.{column}::text)')
                params.append(search)
            similarity = ('GREATEST(' + ', '.join(similarity_terms)
                          + ') AS similarity')
            where_clauses = []
            for field_name in fields_list:
                column = quote(model._meta.get_field(field_name).column)
                # ``<%`` es el operador de word_similarity; el ``%`` se
                # duplica porque el cursor interpola parámetros.
                where_clauses.append(f'%s <%% {table}.{column}::text')
                params.append(search)
            table_alias = table
            join_sql = ''
            if rel_table:
                rel = quote(rel_table)
                join_sql = (f' JOIN {rel} ON {rel}.{quote(rel_joinkey)}'
                            f' = {table}.{quote("id")}')
                table_alias = rel
            sql = (f'SELECT {table_alias}.{quote(id_column)} AS id,'
                   f' {similarity} FROM {table}{join_sql} WHERE '
                   + ' OR '.join(where_clauses))
            return sql, params

        match_pattern = r'[\w./-]{%s,}' % min(4, len(search) - 3)
        with connection.cursor() as cr:
            # Bajar el umbral de ``<%`` a 0.3 SOLO en esta transacción (el
            # default del cluster es 0.6) — verbatim de la fuente.
            cr.execute(
                'SET LOCAL pg_trgm.word_similarity_threshold to 0.3;')
            for search_detail in search_details:
                model = search_detail['model']
                fields_list = search_detail['search_fields']
                requires_sudo = bool(search_detail.get('requires_sudo'))
                domain = Domain.AND(search_detail['base_domain'])
                meta_names = {f.name for f in model._meta.get_fields()}
                direct_fields = set(fields_list).intersection(meta_names)
                indirect_fields = self._search_get_indirect_fields(
                    fields_list, model)
                indirect_fields_info = defaultdict(dict)
                for name, info in indirect_fields.items():
                    indirect_fields_info[info['comodel']][name] = info
                subqueries = [get_similarity_subquery(
                    model, sorted(direct_fields), 'id')]
                for comodel, infos in indirect_fields_info.items():
                    comodel_similarity_fields = set()
                    id_column = rel_table = rel_joinkey = ''
                    for info in infos.values():
                        direct_field = model._meta.get_field(info['direct'])
                        if direct_field.one_to_many:
                            comodel_similarity_fields.add(info['indirect'])
                            id_column = comodel._meta.get_field(
                                info['cofield']).column
                        elif direct_field.many_to_many:
                            comodel_similarity_fields.add(info['indirect'])
                            id_column = direct_field.m2m_column_name()
                            rel_table = direct_field.m2m_db_table()
                            rel_joinkey = direct_field.m2m_reverse_name()
                    if not comodel_similarity_fields:
                        # Un Many2one punteado no tiene rama aquí — tampoco
                        # en la fuente, donde dejaría el subquery sin columna
                        # de id; se salta en vez de emitir SQL roto.
                        continue
                    subqueries.append(get_similarity_subquery(
                        comodel, sorted(comodel_similarity_fields),
                        id_column, rel_table, rel_joinkey))
                union_sql = '\nUNION ALL\n'.join(sql for sql, _p in subqueries)
                union_params = [p for _s, ps in subqueries for p in ps]
                # UNION ALL permite que cada subplan use su índice GIST —
                # comentario de la fuente, conservado.
                cr.execute(
                    'SELECT id, MAX(similarity) AS _best_similarity'
                    f' FROM ({union_sql}) sub GROUP BY id'
                    ' ORDER BY _best_similarity DESC LIMIT 1000',
                    union_params)
                ids = [row[0] for row in cr.fetchall()]
                domain &= Domain('id', 'in', ids)
                query = to_q(domain, model)
                with sudo(requires_sudo or is_su()):
                    records = list(model.objects.filter(query)
                                   .values(*sorted(direct_fields))[:limit])
                    objects = (list(model.objects.filter(query)[:limit])
                               if indirect_fields else [])
                for record in records:
                    for value in record.values():
                        if isinstance(value, str):
                            yield from re.findall(
                                match_pattern, value.lower())
                for indirect_field in indirect_fields.values():
                    for value in self._mapped_indirect_values(
                            objects, indirect_field):
                        if isinstance(value, str):
                            yield from re.findall(
                                match_pattern, value.lower())

    def _basic_enumerate_words(self, search_details, search, limit):
        """≙ ``_basic_enumerate_words`` (``odoo19c: :2297-2355``).

        El enumerador de respaldo cuando ``pg_trgm`` no está: preselecciona
        por ``=ilike`` sobre la primera letra (inicio de campo, inicio de
        palabra, o tras ``>`` para HTML) y filtra en Python. Los tres
        patrones y el rescate del match exacto cuando el ``perf_limit`` se
        alcanza son verbatim de la fuente.
        """
        match_pattern = r'[\w./-]{%s,}' % min(4, len(search) - 3)
        first = escape_psql(search[0])
        for search_detail in search_details:
            model = search_detail['model']
            fields_list = search_detail['search_fields']
            requires_sudo = bool(search_detail.get('requires_sudo'))
            domain = Domain.AND(search_detail['base_domain'])
            meta_names = {f.name for f in model._meta.get_fields()}
            direct_fields = set(fields_list).intersection(meta_names)
            indirect_fields = self._search_get_indirect_fields(
                fields_list, model)
            all_fields = direct_fields.union(indirect_fields)
            fields_domain = Domain.OR([
                Domain(field, '=ilike', pattern)
                for field in all_fields
                for pattern in (
                    '%s%%' % first,
                    '%% %s%%' % first,
                    '%%>%s%%' % first,  # HTML
                )
            ])
            domain &= fields_domain
            perf_limit = 1000
            query = to_q(domain, model)
            with sudo(requires_sudo or is_su()):
                records = list(model.objects.filter(query)
                               .values(*sorted(direct_fields))[:perf_limit])
                objects = (list(model.objects.filter(query)[:limit])
                           if indirect_fields else [])
            if len(records) == perf_limit:
                # El match exacto pudo quedar fuera del recorte de
                # rendimiento — verificarlo aparte, como la fuente.
                exact_records, _count = model._search_fetch(
                    search_detail, search, 1, None)
                if exact_records:
                    yield search
            for record in records:
                for field_name, value in record.items():
                    if isinstance(value, str):
                        value = value.lower()
                        if field_name == 'arch_db':
                            value = text_from_html(value)
                        for word in re.findall(match_pattern, value):
                            if word[0] == search[0]:
                                yield word.lower()
            for indirect_field in indirect_fields.values():
                for value in self._mapped_indirect_values(
                        objects, indirect_field):
                    if isinstance(value, str):
                        yield from re.findall(match_pattern, value.lower())

    # ── B4 (#537) · configurador y RPC a servicio externo ────────────────────
    #
    # ≙ ``odoo19c: website.py:460-1145`` (zona del configurador). Medida por
    # AST: 19 métodos en la zona + los 2 ayudantes de indexación que la
    # preceden (la estimación inicial de la partición decía 15). En este pase:
    # **12 portados, 9 bloqueados** — cada bloqueado con su sucesor:
    #
    # - ``create_and_redirect_configurator`` (``:460``) — necesita
    #   ``ir.actions.todo`` resuelto por external ID (#467).
    # - ``_preconfigure_snippet`` (``:513``), ``_set_background_options``
    #   (``:591``), ``get_theme_configurator_snippets`` (``:610``) — operan
    #   sobre el árbol lxml de vistas QWeb de snippets; el marco de cliente
    #   está sin decidir (#488) y no hay vistas de snippet que preconfigurar.
    # - ``configurator_init`` (``:658``) — lee ``website.configurator.feature``,
    #   modelo no portado (#552).
    # - ``configurator_recommended_themes`` (``:685``), ``configurator_apply``
    #   (``:721-1106``), ``configurator_addons_apply`` (``:1108``) — módulos
    #   de tema (``theme_*``) e instalación de addons en caliente; no existen
    #   aquí (#488 + #552).
    # - ``_bootstrap_homepage`` (``:1114``) — necesita ``website.page`` (#104).
    #
    # Divergencia transversal del transporte: la fuente delega en
    # ``iap_tools.iap_jsonrpc`` (addon ``iap``); esa cadena está pendiente de
    # la DECISIÓN #413, así que el transporte vive aquí como función local
    # (``_configurator_rpc_call``) y se muda al addon cuando #413 decida.
    # Los endpoints por defecto son cadena vacía — la fuente apunta a
    # ``*.api.odoo.com`` y esta plataforma L0 NO llama a los servicios de
    # Odoo (#416); el operador configura el suyo por ``ir.config_parameter``.

    def _idna_url(self, url):
        """≙ ``_idna_url`` (``odoo19c: :465-466``)."""
        return get_base_domain(url.lower(), True).encode('idna').decode('ascii')

    def _is_indexable_url(self, url):
        """≙ ``_is_indexable_url`` (``odoo19c: :468-480``).

        True si los buscadores deben indexar la URL: coincide con el dominio
        del sitio ignorando ``www.`` y el esquema (eso hace ``get_base_domain``
        con ``strip_www=True``); el ``.lower()`` de ``_idna_url`` es lo único
        que vuelve insensible la comparación — el codec idna no normaliza
        mayúsculas (medido en B2).
        """
        return self._idna_url(url) == self._idna_url(self.domain)

    # ── los tres RPC ─────────────────────────────────────────────────────────

    def _api_rpc(self, route, params, endpoint_param_name, default_endpoint,
                 **kwargs):
        """≙ ``_api_rpc`` (``odoo19c: :486-490``).

        Anota la versión del producto, resuelve el endpoint declarado en
        ``ir.config_parameter`` (bajo ``sudo``, como la fuente) y despacha el
        JSON-RPC. Sin endpoint configurado levanta ``AccessError`` — el mismo
        tipo con el que la fuente reporta el fallo de red, y el que
        ``configurator_init`` atrapa para degradar con gracia.
        """
        params['version'] = release.version
        with sudo():
            api_endpoint = SystemParameter.get_param(
                endpoint_param_name, default_endpoint)
        if not api_endpoint:
            raise AccessError(
                _('No external service endpoint is configured for %s.')
                % endpoint_param_name)
        return _configurator_rpc_call(api_endpoint + route, params=params,
                                      **kwargs)

    def _website_api_rpc(self, route, params):
        """≙ ``_website_api_rpc`` (``odoo19c: :492-494``) — industrias,
        sugerencias de tema, …"""
        return self._api_rpc(route, params, 'website.website_api_endpoint',
                             DEFAULT_WEBSITE_ENDPOINT)

    def _OLG_api_rpc(self, route, params):
        """≙ ``_OLG_api_rpc`` (``odoo19c: :496-498``) — generación de texto."""
        return self._api_rpc(route, params, 'website.olg_api_endpoint',
                             DEFAULT_OLG_ENDPOINT, timeout=45)

    # ── el configurador (lo portable sin temas/QWeb) ─────────────────────────

    def get_cta_data(self, website_purpose, website_type):
        """≙ ``get_cta_data`` (``odoo19c: :500-501``), verbatim."""
        return {'cta_btn_text': False, 'cta_btn_href': '/contactus'}

    def _get_snippet_defaults(self, snippet):
        """≙ ``_get_snippet_defaults`` (``odoo19c: :503-505``), verbatim:
        el gancho que los verticales sobreescriben."""
        return {}

    def _get_snippet_view_key(self, snippet, page_code):
        """≙ ``_get_snippet_view_key`` (``odoo19c: :507-511``), verbatim."""
        if '.' not in snippet:
            snippet = 'website.' + snippet
        module, snippet = snippet.split('.')
        return f'{module}.configurator_{page_code}_{snippet}'

    def configurator_set_menu_links(self, menu_company, module_data):
        """≙ ``configurator_set_menu_links`` (``odoo19c: :647-650``).

        La fuente empareja por ``url``; aquí el campo del menú SPA se llama
        ``route`` (divergencia declarada en ``website_menu.py``), y el recorte
        por sitio usa la FK ``website`` que #543 cableó.
        """
        menus = WebsiteMenu.objects.filter(
            route__in=list(module_data.keys()), website=self)
        for m in menus:
            m.sequence = module_data[m.route]['sequence']
            m.save(update_fields=['sequence'])

    def configurator_get_footer_links(self):
        """≙ ``configurator_get_footer_links`` (``odoo19c: :652-655``).

        El ``href`` diverge: las páginas estáticas públicas viven bajo
        ``/pages/<slug>`` (``StaticPage.url``), no en la raíz.
        """
        return [
            {'text': _("Privacy Policy"), 'href': '/pages/privacy'},
        ]

    @classmethod
    def configurator_skip(cls):
        """≙ ``configurator_skip`` (``odoo19c: :704-708``; ``@api.model``).

        La fuente además instala ``theme_default`` y devuelve su redirect
        (``button_choose_theme``); los módulos de tema no existen aquí (#488),
        así que se marca el sitio y se devuelve ``None`` — divergencia
        declarada, no un recorte silencioso.
        """
        website = cls.get_current_website()
        website.configurator_done = True
        website.save(update_fields=['configurator_done'])
        return None

    @classmethod
    def configurator_missing_industry(cls, unknown_industry):
        """≙ ``configurator_missing_industry`` (``odoo19c: :711-718``;
        ``@api.model``) — reporta al servicio la industria que su catálogo no
        tiene. Hereda el estado del RPC: sin endpoint, ``AccessError``.
        """
        website = cls.get_current_website()
        website._website_api_rpc(
            '/api/website/unknown_industry',
            {
                'unknown_industry': unknown_industry,
                'lang': get_context().get('lang'),
            }
        )

    # ── B5 (#538) · bloqueo de rastreadores de terceros ──────────────────────
    #
    # ≙ ``odoo19c: website.py:291-301`` (los dos ayudantes de la lista) y
    # ``:2357-2440`` (los seis del control de HTML). Medido: 8 métodos en el
    # bloque; en este pase: **8 portados, 0 bloqueados**.
    #
    # Divergencias declaradas del bloque:
    #
    # - ``Markup`` (markupsafe) → ``django.utils.safestring.mark_safe``:
    #   markupsafe NO está instalado (medido: ``ModuleNotFoundError``) y
    #   ``SafeString`` es el marcador de «HTML ya seguro» nativo del stack.
    # - ``self.env['ir.http']._is_allowed_cookie`` → ``IrHttp._is_allowed_cookie``
    #   de ``addons/website/models/ir_http.py`` (la extensión de sitio, portada
    #   en este mismo pase sobre la base nueva de
    #   ``src/addons/base/models/ir_http.py``). El FORMATO del consentimiento
    #   diverge — cookie ``cookie_consent`` por categoría en vez de
    #   ``website_cookies_bar`` ``{'optional': bool}``; ver su docstring.
    # - ``user.has_group('website.group_website_restricted_editor')`` NO se
    #   porta: resolver un grupo por external ID necesita el registro de datos
    #   por módulo (#467; mismo criterio que ``_compute_display_name`` de
    #   ``website_menu.py``). Consecuencia conservadora: los editores
    #   restringidos también ven los rastreadores bloqueados — default seguro.
    # - ``self.ensure_one()`` de la fuente es innecesario por construcción:
    #   un método de instancia de Django opera sobre exactamente un registro.

    def _get_blocked_third_party_domains_list(self):
        """≙ ``_get_blocked_third_party_domains_list`` (``odoo19c: :291-292``)."""
        return self.blocked_third_party_domains.split('\n')

    def _get_blocked_iframe_containers_classes(self):
        """≙ ``_get_blocked_iframe_containers_classes`` (``odoo19c: :294-301``).

        Clases de contenedores dentro de los cuales el cliente construye
        iframes al vuelo; se marcan para que el iframe nazca ya controlado.
        """
        return {
            's_map',
            's_instagram_page',
            'o_facebook_page',
            'o_background_video',
            'media_iframe_video',
        }

    def _allConsentsGranted(self):
        """≙ ``_allConsentsGranted`` (``odoo19c: :2357-2369``) — el camelCase
        de la fuente se conserva: el nombre es el contrato.

        ¿Se concedieron todos los consentimientos (de cookies)? Si el sitio
        no tiene barra de cookies habilitada, el consentimiento pleno se
        considera concedido de inmediato: en ese caso se supone que el
        operador implementó su propia conducta de consentimiento con código o
        aplicación propios, capaces de sobreescribir esta función.

        :return: True si todos los consentimientos están concedidos.
        """
        return not self.cookies_bar or IrHttp._is_allowed_cookie('optional')

    def _control_third_party_trackers_in_html(self, html_content):
        """≙ ``_control_third_party_trackers_in_html`` (``odoo19c: :2371-2381``).

        Neutraliza los iframes/scripts de dominios vigilados dentro de un
        fragmento HTML. Ante HTML que el parser no acepta, passthrough del
        input: mejor servir el contenido intacto que romperlo.
        """
        if not html_content or not self._should_remove_third_party_trackers():
            return html_content
        try:
            root_node = html.fromstring(str(html_content))
            els = root_node.xpath("//script | //iframe")
        except (etree.ParserError, etree.XMLSyntaxError):
            return html_content
        for el in els:
            self._remove_third_party_trackers(el.tag, el.attrib, ['domains'])
        return mark_safe(html.tostring(root_node, encoding="unicode"))

    def _should_remove_third_party_trackers(self):
        """≙ ``_should_remove_third_party_trackers`` (``odoo19c: :2383-2387``).

        El escalón ``has_group(...group_website_restricted_editor)`` de la
        fuente NO se porta (#467 — ver el banner del bloque): sin registro de
        grupos por external ID, el default seguro es controlar también al
        editor.
        """
        return (self.cookies_bar
            and self.block_third_party_domains
            and not IrHttp._is_allowed_cookie('optional'))

    def _remove_third_party_trackers(self, tag_name, atts, cookies_watchlist):
        """≙ ``_remove_third_party_trackers`` (``odoo19c: :2389-2412``).

        El ``tagName`` de la fuente se recibe como ``tag_name`` — mismo
        símbolo, forma PEP 8; aplica igual en los dos ``_is_tag_*``.
        """
        # Si la barra de cookies está activada, los iframes y scripts de
        # terceros embebidos deben controlarse. Para eso:
        # - 'domains' es una lista de vigilancia sobre el propio src del
        #   iframe/script,
        # - 'classes' es una lista de vigilancia sobre elementos contenedores
        #   dentro de los cuales el cliente construye (o podría construir)
        #   iframes al vuelo por alguna razón.
        watchlist_checker = {
            'domains': self._is_tag_domains_watchlisted,
            'classes': self._is_tag_classes_watchlisted,
        }
        remove_src = False
        for watch in cookies_watchlist:
            if (checker := watchlist_checker.get(watch)) and checker(tag_name, atts):
                remove_src = True
                break
        if remove_src:
            atts['data-need-cookies-approval'] = 'true'
            # Caso clase en la lista de vigilancia: el trabajo termina aquí.
            # El elemento podría contener un iframe creado al vuelo del lado
            # cliente; se marca ahora para que el iframe pueda marcarse
            # después, al crearse.
            # Caso src de iframe/script en la lista: se adapta el src.
            if atts.get("src"):
                atts['data-nocookie-src'] = atts['src']
                atts['src'] = 'about:blank'

    def _is_tag_domains_watchlisted(self, tag_name, atts):
        """≙ ``_is_tag_domains_watchlisted`` (``odoo19c: :2414-2427``)."""
        domains = self.blocked_third_party_domains.split('\n')
        if tag_name in ('iframe', 'script'):
            src_host = urlsplit((atts.get('src') or '').lower()).hostname
            if src_host:
                return any(
                    # "www.example.com" y "example.com" deben bloquear ambos.
                    src_host == domain.removeprefix('www.')
                    # "domain.com" debe bloquear "subdomain.domain.com", pero
                    # no "(subdomain.)mydomain.com".
                    or src_host.endswith('.' + domain.removeprefix('www.'))
                    for domain in domains
                )
        return False

    def _is_tag_classes_watchlisted(self, tag_name, atts):
        """≙ ``_is_tag_classes_watchlisted`` (``odoo19c: :2429-2430``)."""
        return self._get_blocked_iframe_containers_classes().intersection(
            (atts.get('class') or '').split(' '))

    # ── B6 (#539) · CDN, Plausible, URL canónica, snippets, cachés ───────────
    #
    # El bloque de cierre. Re-medido por AST al abrirlo (patrón de H-API-699:
    # el barrido se hace al abrir el bloque, no de memoria): la fuente declara
    # **111 métodos** y este árbol declaraba **75**, así que el resto es
    # **42**, no los 32 de la partición. De esos 42: **19 se portan aquí**,
    # **3 ya estaban cubiertos con nombre divergente** (``create``/``write`` →
    # ``save``, ``unlink`` → ``delete``; divergencia CRUD declarada en B1),
    # **9 siguen bloqueados por el banner de B4** (configurador), y **4
    # quedan bloqueados aquí** —eran 11: #545 cerró ``rule_is_enumerable``,
    # ``_enumerate_pages``, ``search_pages`` y ``check_existing_page`` (ya
    # portados sobre la URLconf en la sección de B2), y **#104** cerró
    # ``new_page`` (``:1164``), ``get_website_page_ids`` (``:1670``) y
    # ``_get_website_pages`` (``:1707``) al portar ``website.page`` con
    # ``_get_most_specific_pages`` (ver ``website_page.py``)— cada uno con
    # su pieza medida y su sucesor:
    #
    # - ``action_dashboard_redirect`` (``:1801``) — resuelve una acción y dos
    #   grupos por external ID; necesita el registro de datos por módulo.
    #   Sucesor: **#467**.
    # - ``get_client_action_url`` (``:1807``), ``get_client_action``
    #   (``:1817``), ``button_go_website`` (``:1826``) — construyen la URL y
    #   la acción del web client de la referencia (``/odoo/action-…``); el
    #   marco de cliente está sin decidir (**#488**) y esa ruta llevaría la
    #   marca del árbol de referencia a un endpoint del cliente (#416).
    #
    # Divergencias transversales del bloque, declaradas una vez aquí:
    #
    # - **Sin caché.** ``is_menu_cache_disabled`` y ``_get_cached_values``
    #   llevan ``@tools.ormcache`` en la fuente; aquí calculan siempre — la
    #   decisión de caché bajo prefork es la tarea **#542**, el mismo
    #   criterio medido de ``_get_current_website_id`` (B2).
    # - ``tools.urls.urljoin`` vive en ``src/tools/urls.py`` (raíz espejada
    #   de ``odoo/tools/``, H-API-701/#555) — la unión estricta que este
    #   bloque consume tres veces.
    # - **Plausible con default vacío.** La fuente apunta a
    #   ``https://plausible.io`` (el SaaS que su instancia consume); esta
    #   plataforma L0 no sirve endpoints de terceros por defecto (#416). El
    #   operador declara los suyos en ``ir.config_parameter``
    #   (``website.plausible_script`` / ``website.plausible_server``).

    def is_menu_cache_disabled(self):
        """≙ ``is_menu_cache_disabled`` (``odoo19c: :305-313``).

        ¿El menú del sitio contiene una ruta «de registro» (``…-123/``) o un
        menú restringido por grupo? En cualquiera de los dos casos la caché
        de plantillas del menú no puede compartirse entre usuarios.

        Divergencias declaradas: (1) sin el
        ``@tools.ormcache('self.env.uid', 'self.id', cache='templates')`` de
        la fuente — #542 (banner del bloque); (2) el campo del menú se llama
        ``route`` y ``group_ids`` es la FK singular ``group``, las dos
        divergencias ya declaradas en ``website_menu.py``.
        """
        menus = WebsiteMenu.objects.filter(website=self.pk)
        return any(
            (menu.route
             and re.search(r"[/](([^/=?&]+-)?[0-9]+)([/]|$)", menu.route))
            or menu.group_id is not None
            for menu in menus
        )

    def get_unique_path(self, page_url):
        """≙ ``get_unique_path`` (``odoo19c: :1240-1254``).

        Dada una URL, la misma URL sufijada con un contador si ya existe.
        Realineado por **#104**: la búsqueda corre sobre ``website.page``
        acotada al sitio específico — sólo ``website_id`` estricto, no
        ``website_domain()``: ``/url`` puede existir para la genérica y para
        el sitio a la vez, y el gestor de páginas administra ese duplicado
        (comentario de la fuente, conservado).

        Divergencias declaradas: (1) el ``active_test=False`` + ``sudo()``
        de la fuente son el estado por defecto de este ORM; (2) el
        interinato ``StaticPage`` sigue contando mientras sus consumidores
        REST vivan (decisión de #104) — su ``url`` es una property derivada
        del slug, sin columna que filtrar, así que su conjunto se
        materializa y se compara en Python, como antes.
        """
        page_model = model_by_name('website.page')
        current_website = self.get_current_website()
        website_id = (get_context().get('website_id')
                      or (current_website.pk if current_website else None))
        static_urls = {page.url for page in StaticPage.objects.all()}
        inc = 0
        page_temp = page_url
        while (page_model.objects.filter(
                url=page_temp, website_id=website_id).exists()
               or page_temp in static_urls):
            inc += 1
            page_temp = page_url + ('-%s' % inc)
        return page_temp

    def _get_plausible_script_url(self):
        """≙ ``_get_plausible_script_url`` (``odoo19c: :1256-1260``).

        Divergencia declarada: el default de la fuente es
        ``https://plausible.io/js/plausible.js`` — aquí vacío (#416, banner
        del bloque). Sin parámetro configurado no se inyecta script alguno.
        """
        with sudo():
            return SystemParameter.get_param('website.plausible_script', '')

    def _get_plausible_server(self):
        """≙ ``_get_plausible_server`` (``odoo19c: :1262-1266``).

        Divergencia declarada: default vacío en vez de
        ``https://plausible.io`` (#416, banner del bloque).
        """
        with sudo():
            return SystemParameter.get_param('website.plausible_server', '')

    def _get_plausible_share_url(self):
        """≙ ``_get_plausible_share_url`` (``odoo19c: :1268-1270``).

        La URL del tablero compartido de Plausible, o cadena vacía sin clave
        compartida — y también sin servidor configurado, que es la rama que
        la fuente no necesita porque su default nunca es vacío.
        """
        server = self._get_plausible_server()
        if not (self.plausible_shared_key and server):
            return ''
        embed_url = (f'/share/{self.plausible_site}'
                     f'?auth={self.plausible_shared_key}&embed=true'
                     '&theme=system')
        return urljoin(server, embed_url)

    def get_unique_key(self, string, template_module=False):
        """≙ ``get_unique_key`` (``odoo19c: :1272-1295``).

        Dada una cadena, una clave única con prefijo de módulo, sufijada con
        contador si ya existe.

        Divergencias declaradas: (1) ``ir.ui.view`` aquí no declara
        ``website_id``, así que el recorte por sitio de la fuente no tiene
        eje — la unicidad se verifica global, que es lo conservador (una
        clave única global también lo es por sitio); #104 dejó el eje por
        sitio en la página, no en la vista (divergencia 2 de
        ``website_page.py``), así que el recorte llega con la COW. (2) el
        ``active_test=False`` + ``sudo()`` de la fuente son el estado por
        defecto de este ORM: el manager no filtra ``active`` ni aplica ACL
        de lectura.
        """
        if template_module:
            string = template_module + '.' + string
        elif not string.startswith('website.'):
            string = 'website.' + string
        key_copy = string
        inc = 0
        while IrUiView.objects.filter(key=key_copy).exists():
            inc += 1
            key_copy = string + ('-%s' % inc)
        return key_copy

    @classmethod
    def search_url_dependencies(cls, res_model, res_ids):
        """≙ ``search_url_dependencies`` (``odoo19c: :1297-1358``;
        ``@api.model``).

        Dependencias «informativas» de las URL de los registros dados: qué
        registros con campos HTML citan esas URL. La fuente avisa que no
        atrapa el 100 % y que el falso positivo es más que posible; aquí
        igual. Estaba bloqueado en B2; lo desbloqueó ``_get_html_fields``.

        Divergencias declaradas, cada una con su pieza:

        - el modelo se resuelve por ``_name`` (``orm.registry``); un nombre
          desconocido levanta ``KeyError`` — el mismo tipo que el
          ``env[res_model]`` de la fuente.
        - ``Model.has_access('read')`` no tiene análogo de modelo: la
          autorización vive en la capa DRF (capacidades DEC-11), así que el
          barrido no filtra por ACL.
        - la rama ``_handle_views_and_pages`` reagrupa las vistas que
          pertenecen a páginas; ``ir.ui.view`` aquí no declara ``page_ids``
          (#104), así que las vistas se reportan como vistas.
        - el nombre de despliegue sale de ``Meta.verbose_name`` — no hay
          ``ir.model`` poblado con display names.
        - el enlace de respaldo de la fuente (``/odoo/<model>/<id>``) es la
          ruta de su web client y llevaría su marca a un endpoint del
          cliente (#416): sin ``website_url``/``url``, el enlace va vacío
          hasta que el marco de cliente exista (#488).
        - ``ilike`` → ``icontains``: Django escapa ``%``/``_`` del término,
          más estricto (y más seguro) que el ``ilike`` crudo de la fuente.
        """
        dependencies = {}
        current_website = cls.get_current_website()
        model = model_by_name(res_model)
        if model is None:
            raise KeyError(res_model)
        records = model.objects.filter(
            pk__in=[int(res_id) for res_id in res_ids])
        search_criteria = []
        for record in records:
            website = getattr(record, 'website', None) or current_website
            url = getattr(record, 'website_url', None) or record.url
            website_q = website.website_domain() if website else models.Q()
            search_criteria.append((url, website_q))
        if not search_criteria:
            return dependencies
        for dep_model, field_name in cls._get_html_fields():
            has_website = any(
                f.name == 'website' for f in dep_model._meta.get_fields())
            query = models.Q()
            for url, website_q in search_criteria:
                term = models.Q(**{f'{field_name}__icontains': url})
                if has_website:
                    term &= website_q
                query |= term
            dependency_records = list(dep_model.objects.filter(query))
            if not dependency_records:
                continue
            model_display_name = str(dep_model._meta.verbose_name)
            field_string = str(
                dep_model._meta.get_field(field_name).verbose_name)
            dependencies.setdefault(model_display_name, [])
            dependencies[model_display_name] += [{
                'field_name': field_string,
                'record_name': str(dependency),
                'link': (getattr(dependency, 'website_url', None)
                         or getattr(dependency, 'url', None) or ''),
                'model_name': model_display_name,
            } for dependency in dependency_records]
        return dependencies

    @classmethod
    def get_template(cls, template):
        """≙ ``get_template`` (``odoo19c: :1510-1513``; ``@api.model``).

        El ``.sudo()`` final de la fuente es el estado por defecto de este
        ORM (sin ACL de lectura), como declara ``get_unique_key``.
        """
        if isinstance(template, str) and '.' not in template:
            template = 'website.%s' % template
        return IrUiView._get_template_view(template)

    def get_suggested_controllers(self):
        """≙ ``get_suggested_controllers`` (``odoo19c: :1770-1779``).

        Tuplas ``(nombre, url, icono)``; el icono puede ser un nombre de
        módulo o una ruta.

        Divergencia declarada: la fuente pasa cada URL por
        ``ir.http._url_for`` (la localización de idioma del enrutado); ese
        reescritor sigue sin portar — #545 cerró la enumeración sobre la
        URLconf, no el eje de idioma en URL (familia declarada en
        ``ir_http.py`` de este addon) — así que las rutas van tal cual.
        """
        return [
            (_('Homepage'), '/', 'website'),
            (_('Contact Us'), '/contactus', 'website_crm'),
        ]

    @classmethod
    def image_url(cls, record, field, size=None):
        """≙ ``image_url`` (``odoo19c: :1781-1787``; ``@api.model``).

        URL local que apunta al campo de imagen del registro dado; el
        ``unique=`` es un hash de la fecha de escritura para invalidar la
        caché del navegador al cambiar la imagen.

        Divergencias declaradas: (1) ``write_date`` ↔ ``updated_at``
        (``TimeStampedModel``); (2) el ``record.sudo()`` de la fuente es
        innecesario — este ORM no aplica ACL en lecturas; (3) sin ``_name``
        declarado, el segmento del modelo usa el label de Django
        (``app.modelo``) y converge al nombre punteado con el barrido
        prospectivo de ``atributos-de-clase-de-modelo.md``.
        """
        sha = hashlib.sha512(
            str(getattr(record, 'updated_at', None)).encode('utf-8')
        ).hexdigest()[:7]
        size = '' if size is None else '/%s' % size
        model_name = name_of(type(record)) or type(record)._meta.label_lower
        return '/web/image/%s/%s/%s%s?unique=%s' % (
            model_name, record.pk, field, size, sha)

    def get_cdn_url(self, uri):
        """≙ ``get_cdn_url`` (``odoo19c: :1789-1798``).

        Reescribe la URI contra la base CDN si algún filtro de
        ``cdn_filters`` la matchea; si ninguno, la URI vuelve intacta. El
        ``ensure_one`` de la fuente es innecesario por construcción (banner
        de B5). El llamador decide consultar ``cdn_activated``, igual que en
        la fuente.
        """
        if not uri:
            return ''
        cdn_url = self.cdn_url
        cdn_filters = (self.cdn_filters or '').splitlines()
        for cdn_filter in cdn_filters:
            if cdn_filter and re.match(cdn_filter, uri):
                return urljoin(cdn_url, uri)
        return uri

    def _get_canonical_url(self):
        """≙ ``_get_canonical_url`` (``odoo19c: :1830-1835``).

        La URL canónica de la petición en curso, sobre el dominio del sitio.

        Divergencia declarada: la fuente delega en
        ``ir.http._url_localized`` para poner el idioma en la ruta; ese
        reescritor sigue sin portar (#545 cerró la enumeración, no el eje de
        idioma en URL — familia declarada en ``ir_http.py`` de este addon),
        así que la canónica es el dominio configurado más la ruta pedida
        (query incluida), sin prefijo de idioma.
        """
        request = get_current_request()
        path = request.get_full_path() if request is not None else '/'
        return urljoin(self.domain or '', path)

    def _is_canonical_url(self):
        """≙ ``_is_canonical_url`` (``odoo19c: :1837-1849``).

        ¿La URL pedida es la canónica? Con el eje de idioma en URL aún sin
        portar (ver ``_get_canonical_url``), la
        diferencia detectable es el dominio — que es justo la mitad que la
        fuente subraya (*«it is important to also test the domain»*). Fuera
        de una petición no hay URL que corregir: ``True``.
        """
        request = get_current_request()
        if request is None:
            return True
        return request.build_absolute_uri() == self._get_canonical_url()

    def _get_cached_values(self):
        """≙ ``_get_cached_values`` (``odoo19c: :1851-1873``).

        Los cuatro valores que el despacho HTTP necesita antes de tener el
        entorno completo.

        Divergencias declaradas: (1) sin ``@tools.ormcache('self.id')`` —
        #542 (banner del bloque); sin caché tampoco hace falta el
        ``fetch()`` selectivo con que la fuente esquiva los campos
        traducibles. (2) las claves conservan los nombres de la fuente, que
        aquí coinciden con los attname de los FK (``user_id``,
        ``company_id``, ``default_lang_id``).
        """
        return {
            'user_id': self.user_id,
            'company_id': self.company_id,
            'default_lang_id': self.default_lang_id,
            'homepage_url': self.homepage_url,
        }

    def _get_cached(self, field):
        """≙ ``_get_cached`` (``odoo19c: :1875-1876``)."""
        return self._get_cached_values()[field]

    @classmethod
    def _get_html_fields_blacklist(cls):
        """≙ ``_get_html_fields_blacklist`` (``odoo19c: :1878-1881``).

        Los nombres punteados de la referencia, verbatim;
        ``_get_html_fields`` los traduce a tabla con la misma derivación
        ``_name.replace('.', '_')`` que la referencia usa para ``_table``.
        Classmethod y no método de instancia porque la fuente lo llama sobre
        un recordset vacío sin usar ``self`` — mismo criterio que
        ``is_public_user`` en B2.
        """
        return (
            'mail.message', 'mail.activity', 'digest.tip',
        )

    @classmethod
    def _get_html_fields(cls):
        """≙ ``_get_html_fields`` (``odoo19c: :1883-1908``).

        Todos los campos HTML almacenados de los modelos no transitorios,
        sembrando ``('ir.ui.view', 'arch_db')`` como la fuente — allá el
        seed también es explícito porque ``arch_db`` no es de tipo html.

        **Divergencia de mecanismo, declarada.** La fuente consulta el
        catálogo (``ir_model_fields.ttype = 'html'``); ese catálogo no está
        poblado aquí. El equivalente vivo es la **identidad de clase**:
        desde #554 (H-API-700) ``fields.Html`` es una subclase de
        ``TextField``, así que el campo se reconoce con ``isinstance``
        sobre ``_meta.get_fields()`` — que además ve los campos heredados
        de mixins, invisibles para el rodeo por AST que este método usaba
        antes de #554.

        **Segunda divergencia (la de B3):** cada entrada lleva la CLASE del
        modelo, no su nombre punteado — la mayoría de los modelos aún no
        declara ``_name`` (mismo criterio que ``search_details['model']``
        del mixin; vuelve al nombre con el barrido prospectivo de
        ``atributos-de-clase-de-modelo.md``).

        *Métrica:* campos con ``isinstance(f, fields.Html)`` — declarados o
        heredados — en cada modelo concreto no transitorio.
        *Ciega a:* un campo HTML declarado como ``fields.Text`` o
        ``TextField`` pelado — sin la subclase no hay identidad que ver.
        """
        html_fields = [(IrUiView, 'arch_db')]
        blacklist_tables = {
            model_name.replace('.', '_')
            for model_name in cls._get_html_fields_blacklist()
        }
        for model in apps.get_models():
            meta = model._meta
            if issubclass(model, TransientModel):
                continue
            if (meta.db_table.startswith('ir_actions')
                    or meta.db_table in blacklist_tables):
                continue
            for field_name in sorted(
                    f.name for f in meta.get_fields()
                    if isinstance(f, fields.Html)):
                if (model, field_name) not in html_fields:
                    html_fields.append((model, field_name))
        return html_fields

    def _is_snippet_used(self, snippet_module, snippet_id, asset_version,
                         asset_type, html_fields):
        """≙ ``_is_snippet_used`` (``odoo19c: :1910-1934``).

        ¿Alguna aparición del snippet —en los campos HTML del árbol— usa la
        versión del asset dada?

        Divergencias declaradas: (1) el chequeo sobre la **definición de
        plantilla** del snippet exige el compilador QWeb
        (``ir.qweb._render``); ``ir_qweb.py`` es portador de vocabulario sin
        compilador, así que esa rama llega con el marco de cliente (#488) —
        consecuencia conservadora: un snippet cuyo único uso sea su propia
        plantilla se reporta como no usado, y su asset se apaga. (2) el SQL
        se compone con el cursor + ``quote_name`` — la clase ``SQL``
        componible ya está portada (#549 resuelto, mismo criterio que el
        enumerador por trigramas de B3: migrar el rodeo es opcional); el
        patrón viaja como parámetro.
        """
        if not html_fields:
            return False
        quote = connection.ops.quote_name
        pattern = f'<([^>]*data-snippet="{snippet_id}"[^>]*)>'
        selects = []
        params = []
        for model, field_name in html_fields:
            table = quote(model._meta.db_table)
            column = quote(model._meta.get_field(field_name).column)
            selects.append(
                f"SELECT regexp_matches({table}.{column}, %s, 'g')"
                f' FROM {table}')
            params.append(pattern)
        with connection.cursor() as cr:
            cr.execute(' UNION '.join(selects), params)
            snippet_occurences = [row[0][0] for row in cr.fetchall()]
        return self._check_snippet_used(
            snippet_occurences, asset_type, asset_version)

    def _disable_unused_snippets_assets(self):
        """≙ ``_disable_unused_snippets_assets`` (``odoo19c: :1955-1985``).

        Apaga (``active=False``) los assets de snippets que ya nadie usa, y
        reenciende los que reaparecen. El caso especial de
        ``s_quotes_carousel``/``s_blockquote`` se porta verbatim: cubre
        snippets viejos sin atributo ``data-snippet``.

        Divergencias declaradas: (1) el ``active_test=False`` de la fuente
        es el estado por defecto del manager de ``IrAsset``; (2) el ``like``
        con comodín interno (``/static%/snippets/``) se expresa con
        ``__regex``; (3) el ``flush_model()`` final no aplica — cada
        ``save()`` ya escribió.
        """
        snippet_assets = list(
            IrAsset.objects
            .filter(path__regex=r'/static.*/snippets/')
            .order_by('pk'))
        snippet_re = re.compile(
            r'(\w*)\/.*\/snippets\/(\w*)\/(\d{3})(?:_\w*)?\.(js|scss)')
        # El regex matchea /module/static/[…/]/snippets/snippet_id/XXX[_var].tipo
        # — _var no se conserva: sólo module, snippet_id, versión (XXX) y tipo
        # son relevantes (comentario de la fuente).
        html_fields = self._get_html_fields()
        snippet_used = {}
        for snippet_asset in snippet_assets:
            match = snippet_re.match(snippet_asset.path)
            if not match:
                continue
            snippet_module, snippet_id, asset_version, asset_type = (
                match.groups())
            if asset_type == 'scss':
                asset_type = 'css'
            # El módulo no es parte de la clave: se quiere el primero en el
            # orden de id para filtrar extensiones de módulo (fuente).
            key = (snippet_id, asset_version, asset_type)
            if key not in snippet_used:
                snippet_used[key] = self._is_snippet_used(
                    snippet_module, snippet_id, asset_version, asset_type,
                    html_fields)
            is_snippet_used = snippet_used[key]
            if is_snippet_used != snippet_asset.active:
                snippet_asset.active = is_snippet_used
                snippet_asset.save(update_fields=['active'])
                # Cobertura de data-snippet ausentes (fuente, verbatim).
                if (snippet_id == 's_quotes_carousel'
                        and asset_type == 'css'
                        and asset_version in ['000', '001']):
                    old_blockquote_key = ('s_blockquote', '000', 'css')
                    if not snippet_used.get(old_blockquote_key):
                        snippet_used[old_blockquote_key] = True
                        old_blockquote_assets = [
                            asset for asset in snippet_assets
                            if asset.path == ('website/static/src/snippets/'
                                              's_blockquote/000.scss')]
                        for old_asset in old_blockquote_assets:
                            if not old_asset.active:
                                old_asset.active = True
                                old_asset.save(update_fields=['active'])


def _view_owner(view_func):
    """El objeto que porta las declaraciones de una vista despachable.

    La misma resolución que ``CompanyContextMiddleware._view_declares_frontend``
    (``src/addons/base/models/ir_http.py:352-367``, el mecanismo de #546):
    DRF expone la clase como ``view.cls``, las CBV de Django como
    ``view.view_class``, y una FBV lleva los atributos en la propia función.
    Aquí se necesita el dueño —no sólo el booleano— porque la enumeración lee
    tres atributos (``is_frontend``, ``http_method_names``, ``sitemap``), el
    análogo del dict ``routing`` de la fuente.
    """
    return (getattr(view_func, 'cls', None)
            or getattr(view_func, 'view_class', None)
            or view_func)


def _iter_url_patterns(resolver=None, prefix='', literal=True):
    """≙ ``router.iter_rules()`` (consumido en ``odoo19c: :1603``).

    Recorre la URLconf de Django —el mapa de rutas de este árbol— y produce
    ``(route, rule, literal)`` por cada ``URLPattern`` hoja: la ruta compuesta
    con los prefijos de los ``include()``, el patrón, y si la cadena entera
    son ``path()`` literales. ``literal`` es lo que decide si la ruta se
    puede CONSTRUIR como URL — el papel del ``rule.build`` de werkzeug, que
    sobre un regex de ``re_path()`` no tiene análogo.

    Función de módulo y no método: la fuente tampoco lo declara como método
    (``iter_rules`` es del mapa, no del modelo).
    """
    if resolver is None:
        resolver = get_resolver()
    for entry in resolver.url_patterns:
        entry_literal = literal and isinstance(entry.pattern, RoutePattern)
        if isinstance(entry, URLResolver):
            yield from _iter_url_patterns(
                entry, prefix + str(entry.pattern), entry_literal)
        elif isinstance(entry, URLPattern):
            yield prefix + str(entry.pattern), entry, entry_literal


def _configurator_rpc_call(url, method='call', params=None, timeout=15):
    """El transporte de los tres RPC — ≙ ``iap_tools.iap_jsonrpc``
    (``odoo19c: addons/iap/tools/iap_tools.py:102-142``).

    Su hogar real es el addon ``iap``; esa cadena espera la DECISIÓN #413,
    así que vive aquí como función de módulo y se muda cuando se decida.
    Se porta el contrato observable de la fuente: payload JSON-RPC 2.0 con
    ``id`` aleatorio, desempaquetado de ``result``, y TODO fallo de red o
    del servidor sale como ``AccessError`` (los llamadores — p. ej.
    ``configurator_init`` en la fuente — atrapan exactamente ese tipo).
    Lo que NO se porta, con razón: ``InsufficientCreditError`` es el modelo
    de créditos IAP de Odoo (#413) y el corto-circuito ``current_test`` es
    de su runner (aquí los tests no llegan a la red: sin endpoint el RPC
    corta antes, y con endpoint se les inyecta el transporte).
    """
    payload = {
        'jsonrpc': '2.0',
        'method': method,
        'params': params,
        'id': uuid.uuid4().hex,
    }
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        body = response.json()
    except requests.exceptions.Timeout:
        raise AccessError(
            _('The request to the service timed out. The URL it tried to '
              'contact was %s') % url)
    except requests.exceptions.RequestException as error:
        raise AccessError(
            _('An error occurred while reaching %s: %s') % (url, error))
    if 'error' in body:
        raise AccessError(
            _('The external service at %s reported an error.') % url)
    return body.get('result')
