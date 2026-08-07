"""Manifiesto PWA del cliente web — adaptación de
``odoo19c: addons/web/controllers/webmanifest.py``, licencia LGPL-3
(``web/__manifest__.py``, ``odoo-tools@622ddc2a``) — copia + adaptación con
atribución (DEC-KX-03).

Re-medido 2026-08-07 (H-API-378). Medición símbolo-por-símbolo
(``scripts/pendientes_cascara.py web``, AST — mismo criterio que
``porte-completo-no-parcial.md``) sobre la clase única ``WebManifest``:
**14** símbolos (la clase + 13 métodos). **9 portados**, **4 métodos +
la clase declarados ausentes** con razón — no hay recorte silencioso.

La versión anterior de este docstring declaraba 11 de 13 ausentes citando una
única causa raíz ("0 static/ en el árbol, sin shell que instalar"). Esa causa
raíz sigue siendo cierta para 4 métodos, pero **dos pases previos la
sobregeneralizaron a los 11 sin volver a medir cada uno por separado**
(H-API-378: 3.7 M de tokens, 0 símbolos escritos). Re-analizado hoy, **5** de
esos 11 sí tenían mecanismo nativo disponible una vez que se busca el dato
real en vez del asset de archivo que la referencia usa:

- el árbol de menú del backoffice (``base.IrUiMenu``, seedeado por
  ``authz/management/commands/seed_menu.py``) — mismo dato que
  ``_get_shortcuts`` necesita (una lista de apps con una URL de entrada),
  servido por otra fuente. Ya es el patrón establecido en este mismo addon:
  ``home.py`` cede ``web_load_menus`` a ``authz/controllers/main.py::MyMenuView``
  citando esta misma línea de la referencia (``home.py:97``) y delegando en
  ``IrUiMenu.objects.load_menus_tree()``;
- el logotipo de la compañía (``ResCompany.logo_web``, ya servido por
  ``binary.py::company_logo``) — el único asset de branding real que este
  backend expone, y suficiente para cubrir todos los puntos donde la
  referencia necesita "un ícono": el manifiesto principal, el manifiesto de
  app-acotada y el PNG con relleno de ``scoped_app_icon_png``.

Portados (9) — con divergencia de fuente declarada, no de forma
====================================================================

===========================  ===================================================
Referencia                    Aquí
===========================  ===================================================
``_get_shortcuts``            ``_get_shortcuts(request)`` — ``base.IrUiMenu``
                               en vez de 4 módulos hardcoded + ``ir.model.data``
``_get_webmanifest``          ``_get_webmanifest(request)``
``webmanifest``                ``webmanifest(request)`` — ``GET
                               /api/v2/web/manifest.webmanifest``
``_icon_path``                 ``_icon_path(request)`` — URL de
                               ``company_logo``, no un PNG empacado
``_get_scoped_app_icons``      ``_get_scoped_app_icons(request, app_id)``
``_get_scoped_app_shortcuts``  ``_get_scoped_app_shortcuts(app_id)`` — idéntico
``_get_scoped_app_name``       ``_get_scoped_app_name(app_id)`` — vía
                               ``base.IrModule``, no ``modules.Manifest``
``scoped_app_manifest``        ``scoped_app_manifest(request)`` — ``GET
                               /api/v2/web/manifest.scoped_app_manifest``
``scoped_app_icon_png``        ``scoped_app_icon_png(request)`` — ``GET
                               /api/v2/web/scoped_app_icon_png``
===========================  ===================================================

Tres divergencias declaradas, comunes a los 9
================================================

1. **Función de módulo, no método de clase.** Ningún controlador de este
   addon usa ``http.Controller`` (0 clases en ``session.py``/``home.py``/
   ``binary.py``/``export.py``) — es el mecanismo de registro de rutas de
   Odoo, sin equivalente en Django/DRF. Cada método recibe ``request``
   explícito en vez de leerlo de ``self``/``request`` global.
2. **``scope``/``start_url`` fijos en ``/admin``, no ``/odoo``.** El
   manifiesto principal describe el *backoffice* — el árbol que sirve
   ``_get_shortcuts`` es ``base.IrUiMenu``, y sus rutas ya usan ese prefijo
   (``authz/management/commands/seed_menu.py``: ``/admin/products``,
   ``/admin/orders``, …).
3. **``unquote()`` no se re-aplica.** La referencia decodifica ``path``/
   ``app_name`` porque su framework HTTP no los decodifica automáticamente
   al leerlos de la query string armada por ``urlencode`` en ``scoped_app``
   (:73-84 más abajo). ``request.query_params`` de DRF (``QueryDict``) ya
   decodifica percent-encoding una vez al parsear — decodificar de nuevo
   corrompería un ``%25`` legítimo.

``_get_shortcuts`` — el árbol de menú admin como fuente
===========================================================

La referencia arma shortcuts para 4 módulos hardcoded (``mail``, ``crm``,
``project``, ``project_todo``) resolviendo su ``ir.ui.menu`` raíz vía
``ir.model.data`` (mapa *módulo instalado → id de registro XML*). Este árbol
no tiene ese mapa: el menú se siembra por **sección de dominio**
(``sec-catalogo``, ``sec-ventas``…), no por nombre de addon instalado.

Mismo dato — "una lista de apps con una URL de entrada al backoffice, podada
por lo que el usuario puede ver"—, otra fuente: las raíces visibles de
``base.IrUiMenu.objects.load_menus_tree()`` (idéntico mecanismo de podado por
capacidad que ``MyMenuView``, ``authz/controllers/main.py:73-81``). Una
sección (``sec-*``) no tiene ``route`` propio — es un contenedor
(``IrUiMenu.is_section``, ``base/models/ir_ui_menu.py:356-359``) —, así que
el shortcut usa el primer hijo directo con ruta como destino y el nombre de
la sección como etiqueta. Sin sesión resoluble (usuario anónimo), ``[]`` —
mismo desenlace que la referencia ante ``AccessError``.

``_icon_path`` / iconos — el logo de la compañía, no un PNG empacado
========================================================================

**0** directorios ``static/`` en los 78 addons de ``src/addons`` (medido hoy:
``find src/addons -maxdepth 2 -type d -iname static``) — sigue sin existir
el mecanismo de la referencia para resolver un ``odoo-icon-*.png`` propio.
Pero SÍ hay un asset de branding real y ya servido:
``binary.py::company_logo`` (``GET /api/v2/web/binary/company_logo/``), que
lee ``ResCompany.logo_web`` y **nunca** da 404 por campo vacío —
``IrBinary.get_image_response_from`` cae a un marcador de posición
(``base/models/ir_binary.py:230-237``). ``_icon_path(request)`` construye la
URL absoluta a ese endpoint para la compañía de la sesión; sin sesión
resoluble, ``None`` — y los tres consumidores (``_get_webmanifest``,
``_get_scoped_app_icons``, ``scoped_app_icon_png``) degradan a ``[]``/404 en
vez de referenciar una URL que no resolvería nada, cumpliendo la regla del
enunciado de esta tarea: *"un manifest que apunta a un icono inexistente es
un 404 silencioso"*.

``app_id`` no filtra el ícono en ``_get_scoped_app_icons``: sin almacén de
iconos por addon (``{app_id}/static/description/icon.svg``, **0** en el
árbol — mismo hallazgo), el resultado es siempre el *fallback* de
``_icon_path``, igual que en la referencia cuando el SVG del addon no existe
(``webmanifest.py:176-180`` de la referencia).

``scoped_app_icon_png`` — la rama ``add_padding`` SÍ se construye
======================================================================

La referencia usa ``odoo.tools.image.image_process(…, colorize=(255,255,255),
padding=16)`` — sin equivalente instalado (``image_mixin.py:38-50`` de este
mismo backend sólo hace ``thumbnail`` proporcional, sin relleno ni color de
fondo: ``Image.thumbnail((box, box), Image.LANCZOS)``, ningún parámetro de
padding/colorize). Pillow **sí** está disponible
(``pyproject.toml``: ``Pillow>=10.3.0``), así que, regla 7 de
``porte-completo-no-parcial.md`` ("si el stack no trae el mecanismo, se
construye"), el composicionado se escribe aquí mismo con PIL: miniatura
proporcional dentro de un lienzo de 180×180 con 16px de margen sobre fondo
blanco — la misma geometría que la referencia, sin depender de un helper que
no existe.

Cuatro ausentes, con razón medida hoy — no hay recorte silencioso
======================================================================

**1-2. ``service_worker`` / ``_get_service_worker_content`` (``:73-89`` de
la referencia).** El archivo que sirven (``web/static/src/service_worker.js``)
**sí existe en la referencia** (``odoo-tools:
addons/web/static/src/service_worker.js``, leído hoy) — se descarta su
contenido, no su existencia. La lógica cachea el *shell* renderizado por el
propio backend: intercepta navegaciones ``text/html``, extrae
``odoo.__session_info__`` embebido en el HTML sevido por Odoo
(``service_worker.js:21-24``) y sirve ese HTML cacheado offline. Esta API
nunca embebe sesión en HTML — el catch-all de producción
(``config/urls.py:215-236``, función ``serve_spa``) sirve el ``index.html``
**estático** que Webpack compiló vía ``FileResponse(open(index_path, 'rb'),
content_type='text/html')`` (``:236``), sin plantillado por request;
``extractSessionInfo`` no encontraría nada que extraer. Nota de corrección:
una medición previa de este mismo archivo declaraba el bloqueo por "origen
cruzado" (UI y API en dominios distintos); releído hoy el vhost de
producción (``server: config/apache/practicayoruba-https.conf:78``,
``ServerName %%DOMAIN%%`` — un solo ``VirtualHost``), **UI y API comparten
el mismo dominio** (Django montado en raíz vía ``WSGIScriptAlias /``,
``:199``, el mismo mecanismo que expone ``serve_spa`` en
``config/urls.py``) — el registro del *service worker* SÍ sería
same-origin. El bloqueo real no es de origen: es que el mecanismo de caché
de la referencia asume un *shell* server-renderizado que este backend no
tiene, y que la estrategia de cacheo del *bundle* de Webpack (hashes de
`chunk`, versión del build) es información que sólo el propio build de
``ui/`` conoce — no un dato que este backend pueda inventar. Construirla es
tooling de build (Workbox vía Webpack), trabajo de ``kaupamex-ui``, no de
este controlador.

**3. ``offline`` (``:94-99``).** Página de respaldo que el *service worker*
serviría sin red. Sin *service worker* funcional (punto 1-2), no hay quien
la invoque — mismo criterio de "sin consumidor real" que DEC-03 de
``ui-adaptacion-nativa`` ya aplica a componentes sin quien los use.

**4. ``scoped_app`` (``:101-117``).** La página HTML que renderiza el botón
"agregar a inicio" para una app acotada. **0** usos de
``django.shortcuts.render``/``TemplateResponse`` en todo ``src/addons``
(medido hoy) — ningún controlador de este backend, incluidos los que sí
sirven texto plano (``robots.txt``) o binarios, renderiza una página HTML
completa; los únicos ``.html`` del repo son plantillas de correo
transaccional (``src/core/templates/emails/``), otro subsistema. Sin
*service worker*, la instalabilidad "completa" (el criterio de Chrome exige
un *service worker* con `fetch` handler) tampoco se cumple — el manifiesto
que la sostendría (``scoped_app_manifest``) sí se construye abajo porque no
depende de esta página para ser válido por sí mismo.
"""
from io import BytesIO

