"""La capa HTTP del candado por tiempo — quien lo consume en cada petición.

Adaptación de Odoo ``auth_timeout/models/ir_http.py``
(``odoo-tools@abe4040ec1``, ``odoo19c:``, LGPL-3, 245 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

``models/res_groups.py`` porta **dónde se configura** el umbral y
``models/res_users.py`` **cómo se resuelve** para un usuario. Este archivo
porta lo que faltaba: **quién lo mira**, en cada petición, y qué hace cuando
vence.

Porte símbolo por símbolo — 8 de 8 defs + la excepción
=======================================================

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - Símbolo (línea en la referencia)
     - Estado
   * - ``CheckIdentityException`` (``:9``)
     - portada en ``../exceptions.py`` como ``CheckIdentityRequired`` (403),
       con su hermana ``SessionLockExpired`` (401) para la rama ``logout``
   * - ``_must_check_identity`` (``:19``)
     - portado — el corazón: compara reloj contra los dos umbrales
   * - ``_check_identity`` (``:75``)
     - portado — el flujo de confirmación, con su segundo factor
   * - ``_set_session_inactivity`` (``:118``)
     - portado; **sin productor de presencia hoy** — ver la divergencia 3
   * - ``_authenticate`` (``:157``)
     - portado; lo invoca ``CheckIdentityMiddleware.process_view``
   * - ``_handle_error`` (``:184``)
     - portado; convierte la excepción en respuesta — ver la divergencia 2
   * - ``_session_info_common_auth_timeout`` (``:206``)
     - portado
   * - ``session_info`` (``:222``) · ``get_frontend_session_info`` (``:234``)
     - portados; su consumidor aquí es el endpoint de estado de este addon,
       no ``web`` — ver la divergencia 4

Divergencias declaradas
=======================

1. **``create_time`` lo estampa el login, no el almacén de sesión.** La
   fuente lo lee del almacén, que lo pone al **crear** la sesión. Django no
   registra esa marca: su ``SessionStore`` guarda un diccionario y nada más.
   Aquí lo estampa ``stamp_session_create_time``, recibiendo la señal
   ``user_logged_in``. El ancla se mueve de «sesión creada» a «sesión
   autenticada», que es la que el umbral absoluto quiere medir —una sesión
   anónima no tiene identidad que caducar—. El default de la fuente para esa
   clave es ``0``, que dispara el candado de inmediato; aquí es el mismo, así
   que una sesión sin la marca se trata como vencida, no como eterna.

2. **``_authenticate`` levanta y ``_handle_error`` responde, los dos dentro
   del middleware.** En la fuente son dos ganchos de su despachador: uno
   levanta durante el despacho y el otro atrapa más arriba. En Django el
   middleware está **por encima** del manejador de excepciones de DRF, así
   que una excepción levantada en ``process_view`` no llega a
   ``core.exception_handling`` y saldría como 500. Los dos símbolos se
   conservan con su nombre y su papel; lo que cambia es que el segundo lo
   llama el mismo middleware en vez de un despachador central.

   Y la rama de redirección de la fuente (``request.redirect_query`` a
   ``/auth-timeout/check-identity`` cuando ``routing_type == "http"``) **no
   se porta**: existe para su cliente de páginas, que necesita una URL a la
   que ir. Aquí todo cliente es REST y recibe el 403 con
   ``check_identity_url`` en el cuerpo — el mismo dato, sin la redirección.

3. **``_set_session_inactivity`` no tiene productor de presencia.** En la
   fuente lo llama ``ir_websocket``: el cliente avisa por WebSocket que el
   usuario está inactivo, o el socket se cierra. Este árbol no transporta
   presencia por WebSocket (DEC-AF-06), así que el método se porta y su
   llamador es hoy el endpoint de reporte de inactividad de este addon. El
   canal de WebSocket queda en la tarea **#715**.

4. **``session_info``/``get_frontend_session_info`` no extienden a ``web``.**
   La fuente los extiende por ``_inherit`` sobre ``ir.http``. Aquí el
   productor equivalente es ``web.controllers.session.build_session_info(user)``,
   una **función de módulo**: extenderla desde este addon exigiría que
   ``web`` conociera a ``authz_timeout``, invirtiendo la dependencia. Los dos
   símbolos se portan y su consumidor es ``GET /api/v2/authz/timeout/``, que
   es donde el cliente lee su ``lock_timeout_inactivity``. El registro de
   extensores que faltaba para encadenarlo como la fuente ya existe
   (``web.controllers.session.register_session_info_extension``), y
   ``AuthzTimeoutConfig.ready()`` inscribe ``session_info`` al arrancar.

5. **El webauthn SÍ es un método de confirmación**, y desde #722 su eslabón
   vive donde la referencia lo declara: ``authz_passkey/models/res_users.py``,
   colgado de la cadena. Acota la passkey al usuario ya autenticado y delega
   en ``verify_webauthn_credential``, cuyo verificador es el mismo
   ``PasskeyKey.verify_auth`` (≙ ``_verify_auth``) que usa el login.

   El ``auth_method`` que devuelve es ``passkey``, no ``webauthn``: la
   asimetría es de la fuente, que compara ``first_fa != auth["auth_method"]``
   (``:106``) y guarda ``credential["type"]`` (``:109``). Es inocua porque
   ``mfa='skip'`` impide que la rama que escribe ``identity-check-1fa`` llegue
   a correr para este método. Se reproduce verbatim (:ref:`h-api-779`).

6. **``_check_credential`` es un envoltorio de traducción, no un despachador**
   (#722). La fuente llama ``user._check_credentials(credential,
   {"interactive": True})`` y deja escapar ``AccessDenied``, que su
   despachador convierte en respuesta. Aquí ese método **sí existe** como
   cadena sobre ``res.users`` —``base`` atiende ``password`` y los tres
   addons de la familia cuelgan ``totp``, ``totp_mail`` y ``webauthn``— así
   que lo único que queda localmente es traducir la excepción al contrato de
   la vista: ``None`` es rechazo, y la vista lo sella como **401
   ``CHECK_IDENTITY_FAILED``**. ``AccessDenied`` es un ``UserError`` de la
   fachada, no una ``APIException``; dejarlo salir daría un 500.

   ``request`` viaja en ``env`` porque el eslabón de passkey lo necesita: el
   reto de WebAuthn vive en la sesión y ``PasskeyKey.verify_auth`` lo recibe
   explícito, donde la fuente lo lee de un hilo-local.
"""
import logging
import re
import time

