r"""``ir.http`` extendido por ``http_routing`` — el slug con nombre legible.

Adaptación de Odoo Community ``addons/http_routing/models/ir_http.py``
(``odoo19c:``, 630 líneas, LGPL-3 — atribución y aviso de licencia
preservados, DEC-KX-03). La licencia se leyó del manifest de la fuente, no de
la reputación del árbol::

    grep -oP "'license'\s*:\s*'\K[^']+" $ODOO19C/addons/http_routing/__manifest__.py
    -> LGPL-3

**Mecanismo que esa licencia habilita: copia + adaptación con atribución**
(``porte-completo-no-parcial.md``, tabla de licencias). No hace falta
reimplementar el patrón desde cero; sí adaptarlo al stack.

Por qué este addon existe aquí
==============================

``src/addons/base/models/ir_http.py`` porta el algoritmo del slug
(``slugify_one``/``slugify``) y un ``slug`` que devuelve **sólo el id** —
exactamente lo que ``base`` hace en la referencia
(``odoo19c: odoo/addons/base/models/ir_http.py:182-185``). La composición
``<nombre>-<id>`` **no vive en base**: vive aquí, y por eso cada consumidor la
reescribía a mano. Medido antes de este porte::

    grep -rn "IrHttp\.slugify_one" --include=*.py addons/ src/
    -> 2 (website_sale/controllers/serializers.py, website_sale_wishlist/…)

y el primero recomponía ``f'{slugname}-{obj.pk}'`` con un comentario que ya
decía «≙ ``_slug``» y su divergencia de SITIO declarada con sucesor #261 —
esta tarea. Ver :ref:`h-api-993`.

Censo símbolo a símbolo del addon fuente
========================================

Recorrido AST sobre los ``.py`` de producción de ``$ODOO19C/addons/http_routing``
(``tests/`` aparte, ver «Tests» abajo):

=============================  =====  ==========  =========================
Archivo                        Símb.  Portados    Ausentes con sucesor
=============================  =====  ==========  =========================
``__init__.py``                    1           1  —
``models/ir_http.py``             28          22  6 (#274 · #275)
``models/ir_qweb.py``              3           3  —
``models/res_lang.py``             1           1  —
``controllers/main.py``            2           0  2 (#274 · #275)
=============================  =====  ==========  =========================
**Total**                         35          27  8
=============================  =====  ==========  =========================

Los **28** de ``ir_http.py`` son: 2 constantes de módulo (``_UNSLUG_RE``,
``_UNSLUG_ROUTE_PATTERN``), 2 atributos de clase (``_inherit``,
``rerouting_limit``), 2 métodos de ``ModelConverter`` y **22** métodos de
``IrHttp``. Los atributos de clase se midieron con el recorrido de
``atributos-de-clase-de-modelo.md``: la fuente declara **dos** en ``IrHttp``
y **ninguno** en ``ModelConverter``; no hay un tercero que omitir.

Y **3 símbolos que este puerto AÑADE** y la fuente no tiene, cada uno porque
sustituye a algo que allá es ambiente y aquí no lo es —se nombran para que el
conteo cierre en los dos sentidos—: ``_view_declares_frontend`` y
``_view_declares_multilang`` (allá son ``rule.endpoint.routing.get(…)``, una
lectura de la metadata del ``@route``; aquí una vista de Django no lleva mapa
de routing y la declaración se lee de la clase) y ``_lang_redirect`` (agrupa
el ``redirect.set_cookie('frontend_lang', …)`` que las cinco ramas de
redirección de ``_match`` repiten idéntico).

Los **6 ausentes**, con su bloqueo MEDIDO — ninguno omitido en silencio:

1. ``_get_exception_code_values``  ·  2. ``_get_values_500_error``  ·
3. ``_get_error_html``  ·  4. ``_handle_error`` — la familia de la **página
de error**. Bloqueo: los cuatro terminan en
``env['ir.ui.view']._render_template('http_routing.404', values)``, y
``grep -rn "def _render_template" --include=*.py src/ addons/`` da **1** hit,
que es ``ir_actions_report._render_template`` (el de informes, otro objeto).
No hay motor que renderice QWeb —``IrTemplateExpressions.render`` levanta por
diseño, ver su docstring— ni existen las plantillas ``http_routing.404`` /
``4xx`` / ``http_error``. Sucesor: tarea **#274**.

5. ``get_frontend_session_info``  ·  6. ``get_translation_frontend_modules``
— bloqueo: el segundo busca sobre ``ir.module.module`` los módulos con
traducciones de frontend, y ese catálogo (``babel``/``.po``) no existe en
este árbol; el primero publica ``translationURL: '/website/translations'``,
endpoint cuyo insumo (``WebClient().translations``)
``addons/web/controllers/webclient.py`` ya declara AUSENTE por la misma
falta. Al escribirse este pase el modelo ``IrModuleModule`` tampoco
existía (medido entonces):

.. code-block:: text

    grep -rn "class IrModuleModule" --include=*.py src/ addons/   # 0 el 2026-09-02

El modelo lo aportó después ``base_install_request`` (#281); el catálogo
sigue faltando. Sucesor: tarea **#275**.

Los **2 controllers** caen por lo mismo: ``Routing.get_website_translations``
es el endpoint del punto 6 (**#275**) y ``SessionWebsite.logout`` **no añade
código** — re-declara ``/web/session/logout`` con ``website=True,
multilang=False``, o sea *metadata de enrutado*. Aquí esa metadata es el
atributo ``is_frontend`` sobre la vista
(``src/addons/base/models/ir_http.py``, ``_view_declares_frontend``), y la
vista es ``addons/web/controllers/session.py::session_logout``, archivo fuera
del alcance de este pase. Sucesor: tarea **#274** lo lleva junto con el resto
de la superficie de ``web`` que este addon toca.

``__init__.py::_post_init_hook`` está **portado, en otro hogar**: pone
``request.is_frontend = False`` como default, y eso ya lo hace
``CompanyContextMiddleware.__call__`` de ``base``, que cita esa misma línea
(``odoo19c: addons/http_routing/__init__.py:11``) al hacerlo. Duplicarlo aquí
sería un segundo dueño del mismo default.

Lo que la fuente trae y NO es Python
====================================

Medido en este árbol antes de decidir:
``find addons/ src/ -name "*.xml" | wc -l`` → **0**. Ningún addon de este
monorepo declara vistas XML; omitirlas aquí es coherencia con el árbol, no un
recorte de este pase.

- ``views/http_routing_template.xml`` — las **10 plantillas QWeb** de la
  página de error (``400``, ``403``, ``404``, ``415``, ``422``, ``4xx``,
  ``500``, ``error_message``, ``http_error``, ``http_error_debug``). Van con
  los cuatro métodos que las renderizan: tarea **#274**.
- ``static/shapes/404.svg`` — la ilustración de esa misma página: **#274**.
- ``views/res_lang_views.xml`` — dos vistas de formulario/lista de
  ``res.lang`` para el **cliente web de Odoo**. Aquí la administración es DRF
  más React; no hay receptor para una vista XML de backend.
- ``i18n/*.po`` (55 catálogos) — el catálogo de traducción de Odoo.
  ``addons/web/controllers/webclient.py`` ya declara ausente la
  infraestructura de ``babel``/``.po``: **#275**.

Werkzeug NO se usa — qué primitiva de Django ocupa su sitio
===========================================================

Este stack sirve con gunicorn; ``werkzeug`` no es dependencia. Lo que la
fuente delega en ``werkzeug.routing`` se reimplementa con las primitivas de
Django, una por una:

=================================  ====================================
Fuente (werkzeug)                  Aquí (Django)
=================================  ====================================
``routing.BaseConverter``          convertidor de ruta (``to_python``/
                                   ``to_url``) + ``register_converter``
``MapAdapter.match(path)``         ``django.urls.resolve(path)``
``MapAdapter.build(endpoint,args)``  ``django.urls.reverse(view_name, …)``
``routing.RequestRedirect``        ``APPEND_SLASH`` — la única reescritura
                                   que el resolutor de Django provoca
``exceptions.NotFound``            ``django.urls.Resolver404``
``exceptions.abort(redirect)``     devolver la respuesta desde el
                                   middleware / ``process_view``
``werkzeug.urls.url_join/quote``   ``urllib.parse.urljoin`` / ``quote_plus``
=================================  ====================================

Los dos primeros son los que importan: el convertidor es lo que hace que una
URL declare ``<model('product.template'):product>`` y reciba el **registro**,
y ``resolve``/``reverse`` son el par que permite portar ``url_rewrite``,
``_is_multilang_url``, ``_url_localized`` y el redirect SEO de
``_pre_dispatch`` sin inventar un router.

Divergencias declaradas
=======================

1. **``_inherit = 'ir.http'`` → ``chain_method`` sobre ``base.IrHttp``**, no
   subclase. Los consumidores de este árbol importan ``IrHttp`` **de base**
   (``website_sale/controllers/serializers.py``,
   ``website_sale_wishlist/…``); una subclase dejaría ``_slug`` fuera de su
   alcance y obligaría a cambiar sus imports y el ``depends`` de sus
   manifiestos. Colgar los métodos sobre la clase de ``base`` desde
   ``ready()`` es el idioma que ``web`` ya usa para el mismo modelo
   (``addons/web/models/ir_http.py::apply_web_extensions`` cuelga
   ``is_a_bot``), y reproduce lo que en la referencia significa instalar el
   módulo: ``env['ir.http']._slug`` pasa a ser el de ``http_routing`` **para
   todos**.

2. **``cls._slugify`` → ``cls.slugify``.** El porte de ``base`` promovió
   ``_slugify_one``/``_slugify``/``_slug``/``_unslug`` a nombre público
   (sin guion bajo). Eso es el defecto que ``porte-completo-no-parcial.md``
   llama *despromoción* y tiene sucesor propio: tarea **#270** sobre
   ``src/addons/base/models/ir_http.py``, archivo que este pase **no toca**.
   Consecuencia hoy: ``base`` expone ``slug``/``unslug`` (id pelado) y este
   addon instala ``_slug``/``_unslug`` (con nombre) — dos nombres donde la
   fuente tiene uno. ``chain_method`` está escrito para que el día que #270
   restituya el guion bajo, ``_slug`` pase a **encadenar** sobre el de base
   sin tocar este archivo.

3. **``record.with_context(_converter_value=value)`` → atributo en la
   instancia.** Este ORM no tiene contexto de entorno por registro. El
   convertidor deja ``record._converter_value = value``, que es el dato que
   la fuente guarda y el que ``website._slug_matching`` lee.

4. **``request.future_response.set_cookie`` → cookie pendiente en la
   petición.** Django no tiene respuesta futura durante el despacho.
   ``_frontend_pre_dispatch`` deja el par en
   ``request._frontend_lang_cookie`` y ``FrontendLangMiddleware`` lo aplica a
   la respuesta — el mismo reparto que ``UtmCookieMiddleware`` ya usa para
   ``_post_dispatch``.

5. **``_match`` cambia lo que devuelve.** La fuente devuelve ``(rule, args)``
   y **aborta** con la redirección vía excepción. Aquí devuelve
   ``(respuesta_o_None, path)``: en Django una redirección se devuelve, no se
   lanza, y devolver la decisión hace el método probable en aislamiento sin
   levantar un servidor. La rama de 404 sigue **propagando** ``Resolver404``,
   como la fuente propaga ``NotFound``.

6. **La guarda de reentrada de ``_match``.** La fuente corta con
   ``hasattr(request, 'is_frontend')``. Aquí ese atributo lo pone SIEMPRE
   ``CompanyContextMiddleware`` (default ``False``), así que la guarda
   cortaría siempre: se usa una marca propia, ``_http_routing_matched``.

7. **404 sin vista → ``is_frontend = False``**, donde la fuente pone ``True``
   (``odoo19c: :478-479``). No es una decisión nueva:
   ``src/addons/base/models/ir_http.py`` ya la tomó y la midió — su razón es
   que el 404 aquí lo responde DRF en JSON y no hay render de sitio, que es
   justamente lo que la tarea **#274** desbloquearía. Se respeta la decisión
   vigente del árbol (Clausula 1 del principio rector) en vez de
   contradecirla desde este archivo.

8. **``prefetch_langs`` de ``_url_localized`` queda inerte.** El parámetro se
   conserva porque la firma es contrato (``porte-completo-no-parcial.md``),
   pero su cuerpo en la fuente re-navega los argumentos de tipo registro con
   ``with_context(prefetch_langs=True)``, y este ORM no tiene ese contexto ni
   campos traducidos. Declarado inerte, no omitido.

``FrontendLangMiddleware`` NO se cablea en ``MIDDLEWARE``
========================================================

El despacho que invoca ``_match``/``_pre_dispatch`` está escrito y probado en
aislamiento, y **no** se añade a ``MIDDLEWARE``: cambiaría el enrutado de
TODA petición del proyecto. Es decisión del ejecutor — tarea **#276**.

Tests
=====

Los ``tests/`` de la fuente (``common.py::MockRequest``,
``test_res_lang.py``) no se portan a ``addons/http_routing/tests/``: en este
árbol los tests viven en ``tests/unit/<addon>/`` y ``tests/integration/``.
``MockRequest`` es el mock del ``request`` global de Werkzeug — aquí la
petición se construye con ``django.test.RequestFactory``, y
``test_create_res_lang`` prueba el ``Form`` del cliente web de Odoo, que este
árbol no tiene. Los casos de este porte están en
``tests/unit/http_routing/``.
"""
import logging
import re
import urllib.parse

