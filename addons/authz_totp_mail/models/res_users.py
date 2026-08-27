"""2FA por correo — clave, código, envío, verificación, política e invitación.

Adaptación fiel de Odoo ``auth_totp_mail/models/res_users.py`` (LGPL-3,
216 loc, leído completo). La referencia extiende ``res.users``; aquí son
funciones sobre el usuario (no hay ``_inherit``), mismo criterio que
``authz_ldap.models.res_users``.

Métodos de la referencia → aquí:

- ``_get_totp_mail_key`` / ``_get_totp_mail_code`` / ``_send_totp_mail_code``
  → ``totp_mail_key`` / ``totp_mail_code`` / ``send_totp_mail_code``.
- ``_check_credentials`` (type ``totp_mail``) → portado abajo **con su nombre**
  y encadenado sobre ``res.users``; ``verify_totp_mail_code`` queda como el
  verificador que consume, reutilizable por la vista del segundo paso. Es el
  tercer eslabón de la cadena que ``base`` abre (#722).
- ``_mfa_type`` / ``_mfa_url`` → el **eslabón externo** de la cadena de tres
  (``base`` → ``authz_totp`` → éste), encadenado con
  ``combine=keep_previous`` para que gane el interno, que es la precedencia de
  la fuente. Su condición es ``totp_mail_policy_applies`` —sólo la política,
  como la fuente.

  **``totp_mail_required`` se retiró (#719, H-API-777).** Era un predicado
  nuestro —0 hits en la referencia— que devolvía *"la política lo exige **y**
  no tiene TOTP de app"*, y esa conjunción es exactamente lo que el
  ``combine=keep_previous`` de la cadena ya calcula: con app activa gana el
  eslabón interno y ``_mfa_type()`` da ``'totp'``. La forma de la fuente para
  la misma pregunta es ``_mfa_type() == 'totp_mail'``, que usa en 5 sitios.
  Tener las dos invitaba a consultar la equivocada, que es literalmente lo que
  la tarea #719 preguntaba.
- ``action_totp_invite`` / ``get_totp_invite_url`` → ``invite_users`` /
  ``get_totp_invite_url`` (la URL es config L2: el puente de portal la
  re-enruta por audiencia, como hace ``auth_totp_portal`` en la referencia).
- ``write`` (notificación al activar/desactivar 2FA) → ``../signals.py``.
- ``_notify_security_new_connection`` → portado abajo con el mismo nombre, y
  encadenado sobre el eslabón vacío que ``base`` declara. Su llamador es
  ``session_authenticate``, que es donde cae la frontera aquí: la fuente lo
  invoca desde su propio ``authenticate`` (``:44-48``), un método de modelo que
  el addon envuelve con ``super()``; aquí el punto de entrada del login es una
  vista DRF y las vistas no se encadenan.
- ``authenticate`` → NO portado **como método**: la fuente concentra ahí el
  chequeo, la fecha de login y el ``auth_info``, y aquí eso lo reparte Django
  entre sus cuatro backends. Lo que **sí** se unificó (#722) es la mitad de
  verificación: ``_check_credentials`` existe como cadena sobre ``res.users``,
  con este addon de tercer eslabón.
- ``_rpc_api_keys_only`` / ``action_open_my_account_settings`` → NO
  portados: RPC keys y acción de ventana del backoffice Odoo.

**Rate limit (divergencia declarada):** la referencia llama
``_totp_rate_limit('code_check'|'send_email')`` de ``auth_totp``, que
persiste en ``auth_totp_rate_limit_log`` — modelo NO portado (mismo gap).
Hasta portarlo, estos flujos quedan sin rate limit propio.
"""
import logging
from datetime import datetime

from django.apps import apps as django_apps

from exceptions import AccessDenied, UserError
from orm.method_chain import chain_method, keep_previous
from orm.model_classes import extend_model
from tools.misc import hmac as tools_hmac

from addons.authz_totp.models.auth_totp import (
    BROWSER_SCOPE, TRUSTED_DEVICE_COOKIE, AuthTotpDevice,
)
from addons.authz_totp.models.totp import TOTP, hotp
from addons.base.models import SystemParameter
from addons.mail.models.email_executor import dispatch_email
from addons.mail.models.mail_template import MailTemplate