from django.contrib.auth.signals import user_logged_in
from django.http import JsonResponse

from addons.authz_timeout.exceptions import (
    CheckIdentityRequired,
    SessionLockExpired,
)
from addons.web.controllers.session import register_session_info_extension
from exceptions import AccessDenied

_logger = logging.getLogger(__name__)

#: Claves de sesión — verbatim de la fuente, para que el vocabulario del
#: almacén sea el mismo que el de la referencia y un diagnóstico cruce.
SESSION_CREATE_TIME = 'create_time'          # ≙ ``:52``
SESSION_CHECK_NEXT = 'identity-check-next'   # ≙ ``:56``
SESSION_CHECK_1FA = 'identity-check-1fa'     # ≙ ``:70``
SESSION_CHECK_LAST = 'identity-check-last'   # ≙ ``:115``


def stamp_session_create_time(sender, request, user, **kwargs):
    """Estampa el ancla del umbral absoluto al autenticar — divergencia 1.

    Receptor de ``user_logged_in``. La fuente no necesita este símbolo porque
    su almacén de sesión pone ``create_time`` al crearla; Django no lo hace.
    """
    if request is not None and hasattr(request, 'session'):
        request.session[SESSION_CREATE_TIME] = time.time()


def _must_check_identity(request):
    """≙ ``_must_check_identity`` (``:19-73``).

    ¿La sesión de esta petición exige confirmar identidad? Compara el reloj
    contra los dos umbrales, cada uno con su ancla en la sesión:

    - ``lock_timeout`` contra ``create_time`` — duración absoluta.
    - ``lock_timeout_inactivity`` contra ``identity-check-next`` — inactividad.

    Devuelve ``None`` si no hay nada que hacer, o un diccionario con:

    - ``logout`` — hace falta cerrar sesión;
    - ``check_identity`` — hace falta confirmar identidad;
    - ``mfa`` — el umbral que venció exige segundo factor;
    - ``1fa`` — el método ya usado, para no admitirlo como segundo.
    """
    session = request.session
    user = request.user
    timeouts = user._get_lock_timeouts()
    inactivity = timeouts.get('lock_timeout_inactivity')
    # ≙ ``first_timeout`` (``:49``): sólo el umbral de inactividad MÁS CORTO
    # escribe ``identity-check-next``, así que uno más largo compara contra esa
    # misma marca y debe descontar la diferencia. No aplica a ``create_time``,
    # que se estampa una vez al abrir la sesión.
    first_inactivity = inactivity[0][0] if inactivity else 0
    ejes = (
        ('lock_timeout', 'logout', SESSION_CREATE_TIME, 0, 0),
        ('lock_timeout_inactivity', 'check_identity', SESSION_CHECK_NEXT,
         None, first_inactivity),
    )
    for timeout_type, reauth_type, session_key, key_default, first_timeout in ejes:
        for timeout, mfa in reversed(timeouts.get(timeout_type) or []):
            threshold = time.time() - timeout
            timestamp = session.get(session_key, key_default)
            if timestamp is not None and timestamp - first_timeout <= threshold:
                res = {reauth_type: True, 'mfa': mfa}
                if mfa:
                    first_fa = session.get(SESSION_CHECK_1FA)
                    if first_fa:
                        timestamp_1fa, auth_method_1fa = first_fa
                        if timestamp_1fa > threshold:
                            res['1fa'] = auth_method_1fa
                return res
    return None