from django.conf import settings
from django.http import HttpResponsePermanentRedirect, HttpResponseRedirect
from django.urls import Resolver404, register_converter, resolve, reverse
from django.urls.exceptions import NoReverseMatch

from addons.base.models.ir_default import IrDefault
from addons.base.models.ir_http import (
    CompanyContextMiddleware,
    IrHttp,
    get_current_request,
)
from addons.base.models.ir_template_expressions import keep_query
from addons.base.models.res_lang import ResLang
from orm.method_chain import chain_method, merge_dict
from orm.registry import cache_of, model_by_name

_logger = logging.getLogger(__name__)

# NOTE: el segundo patrón lo usa ModelConverter — no lleva ni flags ni grupos.
# ≙ ``odoo19c: :25-27``, verbatim (el comentario incluido: explica por qué hay
# dos y no uno).
_UNSLUG_RE = re.compile(r'(?:(\w{1,2}|\w[\w-]+?\w)-)?(-?\d+)(?=$|\/|#|\?)')
_UNSLUG_ROUTE_PATTERN = r'(?:(?:\w{1,2}|\w[\w-]+?\w)-)?(?:-?\d+)(?=$|\/|#|\?)'

#: ≙ ``rerouting_limit = 10`` (``odoo19c: :48``) — atributo de clase de
#: ``IrHttp``. Se cuelga sobre ``base.IrHttp`` junto con los métodos
#: (``apply_http_routing_extensions``), que es donde la fuente lo declara.
REROUTING_LIMIT = 10


