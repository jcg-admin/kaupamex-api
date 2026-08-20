"""``ir.http`` — el enrutado HTTP y sus utilidades de URL.

Adaptación de ``odoo/addons/base/models/ir_http.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 456 líneas). En la referencia este
modelo **es** la capa HTTP: construye el mapa de rutas de Werkzeug, autentica
cada petición según el ``auth`` declarado por el endpoint, despacha, y
post-procesa la respuesta.

Aquí el enrutado y el despacho los hace Django (URLconf + middleware + DRF), y
la autenticación está decidida y documentada: **sesión de servidor**
(ADR-018) más **capacidad** por vista (``HasCapability``, DEC-11). Así que lo
que se porta es la parte que **no** es enrutado: las utilidades de URL, que
son puro algoritmo y valen en cualquier stack.

``slugify`` — la diferencia con el de Django, que sí importa
===========================================================

Es la pieza con más valor del archivo, y **no la duplica** nada del árbol:
``grep -rn "def slugify\\|from django.utils.text import" src/`` → **0**
[PROVEN].

Django trae ``django.utils.text.slugify``, pero por defecto
(``allow_unicode=False``) **descarta todo lo que no sea ASCII**: un título en
chino se convierte en cadena vacía y una URL entera desaparece. El de la
referencia conserva esos caracteres —su propio docstring lo ejemplifica:
``^h☺e$#!l(%l}o 你好&`` → ``h-e-l-l-o-你好``— y en cambio **sí** despoja los
acentos latinos por descomposición NFKD, para que ``é`` dé ``e`` y no ``e-``.

Esa combinación —quitar marcas combinantes pero conservar los caracteres de
otras escrituras— es una decisión deliberada, no un descuido, y es la razón
de portarlo en vez de usar el de Django. Un catálogo con productos en
japonés o árabe con el de Django pierde el slug entero.

Detalles del algoritmo que se conservan y son fáciles de perder:

- **``[\\W_]+``**: el guion bajo se reemplaza junto con los no-alfanuméricos.
  ``\\W`` por sí solo **no** incluye ``_``, así que sin el ``_`` explícito un
  ``hola_mundo`` quedaría con guion bajo en la URL.
- **``strip('-')`` antes de ``lower()``**: quita los guiones de los bordes que
  dejó el reemplazo, para que ``^hola$`` no dé ``-hola-``.
- **Re-normalizar a NFC al final**: tras descomponer con NFKD hay que
  recomponer, o el slug queda con caracteres combinantes sueltos que se ven
  igual y comparan distinto.
- **``max_length`` se aplica al final**, sobre el slug ya construido, no sobre
  la entrada.

Y en modo ``path`` (una ruta con ``/``): cada segmento se convierte por
separado, los vacíos se descartan, y **si la ruta acaba en una extensión
web conocida, se preserva la extensión** — sin eso, ``estilos.css`` daría
``estilos-css`` y la ruta dejaría de servir el archivo.

Rareza heredada del modo ``path``, conservada a propósito
---------------------------------------------------------

La rama de la extensión hace ``res[-1] = _slugify_one(path_no_ext) + ext``,
donde ``path_no_ext`` sale de ``os.path.splitext(value)`` sobre el
``value`` **completo** — la ruta entera, no el último segmento. Resultado
medido: ``"Mis Estilos/Tema Claro.css"`` da
``"mis-estilos/mis-estilos-tema-claro.css"``, con el primer segmento
repetido dentro del último. [PROVEN]

Casi seguro es un defecto de la referencia. **Se conserva igual**, por el
criterio ya fijado en H-API-168: "más correcto" no basta para divergir; el
criterio es la **comparabilidad**. Arreglarlo aquí haría que la misma ruta
diera distinto de un lado y del otro sin que nadie lo hubiera decidido.
Queda anotado para que la divergencia, si se toma, sea explícita.

Qué NO se porta, con su medición
================================

- **Todo el enrutado y el despacho**: ``routing_map``,
  ``_generate_routing_rules``, ``_match``, ``_pre_dispatch``, ``_dispatch``,
  ``_post_dispatch``, ``_handle_error``, ``_serve_fallback``, ``_redirect``.
  Y con ellos los convertidores de Werkzeug (``ModelConverter``,
  ``ModelsConverter``, ``SignedIntConverter``) y las clases de optimización
  del compilado de rutas (``LazyCompiledBuilder``, ``FasterRule``). En este
  árbol eso es la URLconf de Django más el router de DRF.

  Excepción quirúrgica (tarea #546): de ``_match`` sí se porta **una** de sus
  responsabilidades — estampar ``request.is_frontend`` desde lo que el
  endpoint despachado declara. Vive en ``CompanyContextMiddleware`` (el
  default) y su ``process_view`` (el estampado); ver sus docstrings.
- **Los métodos de autenticación** (``_auth_method_user`` / ``_none`` /
  ``_public`` / ``_bearer``, ``_authenticate``, ``_authenticate_explicit``).
  Se conserva **el vocabulario** —los cuatro nombres, que es lo que un
  endpoint declara— pero no la implementación: la de este árbol es sesión de
  servidor (ADR-018) más capacidad (DEC-11), y montar un segundo camino de
  autenticación al lado del vigente es exactamente lo que no se debe hacer de
  rebote al portar un archivo.
- **``_geoip_resolve``**: delega en el resolutor de la petición de Odoo.
- **``_sanitize_cookies``**: en la referencia es un ``pass`` — un punto de
  extensión vacío para que otros módulos lo sobreescriban. Se porta como tal,
  con esa nota, en vez de omitirlo: su valor está en existir.
- **``RequestUID``**: marcador interno de su sistema de peticiones.
"""
import logging
import os
import re
import unicodedata
from contextvars import ContextVar