def _check_credential(user, credential, request):
    """≙ ``user._check_credentials(credential, {"interactive": True})`` (``:105``).

    **Envoltorio de traducción, no despachador** — divergencia 6. El despacho
    por tipo lo hace la cadena de ``_check_credentials`` sobre ``res.users``:
    ``base`` atiende ``password`` y ``authz_totp`` / ``authz_totp_mail`` /
    ``authz_passkey`` cuelgan su tipo encima. Lo único que ocurre aquí es
    convertir el rechazo al contrato local de la vista.

    Devuelve el ``auth_info`` de la fuente —``{'uid', 'auth_method',
    'mfa'}``— o ``None`` si la credencial no verifica.

    ``request`` viaja en ``env`` porque el eslabón de passkey lo necesita: el
    reto de WebAuthn vive en la sesión.
    """
    try:
        return user._check_credentials(
            credential, {'interactive': True, 'request': request})
    except AccessDenied:
        # La fuente deja escapar ``AccessDenied`` y su despachador la
        # convierte en respuesta. Aquí sería un 500: es un ``UserError`` de la
        # fachada, no una ``APIException``, así que el manejador de DRF no la
        # conoce. La vista sella el ``None`` como 401 ``CHECK_IDENTITY_FAILED``.
        return None


def _check_identity(request, credential):
    """≙ ``_check_identity`` (``:75-116``).

    Sin credencial devuelve el catálogo de métodos que este usuario admite.
    Con credencial la verifica y, si el umbral que venció exige MFA, pide el
    segundo factor descartando el que ya se usó.

    Devuelve ``None`` cuando la confirmación queda completa.
    """
    check_identity = _must_check_identity(request) or {}
    first_fa = check_identity.get('1fa')
    user = request.user
    auth_methods = user._get_auth_methods()
    if not credential:
        if first_fa and first_fa in auth_methods:
            auth_methods.remove(first_fa)
        return {'user_id': user.pk, 'login': user.login,
                'auth_methods': auth_methods}

    if credential.get('type') in ('totp', 'totp_mail'):
        credential['token'] = int(re.sub(r'\s', '', str(credential['token'])))

    auth = _check_credential(user, credential, request)
    if auth is None:
        return None

    if first_fa and first_fa != auth['auth_method']:
        request.session.pop(SESSION_CHECK_1FA, None)
    elif (auth['mfa'] != 'skip' and len(auth_methods) > 1
            and check_identity.get('mfa')):
        request.session[SESSION_CHECK_1FA] = (time.time(), credential['type'])
        auth_methods.remove(credential['type'])
        return {'mfa': True, 'auth_methods': auth_methods}

    request.session.pop(SESSION_CHECK_NEXT, None)
    request.session[SESSION_CHECK_LAST] = time.time()
    return None