class ModelConverter:
    """≙ ``ModelConverter`` (``odoo19c: :30-42``) — un slug de la URL al registro.

    En la fuente hereda de ``ir_http.ModelConverter`` de ``base``, que a su vez
    hereda de ``werkzeug.routing.BaseConverter``. Aquí es un **convertidor de
    ruta de Django**: el mismo contrato de dos direcciones —``to_python`` para
    entrar, ``to_url`` para salir— con ``regex`` en vez del ``regex`` de
    Werkzeug (el nombre coincide).

    Lo que la subclase añade sobre la de ``base``, y se conserva entero:

    - ``regex = _UNSLUG_ROUTE_PATTERN`` — deja de aceptar sólo dígitos y pasa a
      aceptar ``<nombre>-<id>``. Es lo que hace legible la URL.
    - el ``domain``, que la fuente guarda sin consumirlo en este archivo.
    - la tolerancia al id negativo: nuestro patrón admite ``-42`` y, si ese
      registro no existe, se reintenta con ``abs()``.

    Divergencia de mecanismo: Django registra los convertidores **por nombre
    global** (``register_converter(cls, 'model')``) y no admite argumentos por
    ruta como ``<model('product.template'):x>``. Por eso el modelo viaja como
    atributo de clase y :func:`register_model_converter` fabrica una subclase
    por modelo — la misma información, expresada donde este stack la admite.
    """

    regex = _UNSLUG_ROUTE_PATTERN

    #: Nombre del modelo en notación de punto, resuelto por
    #: ``orm.registry.model_by_name`` — ≙ el ``self.model`` que la fuente
    #: recibe en el constructor.
    model = None
    domain = '[]'

    def __init__(self, url_map=None, model=False, domain='[]'):
        """≙ ``__init__`` (``odoo19c: :32-35``).

        ``url_map`` se conserva en la firma —es contrato— aunque Django
        instancie el convertidor sin él: el registro de rutas de Django no se
        pasa al convertidor, así que queda en ``None`` y no se consulta.
        """
        self.url_map = url_map
        if model:
            self.model = model
        self.domain = domain

    def to_python(self, value):
        """≙ ``to_python`` (``odoo19c: :37-42``) — el slug al registro.

        Soporte limitado de ids negativos por culpa del propio patrón de slug:
        si no existe, se asume el ``abs()``. Es la nota de la fuente, verbatim.
        """
        identifier = _unslug(value)[1]
        record = self._browse(identifier)
        if record is None and identifier is not None and identifier < 0:
            record = self._browse(abs(identifier))
        if record is not None:
            # ≙ ``with_context(_converter_value=value)``: este ORM no tiene
            # contexto por registro, así que el dato viaja en la instancia.
            record._converter_value = value
        return record

    def to_url(self, value):
        """≙ ``to_url`` (``odoo19c: odoo/addons/base/models/ir_http.py:77-78``).

        Heredado de la de ``base``, que devuelve ``IrHttp._slug(value)``. Con
        este addon instalado ese ``_slug`` es el de nombre legible, que es
        justamente el punto del módulo.
        """
        return _slug(IrHttp, value)

    def _browse(self, identifier):
        """El ``env[self.model].browse(id)`` de la fuente, en este ORM."""
        if identifier is None or self.model is None:
            return None
        return model_by_name(self.model).objects.filter(pk=identifier).first()