_logger = logging.getLogger(__name__)

# ≙ ir.config_parameter 'auth_totp.policy' (res_users.py:121-126):
# '' (apagada) | 'all_required' | 'employee_required'.
PARAM_TOTP_POLICY = 'authz_totp.policy'
# URL a la que invita el correo. En la referencia es la acción del
# backoffice ('/odoo/action-...', res_users.py:93-94) y el puente
# auth_totp_portal la re-enruta a '/my/security' para no-internos. Aquí es
# L2 para que cada despliegue apunte a su ruta del SPA.
PARAM_INVITE_URL = 'authz_totp_mail.invite_url'

# Ventana del código por correo: 1 hora, igual que la referencia
# (window=3600, timestep=3600 — res_users.py:146,177).
TOTP_MAIL_WINDOW = 3600
TOTP_MAIL_TIMESTEP = 3600

TEMPLATE_TOTP_INVITE = 'authz_totp_mail: invitación 2FA'
TEMPLATE_TOTP_MAIL_CODE = 'authz_totp_mail: código 2FA'

# ≙ el asunto y el cuerpo del aviso de conexión nueva (res_users.py:63-65),
# verbatim. Como en ``../signals.py``, el correo va directo por
# ``dispatch_email``: la plantilla QWeb ``mail.account_security_alert`` con su
# ``suggest_2fa`` es capa de presentación del backoffice y no se porta.
NEW_CONNECTION_SUBJECT = 'New Connection to your Account'
NEW_CONNECTION_CONTENT = 'A new device was used to sign in to your account.'

# ≙ la ruta del segundo paso por correo ('/web/login/totp', res_users.py:133).
# La referencia la escribe literal en los dos archivos de la cadena en vez de
# compartir una constante; aquí se replica esa independencia —el 2FA de app y
# el de correo pueden divergir de ruta sin tocarse.
TOTP_MAIL_SECOND_STEP_URL = '/login/totp'


def totp_mail_key(user):
    """≙ ``_get_totp_mail_key`` (res_users.py:160-162): clave HMAC derivada
    del secreto del despliegue + identidad y último login del usuario (el
    ``login_date`` de la referencia invalida los códigos al re-loguear)."""
    message = str((user.id, user.login, user.last_login))
    return tools_hmac('auth_totp_mail-code', message).encode()


def totp_mail_code(user):
    """≙ ``_get_totp_mail_code`` (res_users.py:164-182): ``(code, segundos)``.

    El guard de sesión pre-auth de la referencia (``request.session.pre_uid``)
    pertenece a su flujo de login web; aquí el llamador controla el contexto.
    """
    key = totp_mail_key(user)
    counter = int(datetime.now().timestamp() / TOTP_MAIL_TIMESTEP)
    code = hotp(key, counter)
    return str(code).zfill(6), TOTP_MAIL_WINDOW


def verify_totp_mail_code(user, code):
    """≙ ``_check_credentials`` type ``totp_mail`` (res_users.py:139-158).

    Devuelve True si el código de 6 dígitos coincide dentro de la ventana.
    Levanta ``AccessDenied`` con el mismo mensaje que la referencia si no.
    """
    try:
        token = int(code)
    except (TypeError, ValueError):
        token = None
    match = None
    if token is not None:
        match = TOTP(totp_mail_key(user)).match(
            token, window=TOTP_MAIL_WINDOW, timestep=TOTP_MAIL_TIMESTEP)
    if match is None:
        _logger.info('2FA check (mail): FAIL for %r', user.login)
        raise AccessDenied(
            'Verification failed, please double-check the 6-digit code')
    _logger.info('2FA check (mail): SUCCESS for %r', user.login)
    return True


def send_totp_mail_code(user):
    """≙ ``_send_totp_mail_code`` (res_users.py:184-216): renderiza la
    plantilla del código y la despacha al email del usuario."""
    if not user.login:
        raise UserError(
            'Cannot send email: user %s has no email address.' % user)
    code, expiration = totp_mail_code(user)
    template = MailTemplate.objects.filter(
        name=TEMPLATE_TOTP_MAIL_CODE).first()
    if template is None:
        raise UserError('TOTP mail template is not seeded.')
    rendered = template.render(user, extra_context={
        'code': code, 'expiration_minutes': expiration // 60,
    })
    dispatch_email(
        rendered['subject'], rendered['body_html'],
        rendered['email_from'] or None, [user.login])
    _logger.info('TOTP mail code sent to %r', user.login)


