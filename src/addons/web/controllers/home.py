"""Salud del servidor + robots.txt — adaptación de
``odoo19c: addons/web/controllers/home.py``, licencia LGPL-3.

Completado 2026-08-07 contra H-API-369 / DEC-FW-04 — el addon ``web`` era una
cáscara de solo ``session.py`` + ``export.py`` + ``webmanifest.py`` (sin
``home.py``).

Medición símbolo-por-símbolo (``re.findall(r'^\\s{4}def (\\w+)', ref)``, mismo
criterio que ``porte-completo-no-parcial.md``, sobre la clase única ``Home``):
**11** métodos. **3 portados** (``health``, ``robots``,
``_get_allowed_robots_routes``), **8 declarados ausentes** con razón — no hay
recorte silencioso.

Por qué 8 de 11 son ausentes — una sola causa raíz arquitectónica
====================================================================

La referencia es el controlador raíz del **cliente web renderizado por el
propio backend**: selector de base de datos, formulario de login servido como
página HTML (``web.login``, plantilla QWeb), bootstrap del shell JS
(``web.webclient_bootstrap``) y el redirect post-login que decide si el
usuario cae en ``/odoo`` (backend) o en ``/web/login_successful`` (portal).

Esta API **no sirve ningún shell**, por la misma causa raíz que
``webmanifest.py`` ya documentó y remidió aquí: **0** directorios ``static/``
en los 78 addons, **0** renderizado de página completa por plantilla, y el
frontend (``kaupamex-ui``) es una SPA React compilada aparte y servida por
Apache — no embebida ni renderizada por Django (``config/urls.py:199-242``,
``serve_spa``: catch-all que sirve ``UI_DIST/index.html`` para toda ruta que
no empiece por ``api/``/``admin/``/``static/``/``media/``). El enrutamiento
posterior al login —a qué pantalla cae el usuario— es trabajo del router de
React, no de una redirección HTTP del servidor.

Los 8 ausentes, agrupados por qué bloquea cada uno
====================================================

- ``index`` / ``_web_client_readonly`` / ``web_client`` — bootstrap del shell
  JS vía QWeb (``web.webclient_bootstrap``) + selector de base de datos
  (``ensure_db``, multi-db). Ningún consumidor: la SPA arranca desde
  ``ui/public/index.html`` servido por Apache, no desde una plantilla que
  Django renderiza. ``_web_client_readonly`` es sólo el kwarg ``readonly=``
  de la ruta de ``web_client``; sin la ruta, el helper no tiene función.
- ``web_login`` / ``login_successful_external_user`` — formulario de login
  HTML server-side (plantillas ``web.login`` / ``web.login_successful``,
  cabeceras CSP para iframe, listado de bases, CAPTCHA). **Superseded, no
  meramente ausente**: la mitad que sí aplica —validar credencial y abrir
  sesión— ya está servida como endpoint REST en
  ``POST /api/v2/web/session/authenticate/`` (``session.py::session_authenticate``,
  mismo mecanismo: ``authenticate()`` + ``login()`` de Django). La mitad de
  renderizado de página no tiene consumidor: el formulario de login es una
  ruta de React en ``ui/``, no una plantilla que este backend sirve.
- ``web_load_menus`` — **cubierto en otro addon, no duplicado aquí**
  (mismo principio que ``hallazgos-documentacion-obligatoria.md`` aplica a
  hallazgos transversales: vive donde se produjo, se cruza, no se copia).
  ``authz/controllers/main.py::MyMenuView`` (``GET /api/v2/authz/me/menu/``)
  cita **esta misma línea de la referencia** en su docstring
  (``"home.py:97 de la referencia sella la respuesta..."``) y delega el
  mecanismo —los dos filtros, la regla de ancestros, el caché por perfil— en
  ``base.IrUiMenu.objects.load_menus_tree()``, el equivalente exacto de
  ``ir.ui.menu.load_web_menus()``.
- ``_login_redirect`` — envuelve ``_get_login_redirect_url()`` de
  ``utils.py`` de la referencia, que a su vez depende de
  ``is_user_internal()`` y de ``_mfa_url()`` para decidir la URL de
  aterrizaje post-login. El **primitivo del que depende SÍ está portado**:
  ``ResUsers.is_internal()`` (``base/models/res_users.py:430``, docstring
  ``≙ _is_internal (res_users.py:1165-1167)``). Lo que falta es la
  orquestación HTTP de a dónde redirigir — trabajo del router de React, que
  ya recibe ``is_system``/``login``/``name`` de ``session_info()``
  (``session.py::_session_info``) para decidir la pantalla de aterrizaje.
- ``switch_to_admin`` — "convertirse en superusuario": eleva el ``uid`` de
  la sesión a ``SUPERUSER_ID`` para un usuario de ``base.group_system``,
  invalidando el caché de registro y rotando el token de sesión. **Este es
  el único de los 8 sin equivalente arquitectónico posible por adaptación
  directa** — el modelo de capacidades (DEC-11) no tiene la noción de una
  sesión con privilegio conmutable: ``is_superadmin(user)``
  (``authz/resolution.py``) es un chequeo de **pertenencia derivada**
  (rol), no un flag de sesión que se prende y apaga por request.
  **DESCONOCIDO — condición de cierre:** requiere una decisión de seguridad
  explícita (ADR) sobre si "convertirse en admin" debe existir en este
  producto y, si existe, cómo se audita (``authz_audit``); no es un
  mecanismo que se construya sin esa decisión previa, a diferencia de los
  demás ausentes de esta lista, que sí tienen forma nativa clara y
  simplemente no aplican aquí.

Portados (3) — infraestructura HTTP genérica, sin dependencia de shell
=========================================================================

Ninguno de los tres depende de QWeb, ``static/`` ni del selector de base de
datos; son infraestructura de servidor genérica que sí aplica a cualquier
backend HTTP, tenga o no shell propio.

Correspondencia con la referencia (``odoo-tools@622ddc2a``)
===========================================================

===================================  ==========================================
Referencia                            Aquí
===================================  ==========================================
``Home.health``                       ``health()`` — ``GET /api/v2/web/health/``
``Home.robots``                       ``robots()`` — ``GET /api/v2/web/robots.txt``
``Home._get_allowed_robots_routes``   ``_get_allowed_robots_routes()`` (idéntico nombre)
===================================  ==========================================

Dos divergencias declaradas en ``health()``
=============================================

1. **Servidor vs. base propia.** La referencia conecta a la base
   administrativa ``postgres`` (``odoo.sql_db.db_connect('postgres')``) para
   verificar que el **servidor** PostgreSQL responde, independientemente de
   si la base de la app está arriba. Este backend no tiene credenciales
   configuradas para una base ajena a la suya — verificar la conexión
   **propia** (``django.db.connection``) cubre el caso real que le importa a
   un balanceador/orquestador: "¿puede esta instancia de la API atender
   peticiones que tocan datos?". Documentado, no simulado.
2. **Excepción capturada.** La referencia captura ``psycopg2.Error``
   (driver v2). Este backend usa ``psycopg`` v3
   (``pyproject.toml``: ``psycopg[binary]>=3.2``); en vez de acoplar el
   healthcheck a un driver concreto, se captura ``django.db.Error`` — la
   clase base de Django para *cualquier* error de base de datos
   (``OperationalError``, ``InterfaceError``, …), portable si el backend
   cambia de driver.

``robots()`` — el mismo contenido, un techo de montaje declarado
====================================================================

El contenido (``User-agent: *`` / ``Disallow: /`` / ``Allow: <rutas>``) y
``_get_allowed_robots_routes()`` (punto de extensión, ``return []`` por
defecto, idéntico a la referencia) se portan sin cambios. La ruta queda
montada bajo el namespace propio del addon
(``/api/v2/web/robots.txt``, vía ``web/controllers/urls.py``) porque
``config/urls.py`` — donde viviría el montaje real en la raíz del sitio
(``/robots.txt``, la ubicación que un crawler espera) — es territorio
compartido de la fase de consolidación, no de este addon. Pendiente: un
``path('robots.txt', robots)`` en ``config/urls.py`` ANTES del catch-all de
la SPA (``serve_spa``, que si no se excluye serviría ``index.html`` en su
lugar).
"""
from django.db import Error as DatabaseError
from django.db import connection
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from addons.web.controllers.serializers import HealthCheckSerializer