from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from PIL import Image
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from addons.authz.services import is_superadmin, resolve_capabilities
from addons.base.models import IrModule, IrUiMenu, SystemParameter
from tools.misc import str2bool

_TAGS = ['web-manifest']

#: ≙ ``odoo-icon`` de la referencia — respaldo cuando la compañía no declara
#: ``primary_color`` (``base/models/res_company.py:273``). Mismo valor que
#: ``DEFAULT_PRIMARY_COLOR`` de ``models/base_document_layout.py:161`` de
#: este mismo addon; se repite en vez de importarse porque ese módulo no lo
#: expone en ``__all__`` — es un detalle de implementación de otro archivo.
_DEFAULT_THEME_COLOR = '#000000'

#: Lienzo del PNG con relleno de ``scoped_app_icon_png`` — ``webmanifest.py``
#: de la referencia (``:141``): ``size=(180, 180)``, ``padding=16``.
_PADDED_ICON_SIZE = 180
_PADDED_ICON_PADDING = 16


# === Helpers compartidos ======================================================

def _resolve_company(request):
    """La compañía de la sesión autenticada, o ``None``.

    Sin resolutor subdominio→compañía (``CompanyContextMiddleware`` ya
    declara ese vacío), no hay compañía que adivinar para un visitante
    anónimo — mismo criterio que ``binary.py::company_logo``.
    """
    if not getattr(request.user, 'is_authenticated', False):
        return None
    return getattr(request.user, 'company', None)


