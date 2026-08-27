"""Sesión del cliente — adaptación de ``odoo19c: addons/web/controllers/session.py``.

Siete de las ocho rutas de sesión de la referencia (todas salvo ``account``,
ver más abajo), adaptadas al contrato REST del producto. El mecanismo NO se
reimplementa: Django ya provee sesión de servidor, que es justo lo que
ADR-018 declara como autenticación por defecto.

Completado 2026-08-07 (H-API-373): ``check``/``modules``/``get_lang_list``
figuraban en esta tabla y en ``LangSerializer``/``IrModule``/``ResLang``
importados, pero **sin vista implementada** — un grep por substring
(``'authenticate' in texto``) los daba por portados porque ``authenticate``
aparece contenido dentro de ``session_authenticate``. Medido por AST
(``ast.FunctionDef``, no substring) sobre la clase ``Session`` de la
referencia (8 métodos) contra las funciones de este módulo: sólo 4 tenían
cuerpo real. Los tres quedan implementados abajo.

Correspondencia con la referencia (``odoo-tools@622ddc2a``)
===========================================================

===============================  ============================================
Referencia                       Aquí
===============================  ============================================
``/web/session/authenticate``    ``POST /api/v2/web/session/authenticate/``
``:31``, ``jsonrpc``,            ``AllowAny`` — el login es pre-auth
``auth="none"``
-------------------------------  --------------------------------------------
``/web/session/destroy``         ``POST /api/v2/web/session/destroy/``
``:84``, ``jsonrpc``,            ``IsAuthenticated``
``auth='user'``
-------------------------------  --------------------------------------------
``/web/session/logout``          ``POST /api/v2/web/session/logout/``
``:88``, ``http``, ``auth='none'``  ``AllowAny`` — idempotente
-------------------------------  --------------------------------------------
``/web/session/get_session_info``  ``GET /api/v2/web/session/``
``:25``, ``auth='user'``
-------------------------------  --------------------------------------------
``/web/session/check``           ``GET /api/v2/web/session/check/``
``:69``, ``jsonrpc``,            ``IsAuthenticated`` — no-op, valida sesión
``auth='user'``
-------------------------------  --------------------------------------------
``/web/session/modules``         ``GET /api/v2/web/session/modules/``
``:64``, ``jsonrpc``,            ``IsAuthenticated``
``auth='user'``
-------------------------------  --------------------------------------------
``/web/session/get_lang_list``   ``GET /api/v2/web/session/get_lang_list/``
``:57``, ``jsonrpc``,            ``AllowAny`` — catálogo público, sin dato
``auth="none"``                  sensible
===============================  ============================================

Cuatro divergencias declaradas
================================

1. **Sin parámetro ``db`` — bloqueado, NO inaplicable.** La referencia lo
   recibe y valida contra ``http.db_filter`` porque un servidor sirve N bases.

   Esta viñeta decía *"aquí la base es una y la fija el despliegue; aceptarlo
   sería superficie sin función"*, y las dos mitades eran falsas
   (:ref:`h-api-781`). **Este árbol también sirve N bases:** declara
   ``DATABASE_ROUTERS = ['orm.routers.CompanyDatabaseRouter']``
   (``src/config/settings/base.py:319``), puebla aliases ``company_<N>_db``
   con ``install_company_aliases`` (``:314``), sabe crearlas y migrarlas
   (``company_create`` / ``company_migrate_all``) y su cron las recorre con
   ``list_company_db_names``. Y el mecanismo de la referencia **está portado
   fielmente**: ``service.db.db_filter`` (``:145``, con ``%h``/``%d``,
   normalización de puerto y ``www.``), ``db_list_for_host`` (≙ ``db_list``)
   y ``db_monodb``, con sus pruebas en
   ``tests/unit/service/test_db_resolution.py``.

   Lo que falta es **otra cosa, y es lo que bloquea al parámetro**: nadie
   resuelve la base **por petición**. Medido sobre ``src/`` y ``addons/``,
   excluyendo ``service/db.py`` y los tests, ``db_list_for_host`` y
   ``db_monodb`` tienen **0 consumidores**; hoy la base la elige el router por
   app/modelo, no el host. Aceptar un ``db`` sin ese resolutor sería aceptar un
   valor que nada consume — que es un defecto distinto del que la viñeta
   afirmaba. Se repone cuando el resolutor exista. Sucesor: **#736**;
   iniciativa ``implementar-aislamiento-multi-db-per-company``.
2. **``logout`` no redirige.** La referencia devuelve un 303 a ``/odoo``
   porque su cliente es una página. El nuestro es un cliente REST: 204.
3. **``destroy`` y ``logout`` hacen lo mismo.** En la referencia difieren en
   el tipo de transporte (``jsonrpc`` vs ``http``) y en si conservan la base
   (``keep_db``); ninguna de las dos distinciones sobrevive aquí. Se conservan
   ambas rutas porque son contrato publicado de la referencia, no por aportar
   comportamientos distintos.
4. **``modules``/``get_lang_list`` resuelven contra modelos propios, no
   contra el registry ni el RPC dispatch de la referencia.** ``modules``
   consulta ``base.IrModule`` (``state='installed'``) en vez de
   ``request.env.registry._init_modules`` — el catálogo técnico de addons ya
   es un modelo de datos en este árbol (ver ``base/models/ir_module.py``).
   ``get_lang_list`` consulta ``base.ResLang`` (``active=True``) en vez de
   escanear los ``.po`` del árbol con ``scan_languages()`` — el catálogo de
   idiomas también es un modelo, no un directorio de traducciones.

Lo que esta adaptación NO porta
================================

``account`` (``:73``, ``jsonrpc``, ``auth='user'``). Arma la URL de OAuth
hacia ``https://accounts.odoo.com/oauth2/auth`` para enlazar la sesión con
una cuenta de Odoo Online — el hub de identidad de la SaaS de Odoo. Esta
plataforma no tiene (ni le corresponde tener) un "Kaupamex Online" al que
enlazar: es un mecanismo de la casa matriz de la referencia, no una laguna
del ORM que completar (regla 7, ``porte-completo-no-parcial.md`` — la
pregunta es "¿qué me impide construirlo?", y la respuesta aquí es que no hay
qué construir, no que el stack no alcance). ``authz_oauth`` (addon propio)
resuelve el problema adyacente pero distinto de *iniciar sesión* vía un
proveedor externo (Google, etc.) — no el de *enlazar* la sesión ya abierta a
un backend SaaS ajeno. Divergencia de mecanismo declarada (desenlace 1 de
``porte-completo-no-parcial.md``), no omisión silenciosa.

El segundo factor — la sesión PARCIAL
======================================

La referencia difiere la finalización de la sesión cuando ``user._mfa_url()``
devuelve algo (``odoo19c: odoo/http.py:1250-1258``)::

    self.uid = None
    self['pre_login'] = credential['login']
    self['pre_uid'] = pre_uid
    # if 2FA is disabled we finalize immediately
    if auth_info.get('mfa') == 'skip' or not user._mfa_url():
        self.finalize(env)

Eso se porta verbatim en ``session_authenticate``: con segundo factor activo la
sesión queda **parcial** —dos claves y ningún ``login()``— y quien la cierra es
el segundo paso, que vive en el addon del método (``authz_totp``), no aquí.

**Por qué el corte vive en ``web`` y el segundo paso no.** Es el reparto de la
referencia: el corte está en ``odoo/http.py``, su núcleo, y consulta
``_mfa_url()`` sin importar ningún addon de 2FA; el segundo paso está en
``auth_totp/controllers/home.py``, que sí conoce el mecanismo. Aquí
``_mfa_url()`` lo declara ``base`` (``res_users.py:714``, el eslabón que
devuelve ``None``), así que este módulo no gana dependencia alguna: pregunta
por la cadena y no sabe quién la contesta.

Por la **misma** cadena sale el aviso de dispositivo nuevo
(``_notify_security_new_connection``, ≙ ``auth_totp_mail``): son dos llamadas
seguidas a dos eslabones vacíos de ``base``, y ninguna de las dos le dice a
este módulo qué addon está detrás.

Divergencia de forma, no de mecanismo: la referencia **redirige** (303) a
``_mfa_url()`` porque su cliente es una página. El nuestro es un cliente REST,
así que devuelve **401** con ``codigo_error: MFA_REQUIRED`` y la url en el
cuerpo. El 401 es el código correcto y no el 403: la credencial se aceptó pero
la sesión **no** está abierta — que es exactamente lo que ``self.uid = None``
declara. Contrastar con ``CHECK_IDENTITY_REQUIRED`` de ``authz_timeout``, que
sí es 403 porque ahí la sesión existe y sólo hay que reconfirmarla.
"""
from django.contrib.auth import login, logout
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from addons.authz.services import is_superadmin
from addons.base.models import IrModule, ResLang, ResUsers
from addons.web.controllers.serializers import (
    CredentialSerializer, LangSerializer, SessionInfoSerializer,
)
from exceptions import AccessDenied