def model_converter_for(model_name, domain='[]'):
    """La subclase de :class:`ModelConverter` atada a un modelo.

    Existe porque Django registra convertidores por nombre global; ver la
    divergencia de mecanismo en el docstring de :class:`ModelConverter`.
    """
    return type(
        'ModelConverter_%s' % model_name.replace('.', '_'),
        (ModelConverter,),
        {'model': model_name, 'domain': domain},
    )


def register_model_converter(name, model_name, domain='[]'):
    """Registra ``<name:arg>`` como convertidor de ``model_name`` en Django."""
    register_converter(model_converter_for(model_name, domain), name)


# ---------------------------------------------------------------------------
# Slug tools — ≙ la sección homónima de la fuente (``odoo19c: :50-96``)
# ---------------------------------------------------------------------------

def _slug(cls, value):
    """≙ ``_slug`` (``odoo19c: :54-66``) — ``<nombre-slugificado>-<id>``.

    Acepta el registro o la tupla ``(id, nombre)`` que devuelve un
    ``name_search``. Si el nombre no deja ningún carácter de palabra, devuelve
    **sólo el id** — no ``-42``: esa rama de la fuente se conserva porque es
    la que hace que un producto llamado ``???`` siga teniendo URL.

    ``cls.slugify`` y no ``cls._slugify``: ver la divergencia 2 del módulo
    (la despromoción de ``base``, sucesor #270).
    """
    try:
        identifier, name = value.pk, value.display_name
    except AttributeError:
        # Se asume la tupla de un name_search — ≙ el comentario de la fuente.
        identifier, name = value
    if not identifier:
        raise ValueError("Cannot slug non-existent record %s" % value)
    slugname = cls.slugify(name or '')
    if not slugname:
        return str(identifier)
    return f"{slugname}-{identifier}"


def _unslug(cls_or_value, value=None):
    """≙ ``_unslug`` (``odoo19c: :68-76``) — el slug a ``(nombre, id)``.

    Siempre devuelve una 2-tupla ``(str|None, int|None)``. El primer elemento
    es el trozo legible; devolver sólo el entero rompería a quien desempaqueta
    dos valores, que es el contrato de la fuente.

    Admite las dos formas de llamada —``_unslug('x-1')`` como función suelta y
    ``IrHttp._unslug('x-1')`` una vez instalada como ``classmethod``— porque el
    convertidor la usa antes de que el registro esté poblado.
    """
    if value is None and isinstance(cls_or_value, str):
        value = cls_or_value
    match = _UNSLUG_RE.match(value or '')
    if not match:
        return None, None
    return match.group(1), int(match.group(2))


def _unslug_url(cls, value):
    """≙ ``_unslug_url`` (``odoo19c: :78-87``) — de ``/blog/mi-blog-1`` a ``blog/1``."""
    parts = value.split('/')
    if parts:
        unslug_val = _unslug(parts[-1])
        if unslug_val[1]:
            parts[-1] = str(unslug_val[1])
            return '/'.join(parts)
    return value


def _get_converters(cls):
    """≙ ``_get_converters`` (``odoo19c: :89-96``) — el mapa de convertidores.

    La fuente hace ``dict(super()._get_converters(), model=ModelConverter)``.
    Aquí ``base`` no declara ninguno (medido: ``grep -n "_get_converters"
    src/addons/base/models/ir_http.py`` → **0**), así que el mapa nace con esta
    entrada; ``chain_method(..., combine=merge_dict)`` reproduce el ``dict(...)``
    de la fuente el día que ``base`` declare el suyo.
    """
    return {'model': ModelConverter}


# ---------------------------------------------------------------------------
# Language tools — ≙ la sección homónima de la fuente (``odoo19c: :98-320``)
# ---------------------------------------------------------------------------

def _get_default_lang(cls):
    """≙ ``_get_default_lang`` (``odoo19c: :258-263``).

    El idioma por defecto del sitio: el que ``ir.default`` fija para
    ``res.partner.lang``, y si no hay, el primero de los activos. El orden de
    ``ResLang`` (``Meta.ordering = ['-active', 'name']``) reproduce el
    ``_order = "active desc,name"`` de la fuente, así que "el primero" es el
    mismo registro de los dos lados.
    """
    lang_code = IrDefault._get('res.partner', 'lang')
    if lang_code:
        return ResLang.objects.filter(code=lang_code).first()
    return next(iter(ResLang._get_frontend().values()), None)


def get_nearest_lang(cls, lang_code):
    """≙ ``get_nearest_lang`` (``odoo19c: :301-314``) — ``fr_BE`` cae en ``fr_FR``."""
    if not lang_code:
        return None

    frontend_langs = ResLang._get_frontend()
    if lang_code in frontend_langs:
        return lang_code

    short = lang_code.partition('_')[0]
    if not short:
        return None
    return next((code for code in frontend_langs if code.startswith(short)), None)


def _get_translation_frontend_modules_domain(cls):
    """≙ ``_get_translation_frontend_modules_domain`` (``odoo19c: :287-292``).

    El cuerpo de la fuente es ``return []`` y eso **es** el porte: existe para
    que otro addon lo extienda sin tocar el consumidor. Mismo criterio con que
    ``base`` porta ``sanitize_cookies``.
    """
    return []


def _get_translation_frontend_modules_name(cls):
    """≙ ``_get_translation_frontend_modules_name`` (``odoo19c: :294-299``)."""
    return ['web']