import models

from orm.environments import activate_companies, set_current_uid
from tools.logging_context import clear_correlation_id, new_correlation_id

_logger = logging.getLogger(__name__)

#: La petición en curso — el ``request`` global de la referencia
#: (``odoo19c: odoo/http.py``), que ``website.py`` consulta 30 veces para
#: resolver el sitio, la sesión y el ``Host``.
#:
#: Vive **aquí** y no en un ``src/http.py`` nuevo porque este archivo ya es el
#: hogar declarado del enlace petición→entorno en este árbol: es donde vive
#: ``CompanyContextMiddleware``, que hace el papel de ``ir.http._authenticate``.
#: Crear un ``src/http.py`` para una sola variable abriría una raíz espejada
#: entera —enrutado, despacho, sesiones— por un ContextVar.
#:
#: ``ContextVar`` y no un global, por la misma razón que los tres ejes del
#: entorno (``orm.environments``) — y con el modelo de concurrencia **medido**,
#: no supuesto. ``setup/gunicorn.conf.py`` declara **prefork síncrono**:
#: ``workers = 4`` y ``threads = 1`` por defecto, y su propio comentario prohíbe
#: pasar a un worker asíncrono sin ADR. Es decir, cada worker es un proceso que
#: atiende **una petición a la vez en el mismo hilo**, y ese hilo se reutiliza
#: para la petición siguiente.
#:
#: De ahí las dos mitades del mecanismo, que sin esa medición parecen
#: redundantes:
#:
#: - un **global** filtraría el sitio de una petición a la siguiente del mismo
#:   worker, porque el hilo es el mismo;
#: - el ``ContextVar`` no basta por sí solo: se limpia en el ``finally`` del
#:   middleware justo por eso. Sin ese ``finally``, el valor sobreviviría a la
#:   petición dentro del mismo worker.
#:
#: Con ``GUNICORN_THREADS > 1`` Gunicorn pasa a hilos y el ``ContextVar`` aísla
#: por hilo — el mecanismo vale igual en las dos configuraciones.
_current_request: ContextVar = ContextVar('current_request', default=None)


def get_current_request():
    """La petición en curso, o ``None`` fuera de una — ≙ el ``request`` global.

    Devolver ``None`` en vez de levantar es deliberado y es lo que hace la
    fuente: ``website.py`` escribe ``if request and …`` una y otra vez, porque
    el mismo código corre en una petición web y en un cron sin petición
    ninguna. Un acceso que reventara fuera de petición rompería el cron.
    """
    return _current_request.get()


def set_current_request(request):
    """Fija la petición en curso (o la limpia con ``None``)."""
    _current_request.set(request)

#: Extensiones cuyo tipo MIME sirve la web — verbatim de la fuente. En modo
#: ``path`` la extensión se preserva en vez de convertirse en parte del slug.
EXTENSION_TO_WEB_MIMETYPES = {
    '.css': 'text/css',
    '.less': 'text/less',
    '.scss': 'text/scss',
    '.js': 'text/javascript',
    '.xml': 'text/xml',
    '.csv': 'text/csv',
    '.html': 'text/html',
}

#: Los cuatro modos de autenticación que un endpoint puede declarar en la
#: referencia. Se conserva el **vocabulario**; la implementación de este árbol
#: es otra (ADR-018 + DEC-11). Ver el docstring del módulo.
AUTH_METHODS = ('user', 'public', 'none', 'bearer')