_MODULES_RESPONSE = OpenApiResponse(description='["addon_a", "addon_b", ...]')

#: Claves de la sesión **parcial** — ≙ ``pre_login``/``pre_uid`` de
#: ``odoo19c: odoo/http.py:1252-1253``. Se conservan sus nombres porque son el
#: contrato entre el corte (aquí) y el segundo paso (el addon del método), que
#: en la referencia son dos archivos igual de distantes.
PRE_LOGIN_KEY = 'pre_login'
PRE_UID_KEY = 'pre_uid'

#: Tercera clave, **sin contraparte en la referencia**, y la razón es del
#: stack: allá `finalize()` sólo asigna `uid` porque no hay backends
#: enchufables. Aquí `login()` exige saber **qué** backend autenticó, y el
#: segundo paso ya no lo tiene: recupera al usuario del ORM, no de
#: `authenticate()`, que es quien deja `user.backend` puesto.
#:
#: Hardcodear `ModelBackend` sería un fallo silencioso para el resto: los
#: cuatro backends declarados (`AUTHENTICATION_BACKENDS`) incluyen LDAP, y un
#: usuario de LDAP quedaría marcado como autenticado por contraseña local.
#: Así que el primer paso anota cuál fue, y el segundo lo reusa.
PRE_BACKEND_KEY = 'pre_backend'