def _view_declares_frontend(cls, view_func):
    """≙ ``routing.get('website', False)`` del endpoint despachado.

    Delega en ``CompanyContextMiddleware._view_declares_frontend``, que es
    quien ya porta esa lectura en este árbol (tarea #546) y quien midió dónde
    la declara cada estilo de vista (DRF ``.cls``, CBV ``.view_class``, FBV la
    propia función). Reimplementarla aquí sería una segunda fuente de verdad.
    """
    return CompanyContextMiddleware._view_declares_frontend(view_func)


def _view_declares_multilang(cls, view_func):
    """≙ ``routing.get('multilang', routing['type'] == 'http')``.

    En la fuente el default depende del ``type`` del endpoint: ``'http'`` sí,
    ``'json'`` no. Aquí **toda** vista responde HTTP —DRF negocia el formato
    por cabecera, no por tipo de ruta—, así que el default es ``True`` y la
    vista lo niega declarando ``is_frontend_multilang = False``, que es el
    ``multilang=False`` del ``@route`` de la fuente.
    """
    owner = (getattr(view_func, 'cls', None)
             or getattr(view_func, 'view_class', None)
             or view_func)
    return bool(getattr(owner, 'is_frontend_multilang', True))


#: La clave con que la fuente indexa esta caché es ``(self._name, method,
#: path, query_args)`` — ``tools.cache.ormcache.determine_key``. Aquí el
#: nombre del modelo se escribe literal en vez de leerse de ``cls._name``
#: porque ``base.IrHttp`` **no declara** ``_name`` todavía (medido:
#: ``grep -c "_name = " src/addons/base/models/ir_http.py`` -> 0), y ese
#: archivo es de otro pase (sucesor #270). El decorador ``@ormcache`` no se
#: puede usar por eso mismo: su ``key`` evalúa ``<primer_parámetro>._name`` y
#: reventaría con ``AttributeError`` en la primera llamada — medido, no
#: supuesto. El mecanismo se **construye** aquí (misma ranura, misma forma de
#: clave) en vez de declarar la caché ausente; el día que ``_name`` exista,
#: esto vuelve a ser el decorador de una línea.
_REWRITE_MODEL_NAME = 'ir.http'


def _url_rewrite_uncached(path, query_args=None):
    """El cuerpo de :func:`url_rewrite`, sin caché — ver su docstring."""
    new_url = False
    endpoint = False
    try:
        endpoint = resolve(path).func
    except Resolver404:
        # ≙ ``werkzeug.routing.RequestRedirect``: la única reescritura que el
        # resolutor provoca por sí mismo. En Werkzeug es la barra final
        # (``strict_slashes``); en Django es ``APPEND_SLASH``, y se consulta
        # el ajuste en vez de asumirlo.
        if getattr(settings, 'APPEND_SLASH', False) and not path.endswith('/'):
            try:
                endpoint = resolve(path + '/').func
            except Resolver404:
                new_url = path
            else:
                new_url = path + '/'
        else:
            new_url = path
    return new_url or path, endpoint or None


def url_rewrite(cls, path, query_args=None):
    """≙ ``url_rewrite`` (``odoo19c: :613-630``) — ``(url, endpoint)``.

    La fuente prueba ``POST`` y cae a ``GET`` porque su router discrimina por
    método; el resolutor de Django no lo hace —el método lo decide la vista—,
    así que la doble prueba no tiene receptor y se resuelve una vez.
    ``query_args`` se conserva en la firma (es contrato y es clave de caché)
    aunque ``resolve`` no lo consuma: en la fuente sólo sirve para desempatar
    rutas con ``?``, cosa que la URLconf de Django no admite.

    La caché es la misma ranura que la fuente declara —``routing.rewrites``,
    ya dimensionada en ``src/orm/registry.py``— y la misma forma de clave; ver
    :data:`_REWRITE_MODEL_NAME` por qué se construye a mano en vez de con el
    decorador ``@ormcache``. La vacía ``orm.registry.clear_cache`` igual que a
    las demás, porque es el mismo contenedor.
    """
    cache = cache_of('routing.rewrites')
    key = (_REWRITE_MODEL_NAME, url_rewrite, path, query_args)
    try:
        return cache[key]
    except KeyError:
        result = _url_rewrite_uncached(path, query_args)
        cache[key] = result
        return result


def _is_multilang_url(cls, local_url, lang_url_codes=None):
    """≙ ``_is_multilang_url`` (``odoo19c: :220-256``) — ¿esta URL se traduce?

    Dos condiciones, en el orden de la fuente: nada bajo ``/static/`` ni
    ``/web/``; y del resto, se traduce lo que no tiene endpoint o cuyo
    endpoint se declara de sitio **y** multilingüe.
    """
    if not lang_url_codes:
        lang_url_codes = [lang.url_code for lang in ResLang._get_frontend().values()]
    spath = local_url.split('/')
    # Si ya hay un idioma en la ruta, se quita.
    if spath[1] in lang_url_codes:
        spath.pop(1)
        local_url = '/'.join(spath)

    url = local_url.partition('#')[0].split('?')
    path = url[0]

    # /static/ y /web/ no son multilingües.
    if '/static/' in path or path.startswith('/web/'):
        return False

    query_string = url[1] if len(url) > 1 else None

    try:
        __, func = url_rewrite(cls, path, query_args=query_string)
        # Una ruta sin endpoint (p. ej. una página servida por el CMS) sí es
        # multilingüe — ≙ el comentario "/page/xxx has no endpoint" de la fuente.
        return (not func or (_view_declares_frontend(cls, func)
                             and _view_declares_multilang(cls, func)))
    except Exception as exception:  # noqa: BLE001
        _logger.warning(exception)
        return False