def totp_mail_policy_applies(user):
    """≙ el tramo de política de ``_mfa_type`` (res_users.py:120-126): True si
    la política L2 exige 2FA a este usuario, **sin mirar** si ya tiene TOTP de
    app.

    Es la condición completa del eslabón externo de la cadena, y sólo ésa: en
    la fuente, al usuario que ya tiene la app lo descarta el ``super()`` de
    arriba, no este tramo.

    ``employee_required`` (≙ ``_is_internal`` de la referencia) usa
    ``ResUsers._is_internal()`` — el eje interno/portal real, resuelto por el
    ``user_type`` de los grupos (antes era el proxy ``partner.employee``).
    """
    policy = SystemParameter.get_param(PARAM_TOTP_POLICY, '')
    if policy == 'all_required':
        return True
    if policy == 'employee_required':
        return user._is_internal()
    return False


def _mfa_type(self):
    """≙ ``_mfa_type`` (``:116-125``) — ``'totp_mail'`` si la política lo exige.

    Es el eslabón **externo**: devuelve ``None`` cuando la política no aplica,
    y su valor cede ante el del eslabón interno por ``keep_previous``.

    Consulta ``totp_mail_policy_applies`` —sólo la política— y ésa es la forma
    de la fuente. La diferencia no es cosmética: meter aquí dentro la guarda
    *"…y no tiene TOTP de app"* haría callar al eslabón justo en el caso que la
    precedencia decide, y entonces la cadena daría ``'totp'`` por el predicado y
    no por el ``combine``. Medido: escrito así, el control de precedencia
    (``tests/unit/authz_totp/test_res_users.py``) no discrimina.

    **La pregunta compuesta se hace sobre el resultado, no antes:**
    ``user._mfa_type() == 'totp_mail'`` — la forma que la fuente usa en sus 5
    consumidores. Ver #719 / :ref:`h-api-777`.
    """
    if totp_mail_policy_applies(self):
        return 'totp_mail'


def _mfa_url(self):
    """≙ ``_mfa_url`` (``:127-132``) — la ruta del segundo paso para el correo."""
    if self._mfa_type() == 'totp_mail':
        return TOTP_MAIL_SECOND_STEP_URL


def _check_credentials(self, credential, env):
    """≙ ``_check_credentials`` tipo ``totp_mail`` (``:138-156``).

    Es el **tercer** eslabón de la cadena: atiende su tipo y devuelve ``None``
    para cualquier otro, que es el relevo perezoso de ``chain_method``
    ocupando el lugar del ``return super()._check_credentials(...)`` de la
    fuente (``:155-156``).

    ``mfa='default'`` es de la referencia (``:154``) y **no** es cosmético: su
    consumidor en el candado por tiempo compara ``auth['mfa'] != 'skip'`` para
    decidir si exige el segundo factor. Con ``'skip'`` esa rama no dispara y la
    confirmación de dos factores colapsa a uno — el defecto que este porte
    corrige (:ref:`h-api-780`).

    ``verify_totp_mail_code`` ya levanta ``AccessDenied`` con el mensaje de la
    fuente, así que aquí no se traduce nada: el rechazo atraviesa la cadena
    entera sin que ningún eslabón lo atienda, que es el contrato.

    **Divergencia declarada — el límite de tasa.** La fuente llama
    ``_totp_rate_limit('code_check')`` al entrar y purga dos contadores al
    acertar (``:140``, ``:149-150``). Ese mecanismo persiste en
    ``auth_totp_rate_limit_log``, modelo **no portado** (gap ya nombrado en el
    docstring del módulo y en H-API-232). Se porta con el modelo.
    """
    if credential.get('type') != 'totp_mail':
        return None
    verify_totp_mail_code(self, credential.get('token') or '')
    return {'uid': self.pk, 'auth_method': 'totp_mail', 'mfa': 'default'}