#: Extensiones del cuerpo de sesión — ≙ la cadena de ``super()`` que la
#: referencia obtiene con ``_inherit = "ir.http"`` sobre ``session_info()``.
#:
#: Allá cada addon que quiera añadir una clave declara su propio
#: ``session_info()`` y llama a ``super()``; el ORM compone la cadena por
#: herencia. Aquí el productor es una **función de módulo**, no un método de
#: modelo, así que no hay MRO donde encadenar: la lista lo sustituye, y el
#: orden de registro cumple el papel del orden de herencia.
#:
#: Cada elemento recibe ``(user, cuerpo)`` y devuelve el cuerpo — la misma
#: firma de ida y vuelta que tiene un ``super()`` de la fuente. Registrar es
#: cosa del ``ready()`` del addon que extiende, no de este módulo: ``web`` no
#: conoce a sus extensores, igual que ``ir.http`` no conoce quién lo hereda.
_SESSION_INFO_EXTENSIONS = []


def register_session_info_extension(extension):
    """Añade un extensor al cuerpo de sesión — ≙ heredar de ``ir.http``.

    Idempotente: un ``ready()`` que se ejecute dos veces —lo hace en algunas
    configuraciones de Django— no debe duplicar la clave ni el trabajo.
    """
    if extension not in _SESSION_INFO_EXTENSIONS:
        _SESSION_INFO_EXTENSIONS.append(extension)
    return extension