def _url_lang(cls, path_or_uri, lang_code=None):
    """≙ ``_url_lang`` (``odoo19c: :162-208``) — pone o quita el idioma.

    Nada se hace con una URL absoluta o inválida. Con un solo idioma instalado
    tampoco, salvo que se fuerce pasando ``lang_code`` — que es la razón de
    que exista ``force_lang`` y no un simple ``if``.
    """
    request = get_current_request()
    location = path_or_uri.strip()
    force_lang = lang_code is not None
    try:
        url = urllib.parse.urlparse(location)
    except ValueError:
        # p. ej. IPv6 inválida — ``urlparse('http://]')``.
        url = False
    # URL relativa, con ruta o con idioma forzado.
    if url and not url.netloc and not url.scheme and (url.path or force_lang):
        base_path = request.path if request is not None else '/'
        location = urllib.parse.urljoin(base_path, location)
        frontend_langs = ResLang._get_frontend()
        lang_url_codes = [info.url_code for info in frontend_langs.values()]
        lang_code = lang_code or getattr(request, 'LANGUAGE_CODE', None) or settings.LANGUAGE_CODE
        lang_row = frontend_langs.get(lang_code) or ResLang.objects.filter(code=lang_code).first()
        lang_url_code = lang_row.url_code if lang_row is not None else lang_code
        lang_url_code = lang_url_code if lang_url_code in lang_url_codes else lang_code
        if (len(lang_url_codes) > 1 or force_lang) and _is_multilang_url(cls, location, lang_url_codes):
            loc, sep, qs = location.partition('?')
            ps = loc.split('/')
            default_lg = _get_default_lang(cls)
            if ps[1] in lang_url_codes:
                # Se reemplaza el idioma sólo si se pidió uno explícito.
                if force_lang:
                    ps[1] = lang_url_code
                # Se quita el idioma por defecto salvo que se pidiera explícito.
                elif default_lg is not None and ps[1] == default_lg.url_code:
                    ps.pop(1)
            # Se inserta el del contexto, o el pedido.
            elif default_lg is None or lang_url_code != default_lg.url_code or force_lang:
                ps.insert(1, lang_url_code)
                # Quitar el último vacío evita la barra final al unir.
                if not ps[-1]:
                    ps.pop(-1)

            location = '/'.join(ps) + sep + qs
    return location


def _url_for(cls, url_from, lang_code=None):
    """≙ ``_url_for`` (``odoo19c: :209-218``) — la URL con la reescritura aplicada."""
    return _url_lang(cls, url_from, lang_code=lang_code)


def _url_localized(cls, url=None, lang_code=None, canonical_domain=None,
                   prefetch_langs=False, force_default_lang=False):
    """≙ ``_url_localized`` (``odoo19c: :103-160``) — la URL en otro idioma.

    Dos cosas a la vez: sufijar el idioma y **reconstruir** las partes de
    convertidor de modelo, para que ``/shop/my-phone-14`` dé
    ``/fr/shop/mon-telephone-14`` y no una traducción a medias del path.

    La reconstrucción es ``resolve`` + ``reverse`` (el par que sustituye a
    ``MapAdapter.match``/``build``). Si no se puede reconstruir se usa la ruta
    tal cual, citada — igual que la fuente.

    ``prefetch_langs`` queda inerte: ver la divergencia 8 del módulo.
    """
    request = get_current_request()
    if not lang_code:
        lang = getattr(request, 'lang', None) or _get_default_lang(cls)
    else:
        lang = ResLang.objects.filter(code=lang_code).first()

    if not url:
        qs = keep_query(request.GET) if request is not None else ''
        url = (request.path if request is not None else '/') + ('?%s' % qs if qs else '')

    # '/shop/silla-17?' -> '/shop/silla-17', si no da 404.
    url, sep, qs = url.partition('?')

    try:
        match = resolve(url)
        path = reverse(match.view_name, args=match.args, kwargs=match.kwargs)
    except (Resolver404, NoReverseMatch):
        # ``build`` devuelve la URL ya citada; se cita aquí por consistencia.
        path = urllib.parse.quote_plus(url, safe='/')
    if lang is not None and (force_default_lang or lang != _get_default_lang(cls)):
        path = f'/{lang.url_code}{path if path != "/" else ""}'

    if canonical_domain:
        # Una URL canónica no lleva query string.
        return urllib.parse.urljoin(canonical_domain, path)

    return path + sep + qs


# ---------------------------------------------------------------------------
# Routing and dispatch — ≙ la sección homónima (``odoo19c: :319-522``)
# ---------------------------------------------------------------------------