def _icon_path(request):
    """≙ referencia ``_icon_path`` (``:91-92``) — URL absoluta, no un path
    relativo a un PNG empacado (ver docstring del módulo, sección iconos).
    ``None`` si no hay compañía resoluble.
    """
    company = _resolve_company(request)
    if company is None:
        return None
    return request.build_absolute_uri(
        f"{reverse('web_v2:binary-company-logo')}?company={company.pk}")


def _default_icons(request):
    """El único ícono disponible en este árbol — ``[{src, sizes, type}]`` o
    ``[]`` sin compañía resoluble. Reutilizado por ``_get_webmanifest`` y
    ``_get_scoped_app_icons`` (ver docstring del módulo)."""
    src = _icon_path(request)
    if src is None:
        return []
    return [{'src': src, 'sizes': 'any', 'type': 'image/png'}]


# === Manifiesto principal (backoffice, scope /admin) =========================

def _get_shortcuts(request):
    """≙ referencia ``_get_shortcuts`` (``:16-41``) — ``base.IrUiMenu`` en
    vez de 4 módulos hardcoded (ver docstring del módulo)."""
    user = request.user
    if not getattr(user, 'is_authenticated', False):
        return []

    roots = IrUiMenu.objects.load_menus_tree(
        user,
        capabilities=resolve_capabilities(user),
        superadmin=is_superadmin(user),
    )
    shortcuts = []
    for root in roots:
        target = root if root.route else next(
            (child for child in getattr(root, '_visible_children', ())
             if child.route),
            None,
        )
        if target is None:
            continue
        shortcuts.append({
            'name': root.name,
            'url': target.route,
            'description': target.name,
        })
    return shortcuts