def build_session_info(user):
    """≙ ``ir.http.session_info()`` de la referencia, recortado a lo publicado.

    La referencia devuelve además la versión del servidor, los módulos
    instalados y la configuración del cliente web. Nada de eso tiene consumidor
    en un cliente REST, así que no se emite.

    **Es público, y el nombre no es el de la referencia a propósito.** Allá el
    símbolo es ``session_info()`` sobre ``ir.http`` —público— pero aquí ese
    nombre ya lo ocupa la **vista** de más abajo, así que el productor del
    cuerpo se llama distinto para no colisionar. Se publica porque el segundo
    paso del login (``authz_totp``) cierra la sesión parcial y tiene que
    devolver **este mismo cuerpo**: quien recibió el 401 ``MFA_REQUIRED`` está
    a mitad del flujo de ``session_authenticate`` y espera su respuesta.
    """
    # ``partner`` es obligatorio en el modelo (la referencia no admite usuario
    # sin partner), así que no se guarda contra su ausencia.
    #
    # ``is_system`` sale de ``is_superadmin``, no de un flag del modelo: aquí
    # el acceso administrativo es una CAPACIDAD (DEC-11) y ``ResUsers`` no
    # declara ``is_superuser``/``is_staff``. En la referencia el equivalente es
    # ``user._is_system()`` (pertenencia a ``base.group_system``) —también una
    # pertenencia, no una columna—, así que la correspondencia es directa.
    cuerpo = {
        'uid': user.pk,
        'login': user.login,
        'name': user.partner.name,
        'is_system': is_superadmin(user),
    }
    # ≙ el tramo de `super()` que cada addon heredero añade sobre el cuerpo
    # base. Sin esto, un addon que declare su extensión la deja sin llamador:
    # el símbolo existe, nunca corre, y nada lo delata.
    for extension in _SESSION_INFO_EXTENSIONS:
        cuerpo = extension(user, cuerpo)
    return cuerpo


@extend_schema(
    tags=['web'],
    summary='Abrir sesión con credencial',
    request=CredentialSerializer,
    responses={
        200: SessionInfoSerializer,
        400: OpenApiResponse(description='CREDENTIAL_REQUIRED'),
        401: OpenApiResponse(
            description='INVALID_CREDENTIAL · MFA_REQUIRED (con ``mfa_url``)'),
    },
    auth=[],
)
@api_view(['POST'])
@permission_classes([AllowAny])
def session_authenticate(request):
    """≙ ``/web/session/authenticate`` — pre-auth.

    ``login()`` de Django cicla la clave de sesión, que es lo que la referencia
    pide con ``should_rotate`` (``odoo19c: odoo/http.py:1293``): una sesión
    abierta nunca reusa el identificador de la anónima previa.

    Con segundo factor activo la sesión queda **parcial** y ``login()`` no se
    llama — ver "El segundo factor" en la cabecera del módulo.
    """
    serializer = CredentialSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'codigo_error': 'CREDENTIAL_REQUIRED',
             'detail': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST)

    # ≙ `odoo19c: odoo/http.py:1240` — el endpoint llama a
    # `res.users.authenticate`, no a la verificación de credencial a secas. La
    # diferencia importa: `_login` es quien envuelve el intento con el
    # limitador de acceso (`_assert_can_auth`) y quien registra el acceso en
    # `res.users.log`. Llamar a `authenticate()` de Django directamente —como
    # se hacía hasta este pase— saltaba las dos cosas.
    try:
        auth_info = ResUsers.authenticate(
            {'type': 'password',
             'login': serializer.validated_data['login'],
             'password': serializer.validated_data['password']},
            {'interactive': True,
             'base_location': request.build_absolute_uri('/').rstrip('/')},
        )
    except AccessDenied as exc:
        # Un solo código para credencial errónea, cuenta inexistente y origen
        # en enfriamiento: separar los casos revelaría qué logins existen. El
        # detalle del limitador sí viaja, porque le dice al cliente que espere
        # en vez de reintentar.
        return Response(
            {'codigo_error': 'INVALID_CREDENTIAL',
             'detail': str(exc) or 'Credencial inválida.'},
            status=status.HTTP_401_UNAUTHORIZED)

    user = auth_info['user']

    # ≙ `auth_totp_mail/models/res_users.py:44-48` — el aviso de conexión desde
    # un dispositivo nuevo. La fuente lo cuelga de `authenticate`, así que sale
    # **aquí**, con la credencial ya aceptada y ANTES de que el segundo factor
    # responda: quien tiene la contraseña y no el segundo factor también lo
    # dispara, que es de quien protege al titular. Tercer eslabón de la misma
    # cadena vacía que `_mfa_url`; este módulo tampoco sabe quién lo contesta.
    user._notify_security_new_connection(request)

    # ≙ `odoo/http.py:1250-1258` — la sesión queda parcial mientras el segundo
    # factor no responda. `_mfa_url()` es la cadena que `base` declara vacía y
    # cada addon de 2FA extiende; este módulo la consulta sin conocer a ninguno.
    mfa_url = user._mfa_url()
    if mfa_url is not None:
        request.session[PRE_LOGIN_KEY] = user.login
        request.session[PRE_UID_KEY] = user.pk
        request.session[PRE_BACKEND_KEY] = getattr(user, 'backend', None)
        return Response(
            {'codigo_error': 'MFA_REQUIRED',
             'detail': 'Se requiere el segundo factor.',
             'mfa_url': mfa_url},
            status=status.HTTP_401_UNAUTHORIZED)

    login(request, user)
    return Response(build_session_info(user))