def _match(cls, path):
    r"""≙ ``_match`` (``odoo19c: :322-481``) — el idioma en la URL, en 9 ramas.

    Devuelve ``(respuesta_o_None, path)``; ver la divergencia 5 del módulo por
    qué no devuelve ``(rule, args)``. Las nueve ramas de la fuente se
    conservan con su numeración y su orden — el orden **es** la semántica:

    1. URL tal cual si el endpoint no es multilingüe.
    2. URL tal cual si no hay idioma en la URL y se pide el por defecto.
    3. URL tal cual, recordando el idioma, si quien pide es un bot.
    4. URL tal cual si falta el idioma pero no se puede redirigir (POST).
    5. Redirigir inyectando el idioma pedido.
    6. Redirigir quitando el idioma por defecto.
    7. Redirigir del alias al código de URL preferido (``fr_FR`` → ``fr``).
    8. Redirigir la portada con barra final.
    9. Reescribir quitando el idioma cuando es válido y no es el por defecto.

    El idioma pedido es, en orden: el de la URL, el de la cookie
    ``frontend_lang``, el del contexto, el por defecto del sitio.
    """
    request = get_current_request()
    if request is None:
        return None, path

    # La URL ya fue reescrita — ≙ la guarda ``hasattr(request, 'is_frontend')``
    # de la fuente; ver la divergencia 6 del módulo.
    if getattr(request, '_http_routing_matched', False):
        return None, path
    request._http_routing_matched = True

    # Ver /1, un endpoint que no es de sitio.
    try:
        rule = resolve(path)
    except Resolver404:
        __, url_lang_str, *rest = path.split('/', 2)
        path_no_lang = '/' + (rest[0] if rest else '')
    else:
        request.is_frontend = _view_declares_frontend(cls, rule.func)
        request.is_frontend_multilang = (request.is_frontend
                                         and _view_declares_multilang(cls, rule.func))
        if not request.is_frontend:
            return None, path
        url_lang_str = ''
        path_no_lang = path

    allow_redirect = (request.method != 'POST'
                      and getattr(request, 'is_frontend_multilang', True))

    # Dos URLs concatenadas dejan una doble barra que hay que fundir.
    if allow_redirect and '//' in path:
        return HttpResponsePermanentRedirect(path.replace('//', '/')), path

    frontend_langs = ResLang._get_frontend()
    url_lang_row = ResLang.objects.filter(url_code=url_lang_str).first() if url_lang_str else None
    nearest_url_lang = get_nearest_lang(
        cls, (url_lang_row.code if url_lang_row is not None else None) or url_lang_str)
    cookie_lang = get_nearest_lang(cls, request.COOKIES.get('frontend_lang'))
    context_lang = get_nearest_lang(cls, getattr(request, 'LANGUAGE_CODE', None))
    default_lang = _get_default_lang(cls)
    chosen = (nearest_url_lang or cookie_lang or context_lang
              or (default_lang.code if default_lang is not None else None))
    request.lang = (frontend_langs.get(chosen)
                    or ResLang.objects.filter(code=chosen).first())
    request_url_code = request.lang.url_code if request.lang is not None else ''

    if not nearest_url_lang:
        url_lang_str = None

    # Ver /2, sin idioma en la URL y sitio por defecto.
    if not url_lang_str and request.lang == default_lang:
        _logger.debug("%r (lang: %r) sin idioma en la URL y sitio por defecto, continuar",
                      path, request_url_code)

    # Ver /3, falta el idioma pero quien pide es un bot.
    elif not url_lang_str and IrHttp.is_a_bot(request.META.get('HTTP_USER_AGENT', '')):
        _logger.debug("%r (lang: %r) falta el idioma pero es un bot, continuar",
                      path, request_url_code)
        request.lang = default_lang

    # Ver /4, sin idioma en la URL y no se debe redirigir (p. ej. POST).
    elif not url_lang_str and not allow_redirect:
        _logger.debug("%r (lang: %r) sin idioma en la URL y sin redirección, continuar",
                      path, request_url_code)

    # Ver /5, falta el idioma en la URL: /home -> /fr/home
    elif not url_lang_str:
        _logger.debug("%r (lang: %r) falta el idioma en la URL, redirigir",
                      path, request_url_code)
        return cls._lang_redirect(HttpResponseRedirect(f'/{request_url_code}{path}'),
                                  request.lang), path

    # Ver /6, el idioma por defecto en la URL: /en/home -> /home
    elif default_lang is not None and url_lang_str == default_lang.url_code and allow_redirect:
        _logger.debug("%r (lang: %r) idioma por defecto en la URL, redirigir",
                      path, request_url_code)
        return cls._lang_redirect(HttpResponseRedirect(path_no_lang), default_lang), path

    # Ver /7, un alias en la URL: /fr_FR/home -> /fr/home
    elif url_lang_str != request_url_code and allow_redirect:
        _logger.debug("%r (lang: %r) alias de idioma en la URL, redirigir",
                      path, request_url_code)
        return cls._lang_redirect(
            HttpResponsePermanentRedirect(f'/{request_url_code}{path_no_lang}'),
            request.lang), path

    # Ver /8, la portada con barra final: /fr_BE/ -> /fr_BE
    elif path == f'/{url_lang_str}/' and allow_redirect:
        _logger.debug("%r (lang: %r) portada con barra final, redirigir",
                      path, request_url_code)
        return cls._lang_redirect(HttpResponsePermanentRedirect(path[:-1]),
                                  default_lang), path

    # Ver /9, idioma válido en la URL: se reescribe quitándolo.
    elif url_lang_str == request_url_code:
        _logger.debug("%r (lang: %r) idioma válido en la URL, reescribir y continuar",
                      path, request_url_code)
        path = path_no_lang

    else:
        _logger.warning("%r (lang: %r) no se pudo enrutar esta petición de sitio, "
                        "URL usada tal cual.", path, request_url_code)

    # Re-resolver con la ruta reescrita, y sí levantar de verdad en 404.
    try:
        rule = resolve(path)
    except Resolver404:
        # Ver la divergencia 7 del módulo: aquí el 404 NO se marca de sitio.
        request.is_frontend = False
        request.is_frontend_multilang = False
        raise
    request.is_frontend = _view_declares_frontend(cls, rule.func)
    request.is_frontend_multilang = (request.is_frontend
                                     and _view_declares_multilang(cls, rule.func))
    return None, path


def _lang_redirect(cls, response, lang):
    """La redirección de ``_match`` con su cookie ``frontend_lang``.

    Las cinco ramas de redirección de la fuente hacen lo mismo:
    ``redirect.set_cookie('frontend_lang', <code>)``. Aquí se agrupa en un
    solo sitio porque en Django la respuesta se devuelve, y repetir el
    ``set_cookie`` cinco veces sería copiar el mismo par cinco veces.
    """
    if lang is not None:
        response.set_cookie('frontend_lang', lang.code)
    return response


def _pre_dispatch(cls, rule, args):
    """≙ ``_pre_dispatch`` (``odoo19c: :482-513``) — el redirect SEO 301.

    Un producto con id 1 llamado ``huevo`` es accesible por ``/foo/1``; la URL
    preferida es ``/foo/huevo-1``, y esta redirección es la que lleva de una a
    otra. La razón real es SEO, no estética: dos URLs para el mismo recurso
    dividen el ranking.

    Devuelve la respuesta de redirección, o ``None``. ``rule`` es el
    ``ResolverMatch`` de Django, el análogo de la ``Rule`` de Werkzeug.

    Divergencia: la fuente re-navega los argumentos de tipo registro con el
    contexto de la petición (``val.with_context(request.env.context)``). Este
    ORM no tiene contexto de entorno, así que ese bucle no tiene receptor —
    los argumentos ya llegan resueltos por el convertidor.
    """
    request = get_current_request()
    if request is None:
        return None

    if getattr(request, 'is_frontend', False):
        _frontend_pre_dispatch(cls)

    if getattr(request, 'is_frontend_multilang', False):
        if request.method in ('GET', 'HEAD'):
            try:
                path = reverse(rule.view_name, args=rule.args, kwargs=args)
            except NoReverseMatch:
                return None
            generated_path = urllib.parse.unquote_plus(path)
            current_path = urllib.parse.unquote_plus(request.path)
            if generated_path != current_path:
                lang = getattr(request, 'lang', None)
                default_lang = _get_default_lang(cls)
                if lang is not None and lang != default_lang:
                    path = f'/{lang.url_code}{path}'
                return HttpResponsePermanentRedirect(path)
    return None