#: No-alfanuméricos **y** el guion bajo. Sin el ``_`` explícito, ``\W`` lo
#: dejaría pasar y el slug llevaría guion bajo.
_NON_WORD = re.compile(r'[\W_]+')


class IrHttp(models.Model):
    """``ir.http`` — utilidades de URL.

    Abstracto en la referencia y abstracto aquí. Del modelo original queda lo
    que no es enrutado; ver el docstring del módulo.
    """

    class Meta:
        abstract = True

    @classmethod
    def slugify_one(cls, value, max_length=None):
        """``_slugify_one`` — un texto a un segmento de URL.

        Conserva los caracteres de escrituras no latinas y despoja los
        acentos: ``^h☺e$#!l(%l}o 你好&`` → ``h-e-l-l-o-你好``, ``café`` →
        ``cafe``. Ver el docstring del módulo sobre por qué eso difiere del
        ``slugify`` de Django y por qué la diferencia importa.

        La referencia intenta primero ``python-slugify`` si está instalada;
        aquí no se intenta, porque no lo está y añadirla cambiaría el
        resultado según el entorno — que es peor que un resultado fijo.
        """
        decomposed = unicodedata.normalize('NFKD', value or '')
        # Quitar las marcas combinantes: 'é' pasa a 'e', no a 'e-'.
        cleaned = ''.join(
            char for char in decomposed
            if unicodedata.category(char) != 'Mn'
        )
        slug = _NON_WORD.sub('-', cleaned).strip('-').lower()
        slug = unicodedata.normalize('NFC', slug)
        return slug[:max_length] if max_length else slug

    @classmethod
    def slugify(cls, value, max_length=None, path=False):
        """``_slugify`` — un texto, o una ruta completa, a slug.

        En modo ``path`` cada segmento se convierte por separado, los vacíos
        se descartan, y si la ruta acaba en una extensión web conocida **la
        extensión se preserva**: sin eso ``estilos.css`` daría
        ``estilos-css`` y la ruta dejaría de servir el archivo.
        """
        if not path:
            return cls.slugify_one(value, max_length=max_length)

        segments = []
        for part in (value or '').split('/'):
            slug = cls.slugify_one(part, max_length=max_length)
            if slug:
                segments.append(slug)
        path_no_ext, ext = os.path.splitext(value or '')
        if ext in EXTENSION_TO_WEB_MIMETYPES and segments:
            segments[-1] = cls.slugify_one(path_no_ext) + ext
        return '/'.join(segments)

    @classmethod
    def slug(cls, value):
        """``_slug`` — el identificador de un registro para la URL.

        Acepta el registro o una tupla ``(id, nombre)``. En Odoo 19 devuelve
        **sólo el id**: el slug con nombre legible quedó en el módulo de sitio
        web, no en ``base``. Se porta lo que ``base`` hace.
        """
        if isinstance(value, tuple):
            return str(value[0])
        return str(getattr(value, 'pk', value))

    @classmethod
    def unslug(cls, value):
        """``_unslug`` — el inverso: ``(None, id)`` o ``(None, None)``.

        La forma del retorno se conserva aunque el primer elemento sea siempre
        ``None`` en ``base``: es el hueco del nombre del modelo, que el módulo
        de sitio web sí rellena. Devolver sólo el entero rompería a quien
        desempaqueta dos valores.
        """
        try:
            return None, int(value)
        except (TypeError, ValueError):
            return None, None

    @classmethod
    def sanitize_cookies(cls, cookies):
        """``_sanitize_cookies`` — punto de extensión, vacío por diseño.

        En la referencia es literalmente ``pass``. Se porta con esa nota
        porque su valor está en **existir**: es el sitio declarado donde otro
        módulo interviene las cookies salientes sin parchear el despacho.
        """
        return cookies

    @classmethod
    def _is_allowed_cookie(cls, cookie_type):
        """``_is_allowed_cookie`` — ¿esta clase de cookie está permitida?

        ≙ ``odoo19c: odoo/addons/base/models/ir_http.py:450-452``. En ``base``
        la política es mínima: la cookie requerida pasa siempre; las demás
        pasan mientras haya una petición que las transporte. Los módulos de
        sitio la restringen sobreescribiendo este método (el consentimiento
        vive en ``addons/website/models/ir_http.py``).

        Divergencia declarada: la fuente devuelve ``bool(request.env.user)``,
        que es verdadero siempre que hay petición — su usuario público es un
        registro real, nunca falsy. Aquí el mismo hecho se expresa como
        ``get_current_request() is not None``: fuera de una petición (cron,
        shell) no hay transporte de cookies y la respuesta es ``False``.
        """
        return True if cookie_type == 'required' else get_current_request() is not None