def _notify_security_new_connection(self, request):
    """≙ ``_notify_security_new_connection`` (``:50-67``) — dispositivo nuevo.

    La fuente lo llama desde su ``authenticate`` con el docstring *"Send an
    alert on new connection. 2FA enabled -> only for new device. Not enabled
    -> no alert"*. Los tres guardas son los suyos: que haya petición, que el
    usuario tenga correo, y que **tenga un método de MFA activo**.

    **El momento es la mitad del mecanismo, y no es intercambiable.** El aviso
    sale cuando la CREDENCIAL acierta, antes de que el segundo factor
    responda — no al abrirse la sesión. Con eso, quien tiene la contraseña y
    no el segundo factor **también** dispara el aviso, que es de quien protege
    al titular. Moverlo al final del flujo lo dejaría mudo justo en ese caso.

    Aquí el correo es ``login`` (este árbol no declara un campo ``email``
    aparte), igual que en ``send_totp_mail_code`` y en ``../signals.py``.
    """
    if request is None or not self.login or not self._mfa_type():
        return
    key = request.COOKIES.get(TRUSTED_DEVICE_COOKIE)
    if key and AuthTotpDevice._check_credentials_for_uid(
            scope=BROWSER_SCOPE, key=key, uid=self.pk):
        return  # dispositivo ya recordado: la fuente tampoco avisa
    dispatch_email(
        NEW_CONNECTION_SUBJECT, NEW_CONNECTION_CONTENT, None, [self.login])
    _logger.info('New device alert email sent for user <%s>', self.login)


def _chain_res_users(model):
    """Instala los cuatro eslabones que este addon cuelga de ``res.users``.

    ``keep_previous`` invierte el relevo por defecto de ``chain_method``: sin
    él este addon —que se instala **después**, porque depende de
    ``authz_totp``— ganaría la precedencia y devolvería ``'totp_mail'`` donde
    la fuente devuelve ``'totp'``.

    Los otros dos van **sin** ``combine``, y por razones distintas:

    - ``_notify_security_new_connection`` no elige un valor: produce un efecto
      y devuelve ``None``, así que el relevo por defecto es el correcto (ver el
      comentario del bloque en ``base/models/res_users.py``).
    - ``_check_credentials`` **sí** quiere el relevo por defecto, porque su
      semántica en la fuente **es** la del relevo: cada eslabón atiende su tipo
      y delega el resto. ``keep_previous`` daría la precedencia contraria y el
      tipo ``totp_mail`` nunca llegaría a atenderse.
    """
    chain_method(model, '_mfa_type', _mfa_type, combine=keep_previous)
    chain_method(model, '_mfa_url', _mfa_url, combine=keep_previous)
    chain_method(model, '_notify_security_new_connection',
                 _notify_security_new_connection)
    chain_method(model, '_check_credentials', _check_credentials)


def apply_authz_totp_mail_res_users_extensions():
    """Cuelga sobre ``res.users`` el eslabón de correo — ≙ ``_inherit``."""
    extend_model('base', 'ResUsers', luego=_chain_res_users)


def get_totp_invite_url():
    """≙ ``get_totp_invite_url`` (res_users.py:93-94), como config L2."""
    return str(SystemParameter.get_param(
        PARAM_INVITE_URL, '/account/security'))


def invite_users(users, inviter):
    """≙ ``action_totp_invite`` (res_users.py:96-116): envía la invitación a
    los usuarios que aún no tienen 2FA activo y devuelve sus nombres."""
    TotpSecret = django_apps.get_model('authz_totp', 'TotpSecret')
    template = MailTemplate.objects.filter(
        name=TEMPLATE_TOTP_INVITE).first()
    if template is None:
        raise UserError('TOTP invite template is not seeded.')
    with_totp = set(
        TotpSecret.objects.filter(
            user__in=[u.id for u in users], confirmed=True,
        ).values_list('user_id', flat=True)
    )
    invited = []
    for user in users:
        if user.id in with_totp:
            continue
        rendered = template.render(user, extra_context={
            'inviter': inviter, 'invite_url': get_totp_invite_url(),
        })
        dispatch_email(
            rendered['subject'], rendered['body_html'],
            rendered['email_from'] or None, [user.login])
        invited.append(str(user.partner) if user.partner_id else user.login)
    return invited