@extend_schema(
    tags=['web'],
    summary='Ver la sesión activa',
    responses={200: SessionInfoSerializer},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def session_info(request):
    """≙ ``/web/session/get_session_info``."""
    return Response(build_session_info(request.user))


@extend_schema(
    tags=['web'],
    summary='Cerrar la sesión activa',
    request=None,
    responses={204: OpenApiResponse(description='Sesión cerrada')},
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def session_destroy(request):
    """≙ ``/web/session/destroy`` — exige sesión, como la referencia."""
    logout(request)
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=['web'],
    summary='Cerrar sesión (idempotente)',
    request=None,
    responses={204: OpenApiResponse(description='Sin sesión activa')},
    auth=[],
)
@api_view(['POST'])
@permission_classes([AllowAny])
def session_logout(request):
    """≙ ``/web/session/logout`` — ``auth='none'`` en la referencia.

    Sin sesión activa devuelve 204 igual: cerrar lo que ya está cerrado no es
    un error, y exigir sesión daría un 401 que le dice al cliente que su
    sesión caducó justo cuando quiere deshacerse de ella.
    """
    logout(request)
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=['web'],
    summary='Validar la sesión activa (no-op)',
    request=None,
    responses={204: OpenApiResponse(description='Sesión válida')},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def session_check(request):
    """≙ ``/web/session/check`` — la referencia también es un no-op
    (``return  # ir.http@_authenticate does the job``). Aquí
    ``permission_classes([IsAuthenticated])`` ES ese chequeo: si la sesión no
    es válida, DRF corta antes de llegar al cuerpo de la vista.
    """
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=['web'],
    summary='Listar los addons instalados',
    responses={200: _MODULES_RESPONSE},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def session_modules(request):
    """≙ ``/web/session/modules``.

    La referencia lee ``request.env.registry._init_modules`` (el registry en
    memoria del proceso Odoo). Aquí el catálogo de addons instalados es un
    modelo de datos propio (``base.IrModule``, ``ir_module.py``), así que se
    consulta ahí en vez de un registry — mismo dato, otra fuente.
    """
    names = list(
        IrModule.objects
        .filter(state=IrModule.STATE_INSTALLED)
        .order_by('name')
        .values_list('name', flat=True)
    )
    return Response(names)


@extend_schema(
    tags=['web'],
    summary='Listar los idiomas activos',
    responses={200: LangSerializer(many=True)},
    auth=[],
)
@api_view(['GET'])
@permission_classes([AllowAny])
def session_get_lang_list(request):
    """≙ ``/web/session/get_lang_list``.

    La referencia escanea los ``.po`` del árbol (``scan_languages()``, vía
    ``dispatch_rpc('db', 'list_lang', [])``). Aquí el catálogo de idiomas
    activos es un modelo (``base.ResLang``), así que se consulta ahí — ver
    docstring de ``LangSerializer``.
    """
    langs = ResLang.objects.filter(active=True).order_by('name')
    return Response(LangSerializer(langs, many=True).data)