class CompanyContextMiddleware:
    """Ata la petición al canal del dato — el rol de ``ir.http._authenticate``.

    En la referencia ``ir.http`` autentica cada petición y deja el entorno
    (``env.company``/``env.companies``) listo para el despacho. Aquí Django
    autentica y este middleware fija el ``ContextVar`` de compañía
    (``orm.environments``, análogo de ``env.companies``) desde
    ``request.user.company_id``, y lo limpia al terminar (``finally``) para
    no filtrar contexto entre requests que comparten hilo (WSGI).

    Resolutor L1 = usuario→compañía (``ResUsers.company``). El resolutor
    subdominio→compañía (``dbfilter`` de la referencia) es una capa futura;
    cuando llegue, fijará el contexto ANTES por host y este middleware lo
    respetará. El operador cross-company queda con ``company=None`` → sin
    scope implícito; su acceso es explícito (canal de elevación,
    DEC-AISL-04).

    Ubicar DESPUÉS de ``AuthenticationMiddleware`` (necesita ``request.user``).

    ``is_frontend`` — la marca de petición de cara pública (tarea #546)
    ====================================================================

    En la referencia la marca la pone el **despacho**, no un prefijo de path:
    ``_match`` lee la metadata de routing del endpoint que resultó despachado
    y estampa ``request.is_frontend = routing.get('website', False)``
    (``odoo19c: addons/http_routing/models/ir_http.py:375`` y ``:473``). Es
    decir: el endpoint **declara** ser de sitio (``@route(..., website=True)``)
    y el despachador copia esa declaración a la petición. El valor por defecto
    es ``False`` (``odoo19c: addons/http_routing/__init__.py:11``).

    Aquí se conserva esa semántica con las dos piezas análogas de Django:

    - ``__call__`` estampa el **default** ``request.is_frontend = False``
      antes de despachar — el papel del ``_post_init_hook`` de la fuente.
    - ``process_view`` (hook que Django invoca justo tras resolver la URL y
      antes de la vista — el punto ``_match`` → ``_pre_dispatch`` de la
      fuente) lee la **declaración de la vista despachada**: un atributo
      ``is_frontend = True`` en la clase de la vista (o en la función, para
      FBV). Ese atributo es el análogo directo de ``website=True`` en el
      ``@route`` de la referencia: metadata declarada por el endpoint, no
      adivinada del path.

    Alternativa considerada y descartada: leer el ``namespace`` de la URL
    resuelta (``request.resolver_match.namespace``). Acoplaría la marca al
    nombre que cada addon eligió para su ``app_name`` — una convención de
    nombres, que es la misma clase de adivinanza que el prefijo de path. La
    declaración explícita en la vista es lo que la fuente hace.

    Divergencias declaradas frente a la fuente:

    - **404 sin vista → ``False``, no ``True``.** La fuente pone ``True`` en
      ``NotFound`` (``:478-479``) porque su frontend renderiza una página 404
      bonita con el sitio. Aquí el 404 lo responde DRF/Django en JSON y no hay
      render de sitio, así que el default conservador se mantiene.
    - **``is_frontend_multilang`` no se porta.** Su condición
      (``routing.get('multilang', routing['type'] == 'http')``, ``:376``)
      describe el reescritor de idioma-en-URL de la fuente, mecanismo que este
      árbol no tiene; portar el atributo sin su consumidor sería un nombre sin
      mecanismo. Se porta cuando llegue ese reescritor.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _view_declares_frontend(view_func):
        """¿La vista despachada se declara de cara pública?

        Lee el atributo ``is_frontend`` donde la declaración vive según el
        estilo de la vista — medido en los paquetes instalados, no de
        memoria: DRF ``as_view`` expone la clase como ``view.cls``
        (``rest_framework/views.py:140``); las CBV de Django la exponen como
        ``view.view_class`` (``django/views/generic/base.py:108``); una FBV
        lleva el atributo en la propia función.
        """
        view_owner = (
            getattr(view_func, 'cls', None)
            or getattr(view_func, 'view_class', None)
            or view_func
        )
        return bool(getattr(view_owner, 'is_frontend', False))

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Estampa ``request.is_frontend`` desde la vista despachada.

        ≙ ``ir.http._match`` copiando ``routing.get('website', False)`` a la
        petición (``odoo19c: addons/http_routing/models/ir_http.py:375``).
        Django invoca este hook tras resolver la URL y antes de llamar la
        vista, así que la decisión es del **despacho** — qué vista sirve la
        petición — nunca de un prefijo de path.

        Devuelve ``None`` siempre: este hook marca, no responde.
        """
        request.is_frontend = self._view_declares_frontend(view_func)
        return None

    def __call__(self, request):
        user = getattr(request, 'user', None)
        authenticated = user is not None and getattr(user, 'is_authenticated', False)
        permitted = ()
        if authenticated:
            # Permitido = compañía propia + la pertenencia N (``company_ids``
            # M2M, el reverso de ``res_company_users_rel``) — el
            # ``user.company_ids`` de la referencia, con la propia primero
            # (``env.company`` = la primera activada). El cómputo vive en
            # ``ResUsers._permitted_company_ids`` (≙ ``_get_company_ids``),
            # que filtra las compañías archivadas como hace la fuente.
            permitir = getattr(user, '_permitted_company_ids', None)
            if permitir is not None:
                permitted = permitir()
        # Los dos ejes del entorno que la referencia deja listos antes del
        # despacho: QUIÉN actúa (``env.uid``) y QUÉ compañías ve
        # (``env.companies``). Se fijan juntos porque llegan de la misma
        # petición, pero son ejes distintos: el actor no acota el dato.
        set_current_uid(user.pk if authenticated else None)
        activate_companies((), permitted)
        # La petición misma es el tercer dato que la referencia deja
        # disponible antes del despacho (su ``request`` global). Lo consume
        # todo lo que resuelve "en qué sitio estamos": ``Website._force``,
        # ``get_current_website`` y su cadena.
        set_current_request(request)
        # Default de la marca de cara pública — el papel del
        # ``_post_init_hook`` de la fuente (``odoo19c:
        # addons/http_routing/__init__.py:11``): toda petición nace backend;
        # ``process_view`` la promueve si la vista despachada lo declara.
        request.is_frontend = False
        try:
            return self.get_response(request)
        finally:
            activate_companies((), ())
            set_current_uid(None)
            set_current_request(None)


