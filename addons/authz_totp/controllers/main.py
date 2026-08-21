"""Vistas — addons.authz_totp (gestión del 2FA del usuario autenticado).

Endpoints ``/api/v2/authz/totp/`` (nunca ``{user_id}`` — el 2FA es del propio
usuario). **Function-based views** (``@api_view`` + ``@require_capability``):
son acciones de un solo verbo (setup/confirm/disable/status/regenerar), donde el
boilerplate de una clase por método no aporta (convención de vistas de acción
única, ver ``CLAUDE.md`` de api). Se gobiernan por la capacidad de cuenta propia
``account.security`` (DEC-ENF-01: sembrada en TODOS los roles vía ``seed_authz``)
— NO ``IsAuthenticated`` a secas (que saltaría el modelo de capacidades).

El segundo paso del LOGIN es la excepción, y vive aquí también
=================================================================

``totp_login`` es ≙ ``auth_totp/controllers/home.py::web_totp``
(``/web/login/totp``, ``auth='public'``, GET+POST). Está en este archivo por el
mismo reparto que la referencia: el **corte** del login vive en el núcleo
(``odoo/http.py`` → aquí ``addons/web/controllers/session.py``) y consulta
``_mfa_url()`` sin conocer ningún método de 2FA; el **segundo paso** vive en el
addon del método, que sí lo conoce.

Es el único endpoint de este módulo que **no** lleva ``require_capability``, y
no por descuido: es **pre-auth**. La sesión está parcial —tiene ``pre_uid`` y
ningún usuario— así que no hay a quién consultarle una capacidad; el gate es la
presencia de ``pre_uid`` más el código. Mismo criterio que
``session_authenticate``, que es ``AllowAny`` por construcción. DEC-11 prohíbe
``IsAuthenticated`` **a secas** donde hay usuario; no obliga a exigir usuario
donde el login todavía no lo ha abierto.

Nuestro ``AllowAny`` **no** equivale entero a su ``auth='public'``
=================================================================

La redacción anterior cerraba con *"la referencia lo declara igual
(``auth='public'`` frente al ``auth='user'``)"*, y eso explicaba **la
referencia** en vez de declarar **nuestra diferencia** — el anti-patrón que
``porte-completo-no-parcial.md`` prohíbe por su nombre.

Allá ``auth=`` es un despachador, no una etiqueta: ``_authenticate`` lee
``endpoint.routing['auth']`` y resuelve ``_auth_method_<nivel>``
(``odoo19c: odoo/addons/base/models/ir_http.py:271-282``). Para ESTA ruta las
dos formas coinciden —``auth='public'`` y ``AllowAny`` dejan pasar al anónimo—
pero el nivel ``public`` hace algo más que dejar pasar: **sustituye el actor**.

.. code-block:: python

   def _auth_method_public(cls):                      # ``:265-269``
       if request.env.uid is None:
           public_user = request.env.ref('base.public_user')
           request.update_env(user=public_user.id)    # corre COMO usuario

Aquí no hay tal usuario —medido: 0 menciones de ``public_user`` en
``src/addons/base/``— así que ``AllowAny`` deja ``AnonymousUser``, que no es un
actor al que atar la capa de ACL. En el segundo paso del login **da igual**: la
vista resuelve al usuario por ``pre_uid`` y no consulta reglas de fila. Donde
sí importa es en la superficie pública de verdad, y ese hueco es la tarea
**#729** (hermana de **#133**, el row-scoping L1 aplicado a mano).

> **Corregido 2026-08-21 (Clausula 2, estado heredado).** Estas líneas decían
> que el gate del segundo factor en el login vivía en
> ``users.tokens.PYTokenObtainPairSerializer``. Medido:
> ``src/addons/base/controllers/schema.py:16`` declara que ese símbolo *"ya no
> existe en ``src/``"*, y el login real es
> ``addons/web/controllers/session.py::session_authenticate``. La afirmación
> llevaba apuntando a un símbolo inexistente.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model, login
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from addons.authz.permissions import require_capability
from addons.authz_totp.controllers.serializers import (
    TotpCodeSerializer, TotpDisableSerializer, TotpLoginSerializer,
)
from addons.authz_totp.models.auth_totp import (
    BROWSER_SCOPE, TRUSTED_DEVICE_COOKIE, AuthTotpDevice,
)
from addons.authz_totp.services import (
    begin_setup,
    confirm_setup,
    consume_recovery_code,
    count_recovery_codes,
    disable,
    generate_recovery_codes,
    totp_enabled,
    verify_code,
)
from addons.web.controllers.session import (
    PRE_BACKEND_KEY, PRE_LOGIN_KEY, PRE_UID_KEY, build_session_info,
)
from orm.environments import sudo, user_scope

_TAGS = ['authz-2fa']
_CAP = 'account.security'

# El ámbito de la clave del dispositivo (``BROWSER_SCOPE``) se declaró aquí
# hasta que apareció su tercer consumidor —el aviso de conexión nueva, en
# ``authz_totp_mail``—, que no puede importar un símbolo privado de una vista.
# Vive ahora junto a ``TRUSTED_DEVICE_COOKIE``, en el módulo del modelo.


def _finalize(request, user):
    """≙ ``request.session.finalize(env)`` (``odoo19c: odoo/http.py:1265-1271``).

    La fuente saca ``pre_login``/``pre_uid`` de la sesión y asigna ``uid``.
    Aquí lo segundo es ``login()``, que además cicla la clave de sesión — el
    ``should_rotate`` de la fuente (``:1293``).

    **El orden importa y no es intercambiable.** ``login()`` de Django preserva
    los datos de una sesión anónima al ciclar la clave, así que las dos claves
    parciales **sobreviven** si no se retiran antes. Una sesión ya abierta que
    conserve ``pre_uid`` volvería a entrar por la rama del segundo paso.
    """
    backend = request.session.get(PRE_BACKEND_KEY)
    request.session.pop(PRE_LOGIN_KEY, None)
    request.session.pop(PRE_UID_KEY, None)
    request.session.pop(PRE_BACKEND_KEY, None)
    login(request, user, backend=backend)


def _device_name(request):
    """El rótulo del dispositivo de confianza — ≙ ``name`` (``:62-68``).

    **Divergencia declarada, y son dos piezas ausentes, no una.** La fuente
    compone ``"%(browser)s on %(platform)s"`` a partir de
    ``request.httprequest.user_agent``, que es el analizador de agente de
    Werkzeug, y le añade ``" (ciudad, país)"`` cuando ``request.geoip`` resuelve
    la ciudad. Este stack no transporta ninguna de las dos: Django expone la
    cabecera ``User-Agent`` **en crudo** y no hay base GeoIP declarada.

    Se conserva el propósito —que el titular reconozca el navegador al listar
    sus dispositivos— con la cabecera recortada, y se declara el hueco en vez
    de inventar un analizador. Sin cabecera, el rótulo es genérico: la fuente
    también lo tolera (su ``user_agent.browser`` puede venir ``None``).
    """
    agent = request.META.get('HTTP_USER_AGENT', '').strip()
    return agent[:120] if agent else 'Navegador desconocido'


@extend_schema(
    tags=_TAGS,
    summary='Segundo paso del login (TOTP) — pre-auth',
    methods=['GET'],
    request=None,
    responses={
        200: OpenApiResponse(
            description='La cookie ``td_id`` era válida: sesión abierta.'),
        401: OpenApiResponse(
            description='NO_PARTIAL_SESSION · TRUSTED_DEVICE_REQUIRED'),
    },
    auth=[],
)
@extend_schema(
    tags=_TAGS,
    summary='Segundo paso del login (TOTP) — pre-auth',
    methods=['POST'],
    request=TotpLoginSerializer,
    responses={
        200: OpenApiResponse(description='Sesión abierta (cuerpo de sesión).'),
        400: OpenApiResponse(description='Código malformado'),
        401: OpenApiResponse(description='NO_PARTIAL_SESSION · TOTP_INVALID'),
    },
    auth=[],
)
@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def totp_login(request):
    """≙ ``auth_totp/controllers/home.py::web_totp`` (``/web/login/totp``).

    Es el **segundo paso** del login: consume la sesión parcial que
    ``session_authenticate`` dejó al responder 401 ``MFA_REQUIRED``.

    ``AllowAny`` es el gate correcto y no una omisión: la sesión no tiene
    usuario, así que no hay a quién consultarle una capacidad. Lo que autoriza
    es la presencia de ``pre_uid`` **más** el segundo factor. La fuente declara
    lo mismo con ``auth='public'``.

    **GET** — la vía del dispositivo recordado. Lee la cookie ``td_id`` y
    finaliza si la clave pertenece a ``pre_uid``. La fuente responde a un GET
    sin cookie válida **renderizando el formulario**; aquí no hay página que
    renderizar, así que devuelve 401 ``TRUSTED_DEVICE_REQUIRED``, que es la
    misma información para un cliente REST: *pide el código*.

    **POST** — el código. Acepta un TOTP de la app **o** un código de
    recuperación (divergencia declarada en ``TotpLoginSerializer``).

    Lo que la fuente hace aquí y este árbol todavía no: envolver la
    comprobación en ``user._assert_can_auth`` —el limitador de intentos—, que
    sigue sin portar (sucesor **#726**), y contar el paso del contador TOTP
    contra la repetición del mismo código (**#718**). Ninguno de los dos
    bloquea el cableado de la cookie, que es lo que esta vista cierra.
    """
    if request.user.is_authenticated:
        # ≙ `if request.session.uid: return redirect(...)` (`:24-25`) — el
        # segundo paso sobre una sesión ya abierta no tiene nada que hacer.
        return Response(build_session_info(request.user))

    pre_uid = request.session.get(PRE_UID_KEY)
    if not pre_uid:
        # ≙ `return request.redirect('/web/login')` (`:27-28`).
        return Response(
            {'codigo_error': 'NO_PARTIAL_SESSION',
             'detail': 'No hay un login a medias; empieza por la credencial.'},
            status=status.HTTP_401_UNAUTHORIZED)

    user = get_user_model().objects.filter(pk=pre_uid).first()
    if user is None:
        # La fuente hace `browse()`, que ante un id muerto da un recordset
        # vacío y cae al render del formulario. Aquí la sesión parcial apunta a
        # un usuario que ya no existe: se retira para no dejarla girando.
        request.session.pop(PRE_LOGIN_KEY, None)
        request.session.pop(PRE_UID_KEY, None)
        request.session.pop(PRE_BACKEND_KEY, None)
        return Response(
            {'codigo_error': 'NO_PARTIAL_SESSION',
             'detail': 'No hay un login a medias; empieza por la credencial.'},
            status=status.HTTP_401_UNAUTHORIZED)

    if request.method == 'GET':
        # ≙ `:31-40` — la rama del dispositivo de confianza.
        key = request.COOKIES.get(TRUSTED_DEVICE_COOKIE)
        if key and AuthTotpDevice._check_credentials_for_uid(
                scope=BROWSER_SCOPE, key=key, uid=user.pk):
            _finalize(request, user)
            return Response(build_session_info(user))
        return Response(
            {'codigo_error': 'TRUSTED_DEVICE_REQUIRED',
             'detail': 'Este navegador no está recordado; envía el código.'},
            status=status.HTTP_401_UNAUTHORIZED)

    serializer = TotpLoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    code = serializer.validated_data['code']
    if not (verify_code(user, code) or consume_recovery_code(user, code)):
        # ≙ `except AccessDenied` (`:51-52`) — un solo desenlace para el código
        # errado y el de recuperación gastado, por la misma razón que
        # `session_authenticate` no separa credencial de cuenta inexistente.
        return Response(
            {'codigo_error': 'TOTP_INVALID',
             'detail': 'Código de verificación inválido.'},
            status=status.HTTP_401_UNAUTHORIZED)

    _finalize(request, user)
    response = Response(build_session_info(user))

    if serializer.validated_data['remember']:
        # ≙ `:59-81`. `_generate` exige las DOS cosas: un usuario en contexto
        # —resuelve el dueño con `get_current_user()`— y privilegio, porque
        # `_check_expiration_date` tope la caducidad al máximo del grupo, que
        # por defecto es 1.0 día. Sin `sudo()` los 90 días se rechazan. Es lo
        # que la fuente pide con `.sudo()._generate(...)`.
        age = AuthTotpDevice._get_trusted_device_age()
        with user_scope(user.pk), sudo():
            key = AuthTotpDevice._generate(
                BROWSER_SCOPE,
                _device_name(request),
                timezone.now() + timedelta(seconds=age),
            )
        response.set_cookie(
            TRUSTED_DEVICE_COOKIE, key,
            max_age=age, httponly=True, samesite='Lax',
        )

    return response


@extend_schema(
    tags=_TAGS,
    summary='Estado del 2FA del usuario',
    responses={200: OpenApiResponse(
        description='{enabled: bool, recovery_codes_remaining: int}')},
)
@api_view(['GET'])
@require_capability(_CAP)
def totp_status(request):
    """GET — ¿el usuario tiene 2FA TOTP activo? + códigos de recuperación
    restantes."""
    return Response({
        'enabled': totp_enabled(request.user),
        'recovery_codes_remaining': count_recovery_codes(request.user),
    })


@extend_schema(
    tags=_TAGS,
    summary='Iniciar alta de 2FA (secreto + otpauth URI)',
    request=None,
    responses={
        201: OpenApiResponse(description='{secret, otpauth_uri}'),
        409: OpenApiResponse(description='TOTP_ALREADY_ENABLED'),
    },
)
@api_view(['POST'])
@require_capability(_CAP)
def totp_setup(request):
    """POST — inicia el alta: devuelve el secreto + URI de aprovisionamiento
    (para el QR). Aún NO activa el 2FA (hay que confirmar un código)."""
    result = begin_setup(request.user)
    if result is None:
        return Response(
            {'codigo_error': 'TOTP_ALREADY_ENABLED',
             'detail': 'El 2FA ya está activo. Desactívalo antes de reconfigurar.'},
            status=409,
        )
    secret, uri = result
    return Response({'secret': secret, 'otpauth_uri': uri}, status=201)


@extend_schema(
    tags=_TAGS,
    summary='Confirmar y activar el 2FA',
    request=TotpCodeSerializer,
    responses={
        200: OpenApiResponse(description='{enabled: true, recovery_codes: [...]}'),
        400: OpenApiResponse(description='TOTP_INVALID / código malformado'),
    },
)
@api_view(['POST'])
@require_capability(_CAP)
def totp_confirm(request):
    """POST {code} — verifica el primer código y ACTIVA el 2FA."""
    serializer = TotpCodeSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    recovery_codes = confirm_setup(request.user, serializer.validated_data['code'])
    if recovery_codes is None:
        return Response(
            {'codigo_error': 'TOTP_INVALID',
             'detail': 'Código inválido o no hay un alta pendiente.'},
            status=400,
        )
    # Los códigos de recuperación se muestran UNA sola vez (como Odoo).
    return Response({'enabled': True, 'recovery_codes': recovery_codes}, status=200)


@extend_schema(
    tags=_TAGS,
    summary='Desactivar el 2FA',
    request=TotpDisableSerializer,
    responses={
        200: OpenApiResponse(description='{enabled: false}'),
        400: OpenApiResponse(description='TOTP_INVALID / código malformado'),
    },
)
@api_view(['POST'])
@require_capability(_CAP)
def totp_disable(request):
    """POST {code} — desactiva el 2FA con un código TOTP actual **o** un código
    de recuperación (para quien perdió el authenticator)."""
    serializer = TotpDisableSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    if not disable(request.user, serializer.validated_data['code']):
        return Response(
            {'codigo_error': 'TOTP_INVALID',
             'detail': 'Código inválido o el 2FA no está activo.'},
            status=400,
        )
    return Response({'enabled': False}, status=200)


@extend_schema(
    tags=_TAGS,
    summary='Regenerar códigos de recuperación',
    request=TotpCodeSerializer,
    responses={
        200: OpenApiResponse(description='{recovery_codes: [...]}'),
        400: OpenApiResponse(description='TOTP_INVALID / código malformado'),
        409: OpenApiResponse(description='TOTP_NOT_ENABLED'),
    },
)
@api_view(['POST'])
@require_capability(_CAP)
def totp_recovery_codes(request):
    """POST {code} — regenera los códigos de recuperación (invalida los
    anteriores). Requiere un código TOTP actual; sólo con 2FA activo."""
    if not totp_enabled(request.user):
        return Response(
            {'codigo_error': 'TOTP_NOT_ENABLED',
             'detail': 'El 2FA no está activo.'},
            status=409,
        )
    serializer = TotpCodeSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    if not verify_code(request.user, serializer.validated_data['code']):
        return Response(
            {'codigo_error': 'TOTP_INVALID',
             'detail': 'Código de verificación inválido.'},
            status=400,
        )
    codes = generate_recovery_codes(request.user)
    return Response({'recovery_codes': codes}, status=200)