def _set_session_inactivity(request, inactivity_period=0, force=False):
    """≙ ``_set_session_inactivity`` (``:118-155``) — divergencia 3.

    Marca o limpia la señal de inactividad de la sesión. ``inactivity_period``
    llega en **milisegundos**, como en la fuente (lo envía el cliente).
    ``force`` marca inactivo sin importar la duración — en la fuente es el
    cierre del WebSocket; aquí, un cliente que declara que se va.

    La fuente guarda la sesión a mano porque las peticiones de WebSocket no la
    guardan solas; aquí la marca en ``request.session`` basta, que es lo que
    Django persiste al terminar la petición.
    """
    session = request.session
    inactivity_period = inactivity_period / 1000
    timeout = request.user._get_lock_timeout_inactivity()
    inactive = timeout and (force or inactivity_period >= timeout)
    if inactive:
        next_check = time.time() + timeout - inactivity_period
        if (not session.get(SESSION_CHECK_NEXT)
                or next_check < session[SESSION_CHECK_NEXT]):
            session[SESSION_CHECK_NEXT] = next_check
    elif (timestamp := session.get(SESSION_CHECK_NEXT)) and timestamp > time.time():
        session.pop(SESSION_CHECK_NEXT)


def _authenticate(request, view_func):
    """≙ ``_authenticate`` (``:157-182``).

    La fuente extiende el ``_authenticate`` del núcleo y **añade** el candado;
    aquí Django ya autenticó, así que este símbolo es sólo el añadido: mira si
    la sesión venció y levanta.

    - ``endpoint.routing["auth"] == "user"`` → la petición trae usuario
      autenticado.
    - ``endpoint.routing.get("check_identity", True)`` → la vista puede
      declarar ``check_identity = False`` para quedar exenta, igual que el
      ``@http.route(check_identity=False)`` de la fuente.
    """
    if not getattr(request.user, 'is_authenticated', False):
        return
    must_check_identity = _must_check_identity(request)
    if not must_check_identity:
        return
    if must_check_identity.get('logout'):
        raise SessionLockExpired()
    if (_view_declares_check_identity(view_func)
            and must_check_identity.get('check_identity')):
        methods = request.user._get_auth_methods()
        first_fa = must_check_identity.get('1fa')
        if first_fa and first_fa in methods:
            methods.remove(first_fa)
        raise CheckIdentityRequired(
            auth_methods=methods, mfa=must_check_identity.get('mfa'))


def _view_declares_check_identity(view_func):
    """¿Esta vista se somete al candado? — ≙ ``routing.get("check_identity",
    True)`` (``:180``).

    Lee el atributo de la vista despachada, con el mismo mecanismo y el mismo
    default (``True``) que la fuente. Una vista exenta lo declara::

        class MiVista(APIView):
            check_identity = False

    Y en una vista-función, sobre la función. El patrón —leer una declaración
    de la vista en vez de adivinar del path— es el de
    ``CompanyContextMiddleware._view_declares_frontend``.
    """
    declared = getattr(view_func, 'check_identity', None)
    if declared is None:
        declared = getattr(getattr(view_func, 'cls', None),
                           'check_identity', None)
    if declared is None:
        declared = getattr(getattr(view_func, 'view_class', None),
                           'check_identity', None)
    return True if declared is None else bool(declared)