def _get_webmanifest(request):
    """≙ referencia ``_get_webmanifest`` (``:43-61``)."""
    company = _resolve_company(request)
    theme_color = (
        company.primary_color if company and company.primary_color
        else _DEFAULT_THEME_COLOR
    )
    return {
        'name': SystemParameter.get_param('web.web_app_name', default='Kaupamex'),
        'scope': '/admin',
        'start_url': '/admin',
        'display': 'standalone',
        'background_color': theme_color,
        'theme_color': theme_color,
        'prefer_related_applications': False,
        'icons': _default_icons(request),
        'shortcuts': _get_shortcuts(request),
    }


@extend_schema(
    tags=_TAGS,
    summary='Manifiesto PWA del backoffice',
    responses={200: OpenApiResponse(description='application/manifest+json')},
    auth=[],
)
@api_view(['GET'])
@permission_classes([AllowAny])
def webmanifest(request):
    """≙ ``/web/manifest.webmanifest`` (``:63-71``) — ``auth='public'`` en
    la referencia."""
    return JsonResponse(
        _get_webmanifest(request), content_type='application/manifest+json')


# === App acotada (scoped app) =================================================

def _get_scoped_app_name(app_id):
    """≙ referencia ``_get_scoped_app_name`` (``webmanifest.py:169-173``).

    Divergencia declarada: la referencia lee ``modules.Manifest.for_addon``
    (metadata del ``__manifest__.py`` en disco). Aquí el catálogo técnico de
    addons es un modelo de datos — ``base.IrModule`` (adaptación de
    ``ir.module.module``) —, así que se consulta ahí en vez del filesystem.
    Mismo contrato: nombre legible si existe, o el identificador crudo.
    """
    module = IrModule.objects.filter(name=app_id).first()
    if module is not None and module.shortdesc:
        return module.shortdesc
    return app_id


def _get_scoped_app_shortcuts(app_id):
    """≙ referencia ``_get_scoped_app_shortcuts`` (``webmanifest.py:166-167``).

    En la fuente es, verbatim, un punto de extensión sin lógica propia —
    ``return []`` — pensado para que otro addon lo sobrescriba. Se porta
    idéntico: no hay divergencia que declarar porque no hay mecanismo que
    adaptar.
    """
    return []


def _get_scoped_app_icons(request, app_id):
    """≙ referencia ``_get_scoped_app_icons`` (``:175-185``) — ``app_id`` no
    filtra nada (ver docstring del módulo, sección iconos): siempre el
    *fallback* de ``_default_icons``."""
    return _default_icons(request)