def _get_allowed_robots_routes():
    """≙ referencia ``_get_allowed_robots_routes`` (``home.py:198-203``).

    Punto de extensión: devuelve las rutas que ``robots()`` permite además
    del ``Disallow: /`` general. En la fuente es un método pensado para que
    otro addon lo sobrescriba (herencia de controladores); aquí, sin ese
    mecanismo, es el punto donde otro addon reasignaría la función si algún
    día hace falta permitir una ruta pública indexable. Vacío por defecto,
    idéntico a la referencia — no hay divergencia que declarar.
    """
    return []


@extend_schema(
    tags=['web'],
    summary='Salud del servidor',
    parameters=[
        OpenApiParameter(
            name='db_server_status', type=bool, required=False,
            description='Si es verdadero, además verifica la conexión a la '
                        'base de datos propia (≙ conexión al servidor '
                        'PostgreSQL en la referencia).'),
    ],
    responses={
        200: HealthCheckSerializer,
        500: HealthCheckSerializer,
    },
    auth=[],
)
@api_view(['GET'])
@permission_classes([AllowAny])
def health(request):
    """≙ ``/web/health`` — ``auth='none'``, ``save_session=False`` en la
    referencia. Django no escribe cookie de sesión salvo que la vista toque
    ``request.session``, así que esta vista ya cumple esa intención sin
    necesitar un flag equivalente.
    """
    health_info = {'status': 'pass'}
    http_status = status.HTTP_200_OK

    if request.query_params.get('db_server_status'):
        try:
            connection.ensure_connection()
            health_info['db_server_status'] = True
        except DatabaseError:
            health_info['db_server_status'] = False
            health_info['status'] = 'fail'
            http_status = status.HTTP_500_INTERNAL_SERVER_ERROR

    return Response(
        health_info, status=http_status,
        headers={'Cache-Control': 'no-store'})


@extend_schema(
    tags=['web'],
    summary='robots.txt',
    responses={200: OpenApiResponse(description='text/plain')},
    auth=[],
)
@api_view(['GET'])
@permission_classes([AllowAny])
def robots(request):
    """≙ ``/robots.txt``.

    Devuelve ``HttpResponse`` (no ``Response`` de DRF) a propósito: el
    cuerpo es texto plano, no JSON — mismo patrón que ``ExportFormat.get()``
    en ``export.py:1013`` de este addon, que también sale de la negociación
    de contenido de DRF devolviendo un ``HttpResponse`` directo.
    """
    allowed_routes = _get_allowed_robots_routes()
    robots_content = ['User-agent: *', 'Disallow: /']
    robots_content.extend(f'Allow: {route}' for route in allowed_routes)

    return HttpResponse('\n'.join(robots_content), content_type='text/plain')