def _handle_error(exception):
    """≙ ``_handle_error`` (``:184-204``) — divergencia 2.

    Convierte la denegación del candado en respuesta. La fuente redirige a una
    página cuando el transporte es ``http``; aquí no hay página que servir y
    el cuerpo ya lleva ``check_identity_url``, así que todo cliente recibe el
    mismo JSON.

    Devuelve ``None`` si la excepción no es de este addon — el llamador la
    deja subir, como hace el ``super()`` de la fuente.
    """
    if not isinstance(exception, (CheckIdentityRequired, SessionLockExpired)):
        return None
    _logger.log(exception.loglevel, '%s', exception.detail['codigo_error'])
    return JsonResponse(exception.detail, status=exception.status_code)


def _session_info_common_auth_timeout(user, session_info):
    """≙ ``_session_info_common_auth_timeout`` (``:206-220``).

    Añade el umbral de inactividad a la info de sesión, sólo para usuario
    autenticado. La fuente guarda con ``_is_public()``; aquí el equivalente es
    ``is_authenticated``, que es lo que distingue al visitante anónimo.
    """
    if getattr(user, 'is_authenticated', False):
        if timeout := user._get_lock_timeout_inactivity():
            session_info['lock_timeout_inactivity'] = timeout
    return session_info


def session_info(user, session_info_dict):
    """≙ ``session_info`` (``:222-232``) — la info del cliente de backoffice.

    Divergencia 4: recibe el diccionario base en vez de llamar a ``super()``,
    porque su productor aquí es una función de módulo de ``web`` y no un
    método de ``ir.http`` que se pueda extender.
    """
    return _session_info_common_auth_timeout(user, session_info_dict)


def get_frontend_session_info(user, session_info_dict):
    """≙ ``get_frontend_session_info`` (``:234-245``) — la del cliente público.

    La fuente las separa porque son dos clientes con dos contratos; el añadido
    del candado es el mismo en ambos, y por eso las dos delegan en
    ``_session_info_common_auth_timeout``. Se conservan las dos por la misma
    razón que la fuente las tiene: quien busque dónde se le dice al cliente
    cuánto dura su inactividad encuentra su nombre.
    """
    return _session_info_common_auth_timeout(user, session_info_dict)


class CheckIdentityMiddleware:
    """El punto de despacho del candado — ≙ el gancho ``_authenticate`` de la
    fuente en su despachador.

    Va **después** de ``AuthenticationMiddleware``: necesita ``request.user``
    resuelto. ``process_view`` es el hook que Django invoca tras resolver la
    URL y antes de la vista, que es exactamente donde la fuente coloca su
    ``_authenticate``: con el endpoint ya conocido, para poder leer su
    declaración de exención.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Deja pasar, o responde la denegación del candado."""
        try:
            _authenticate(request, view_func)
        except (CheckIdentityRequired, SessionLockExpired) as exception:
            return _handle_error(exception)
        return None

    def __call__(self, request):
        return self.get_response(request)


def register_authz_timeout_signals():
    """Conecta el estampado de ``create_time`` al login — divergencia 1."""
    user_logged_in.connect(
        stamp_session_create_time,
        dispatch_uid='authz_timeout.stamp_session_create_time',
    )


def register_authz_timeout_session_info():
    """Da llamador a ``session_info`` — ≙ heredar ``ir.http.session_info()``.

    En la fuente basta con declarar el método sobre un ``_inherit``: el ORM lo
    mete en la cadena de ``super()`` y corre solo. Aquí el productor es una
    función de módulo de ``web``, así que la herencia se sustituye por un
    registro explícito, y el registro es lo que este addon hace al arrancar.

    Sólo se registra ``session_info``. ``get_frontend_session_info`` **no
    tiene dónde registrarse**: ``web/models/ir_http.py`` (punto 9 de su tabla
    de ausencias) declara su base fuera de alcance —el visitante anónimo de
    este árbol no arranca con un cuerpo de sesión; el carrito de invitado se
    identifica por cabecera—, así que no hay productor público al que
    extender. Se conserva escrito porque su día llega si esa decisión cambia,
    y porque retirarlo sería un porte parcial silencioso.
    """
    register_session_info_extension(session_info)