@extend_schema(
    tags=_TAGS,
    summary='Manifiesto PWA de una app acotada',
    parameters=[
        OpenApiParameter(name='app_id', type=str, required=True,
                          description='Nombre técnico del addon (base.IrModule.name).'),
        OpenApiParameter(name='path', type=str, required=False,
                          description="Ruta SPA a la que se acota el manifiesto; default '/'."),
        OpenApiParameter(name='app_name', type=str, required=False,
                          description='Nombre a mostrar; default el de _get_scoped_app_name.'),
    ],
    responses={
        200: OpenApiResponse(description='application/manifest+json'),
        400: OpenApiResponse(description='APP_ID_REQUIRED'),
    },
    auth=[],
)
@api_view(['GET'])
@permission_classes([AllowAny])
def scoped_app_manifest(request):
    """≙ ``/web/manifest.scoped_app_manifest`` (``:144-164``)."""
    app_id = request.query_params.get('app_id')
    if not app_id:
        return Response(
            {'codigo_error': 'APP_ID_REQUIRED', 'detail': 'app_id es obligatorio.'},
            status=status.HTTP_400_BAD_REQUEST)

    path = request.query_params.get('path') or '/'
    app_name = request.query_params.get('app_name') or _get_scoped_app_name(app_id)
    manifest = {
        'icons': _get_scoped_app_icons(request, app_id),
        'name': app_name,
        'scope': path,
        'start_url': path,
        'display': 'standalone',
        'background_color': _DEFAULT_THEME_COLOR,
        'theme_color': _DEFAULT_THEME_COLOR,
        'prefer_related_applications': False,
        'shortcuts': _get_scoped_app_shortcuts(app_id),
    }
    return JsonResponse(manifest, content_type='application/manifest+json')


def _padded_icon_png(file):
    """Miniatura de ``file`` centrada en un lienzo de 180×180 con 16px de
    margen sobre fondo blanco — ≙ ``image_process(…, colorize=(255,255,255),
    padding=16)`` de la referencia (ver docstring del módulo, sección
    ``scoped_app_icon_png``); construido con PIL porque
    ``image_mixin.py::_resize`` no soporta relleno ni color de fondo.
    """
    file.open('rb')
    source = Image.open(file)
    inner = _PADDED_ICON_SIZE - 2 * _PADDED_ICON_PADDING
    source.thumbnail((inner, inner), Image.LANCZOS)
    canvas = Image.new('RGB', (_PADDED_ICON_SIZE, _PADDED_ICON_SIZE), (255, 255, 255))
    offset = (
        (_PADDED_ICON_SIZE - source.width) // 2,
        (_PADDED_ICON_SIZE - source.height) // 2,
    )
    if source.mode == 'RGBA':
        canvas.paste(source, offset, source)
    else:
        canvas.paste(source.convert('RGB'), offset)
    buf = BytesIO()
    canvas.save(buf, format='PNG')
    return buf.getvalue()


@extend_schema(
    tags=_TAGS,
    summary='Ícono PNG de una app acotada (tamaño fijo, para Safari/iOS)',
    parameters=[
        OpenApiParameter(name='app_id', type=str, required=True),
        OpenApiParameter(name='add_padding', type=bool, required=False,
                          description='Compone un PNG de 180×180 con margen; '
                                      'sin él, redirige al ícono directo.'),
    ],
    responses={
        200: OpenApiResponse(description='image/png'),
        302: OpenApiResponse(description='Redirect al ícono directo'),
        400: OpenApiResponse(description='APP_ID_REQUIRED'),
        404: OpenApiResponse(description='Sin ícono resoluble (ver docstring)'),
    },
    auth=[],
)
@api_view(['GET'])
@permission_classes([AllowAny])
def scoped_app_icon_png(request):
    """≙ ``/scoped_app_icon_png`` (``:119-142``) — la rama SVG de la
    referencia no aplica (``_get_scoped_app_icons`` nunca devuelve
    ``image/svg+xml`` aquí); ver docstring del módulo, sección
    ``scoped_app_icon_png``, para la rama ``add_padding``."""
    app_id = request.query_params.get('app_id')
    if not app_id:
        return Response(
            {'codigo_error': 'APP_ID_REQUIRED', 'detail': 'app_id es obligatorio.'},
            status=status.HTTP_400_BAD_REQUEST)

    icons = _get_scoped_app_icons(request, app_id)
    if not icons:
        return Response(status=status.HTTP_404_NOT_FOUND)
    icon_src = icons[0]['src']

    if not str2bool(request.query_params.get('add_padding'), default=False):
        return HttpResponseRedirect(icon_src)

    company = _resolve_company(request)
    file = getattr(company, 'logo_web', None) if company is not None else None
    if not file or not getattr(file, 'name', ''):
        return HttpResponseRedirect(icon_src)

    # ``HttpResponse`` directo, no ``Response`` de DRF: el cuerpo es un PNG
    # crudo, no JSON — mismo patrón que ``home.py::robots`` y
    # ``binary.py::content_common`` (sale de la negociación de contenido).
    return HttpResponse(_padded_icon_png(file), content_type='image/png')