class CorrelationIdMiddleware:
    """Abre y cierra la correlación de la petición (DEC-LOG-07, DEC-AF-11).

    Es la mitad que **sobrevive** de ``RequestLogMiddleware``. Aquélla hacía
    dos trabajos en un solo objeto: abrir la correlación de la petición, y
    escribir una fila de ``RequestLog`` con su metadata de acceso. DEC-AF-11
    retiró ``RequestLog`` —su mitad de acceso es trabajo del ``access_log``
    del proxy inverso, no del ORM— y con ella se fueron ``_write_log`` y
    ``_client_ip``. La correlación no se va con ellos: es la columna que une
    ``ir.logging`` con ``BusinessEvent``, y tiene tres consumidores medidos.

    - ``tools.logging_handlers.DatabaseLogHandler:77`` — puebla
      ``IrLogging.correlation_id`` desde el contexto.
    - ``addons/observability/models/business_event.py:28`` — igual, para el
      evento de negocio.
    - ``addons/authz_audit/audit.py:31`` — lee el atributo de la petición,
      ``getattr(request, 'correlation_id', '')``.

    Vive en ``ir_http`` porque en la referencia ``ir.http`` **es** la capa de
    petición —autentica, despacha y post-procesa la respuesta— y aquí ya aloja
    a ``CompanyContextMiddleware`` por el mismo criterio.

    ``X-Correlation-Id`` — la mitad recuperable del acceso
    =====================================================

    La respuesta sale con el identificador en una cabecera. No es decoración:
    es la condición que DEC-AF-11 declara para que el log del proxy pueda
    unirse al de la aplicación (``%{X-Correlation-Id}o`` en un ``LogFormat``
    propio, cambio de vhost de la tarea **#55**). Sin emitirlo, el
    ``access_log`` y ``ir.logging`` quedan como dos registros sin llave común.

    Ubicar cerca del tope de ``MIDDLEWARE``: la correlación debe estar abierta
    antes de que cualquier capa de abajo emita un log.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cid = new_correlation_id()
        request.correlation_id = cid
        try:
            response = self.get_response(request)
            try:
                response['X-Correlation-Id'] = cid
            except Exception:
                # silent OK because DEC-LOG-04: una respuesta que no admita
                # cabeceras (streaming ya cerrado, doble asignacion) jamas
                # debe romper la peticion del usuario.
                pass
            return response
        finally:
            clear_correlation_id()