def _frontend_pre_dispatch(cls):
    """≙ ``_frontend_pre_dispatch`` (``odoo19c: :514-518``).

    Fija el idioma del contexto y deja pendiente la cookie ``frontend_lang``.
    Ver la divergencia 4 del módulo por qué la cookie queda pendiente en la
    petición en vez de escribirse en una "respuesta futura".
    """
    request = get_current_request()
    if request is None:
        return
    lang = getattr(request, 'lang', None)
    if lang is None:
        return
    # ≙ ``request.update_context(lang=...)``: el contexto de idioma de esta
    # petición en Django es ``LANGUAGE_CODE``.
    request.LANGUAGE_CODE = lang.code
    if request.COOKIES.get('frontend_lang') != lang.code:
        request._frontend_lang_cookie = ('frontend_lang', lang.code)


def apply_http_routing_extensions():
    """Cuelga ``http_routing`` sobre ``base.IrHttp`` — ≙ ``_inherit = 'ir.http'``.

    Se invoca desde ``HttpRoutingConfig.ready()``, cuando el registro de
    modelos ya está poblado y ``setattr`` sobre ``base.IrHttp`` no rompe con
    ``AppRegistryNotReady``. Mismo patrón que
    ``addons/web/models/ir_http.py::apply_web_extensions``.

    ``rerouting_limit`` se cuelga junto con los métodos porque en la fuente es
    un atributo de la **misma** clase (``odoo19c: :48``), y
    ``atributos-de-clase-de-modelo.md`` exige portar todos los que la fuente
    declare o ninguno: son dos (``_inherit`` y éste), y ``_inherit`` es
    justamente lo que este mecanismo materializa.
    """
    if not hasattr(IrHttp, 'rerouting_limit'):
        IrHttp.rerouting_limit = REROUTING_LIMIT

    chain_method(IrHttp, '_slug', classmethod(_slug))
    chain_method(IrHttp, '_unslug', classmethod(_unslug))
    chain_method(IrHttp, '_unslug_url', classmethod(_unslug_url))
    chain_method(IrHttp, '_get_converters', classmethod(_get_converters),
                 combine=merge_dict)
    chain_method(IrHttp, '_get_default_lang', classmethod(_get_default_lang))
    chain_method(IrHttp, 'get_nearest_lang', classmethod(get_nearest_lang))
    chain_method(IrHttp, '_get_translation_frontend_modules_domain',
                 classmethod(_get_translation_frontend_modules_domain))
    chain_method(IrHttp, '_get_translation_frontend_modules_name',
                 classmethod(_get_translation_frontend_modules_name))
    chain_method(IrHttp, '_view_declares_frontend', classmethod(_view_declares_frontend))
    chain_method(IrHttp, '_view_declares_multilang', classmethod(_view_declares_multilang))
    chain_method(IrHttp, 'url_rewrite', classmethod(url_rewrite))
    chain_method(IrHttp, '_is_multilang_url', classmethod(_is_multilang_url))
    chain_method(IrHttp, '_url_lang', classmethod(_url_lang))
    chain_method(IrHttp, '_url_for', classmethod(_url_for))
    chain_method(IrHttp, '_url_localized', classmethod(_url_localized))
    chain_method(IrHttp, '_match', classmethod(_match))
    chain_method(IrHttp, '_lang_redirect', classmethod(_lang_redirect))
    chain_method(IrHttp, '_pre_dispatch', classmethod(_pre_dispatch))
    chain_method(IrHttp, '_frontend_pre_dispatch', classmethod(_frontend_pre_dispatch))


class FrontendLangMiddleware:
    """El despacho que invoca ``_match``/``_pre_dispatch`` en este stack.

    **NO está en ``MIDDLEWARE``** y no debe añadirse desde este pase: cambia el
    enrutado de TODA petición del proyecto. Es decisión del ejecutor —
    tarea **#276**. Vive en este archivo por el mismo criterio con que
    ``UtmCookieMiddleware`` vive en el ``ir_http.py`` de ``utm`` y
    ``CompanyContextMiddleware`` en el de ``base``: el mecanismo de petición
    acompaña al ``ir.http`` que lo define.

    Sitio previsto cuando se cablee: **después** de
    ``CompanyContextMiddleware`` (necesita ``request.is_frontend`` y la
    petición en ambiente) y antes de cualquier middleware que emita cookies.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        redirect, path = IrHttp._match(request.path)
        if redirect is not None:
            return self._apply_pending_cookie(request, redirect)
        if path != request.path:
            # ≙ ``request.reroute(path_no_lang)``.
            request.path = path
            request.path_info = path
        response = self.get_response(request)
        return self._apply_pending_cookie(request, response)

    def process_view(self, request, view_func, view_args, view_kwargs):
        """≙ el punto ``_match`` → ``_pre_dispatch`` de la fuente.

        Devolver una respuesta aquí corta el despacho, que es lo que la fuente
        consigue con ``werkzeug.exceptions.abort(redirect)``.
        """
        return IrHttp._pre_dispatch(request.resolver_match, view_kwargs)

    @staticmethod
    def _apply_pending_cookie(request, response):
        """Vuelca la cookie que ``_frontend_pre_dispatch`` dejó pendiente."""
        pending = getattr(request, '_frontend_lang_cookie', None)
        if pending is not None:
            response.set_cookie(*pending)
        return response
