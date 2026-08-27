"""Funciones de token de signup sobre el partner.

Adaptación fiel de Odoo ``auth_signup/models/res_partner.py`` (LGPL-3, 201 loc,
leído completo). La referencia extiende ``res.partner`` con ``_inherit``;
Django no lo permite, así que son funciones sobre el partner (mismo criterio
que ``authz_ldap.res_users``). El ``signup_type`` persiste en
``SignupRequest`` (OneToOne).

Métodos de la referencia → aquí:

- ``signup_prepare`` / ``signup_cancel`` → ``signup_prepare`` / ``signup_cancel``.
- ``_generate_signup_token`` → ``_generate_signup_token``: firma
  ``[partner.id, user_ids, login_date, signup_type]`` (``../token.py``). El
  ``login_date`` en el payload invalida el token al iniciar sesión.
- ``_get_partner_from_token`` → ``_get_partner_from_token``: verifica firma +
  edad (validez por tipo) + que login_date/user_ids/signup_type siguen
  coincidiendo con el estado actual.
- ``_signup_retrieve_info`` → ``_signup_retrieve_info``: dict con db/token/
  name/login/email para la pantalla de set-password del SPA.
- ``_get_login_date`` → ``_get_login_date``, con su nombre. Estaba como
  ``_login_date``: el renombre no cambia la visibilidad —el guion bajo se
  conserva— pero **ciega al gate**, que compara por nombre literal
  (:ref:`h-api-579`).
- ``signup_get_auth_param`` → ``signup_get_auth_param`` (para el share url de
  portal): token si no hay usuario, login si ya existe.
- ``_signup_retrieve_partner`` → ``_signup_retrieve_partner``: la entrada
  **pública** del par, que convierte el ``None`` de ``_get_partner_from_token``
  en el ``UserError`` de la fuente. Su ``check_validity`` no se porta — allá la
  validez es un chequeo aparte porque el token es una cadena guardada en la
  fila; aquí es una firma con edad, así que resolver **es** validar.
- ``_get_signup_url*`` → NO portados: arman la URL ``/web/reset_password`` del
  frontend QWeb de Odoo; el SPA arma su propia URL con el token que devuelve
  ``_signup_retrieve_info``/``signup_get_auth_param``.
- ``action_signup_prepare`` → NO portado: su cuerpo entero es
  ``return self.signup_prepare()``, un alias que existe para que un botón del
  backoffice tenga a qué apuntar. Sin ese formulario, el alias no envuelve
  nada — el llamador invoca ``signup_prepare`` directamente.
- ``random_token`` → NO portado: **divergencia de mecanismo**, no omisión. La
  fuente genera 20 caracteres al azar y los **guarda en la fila**; aquí el
  token es una carga firmada (``../token.py``), así que no hay cadena
  aleatoria que generar ni columna donde ponerla. Es la misma decisión que
  hace innecesario su ``check_validity``.
- ``now`` → NO portado: es ``datetime.now() + timedelta(**kwargs)``, un
  ayudante de una línea que existe porque su ORM compara fechas en el
  dominio. Aquí la validez se mide en **segundos de edad de la firma**
  (``_validity_seconds``), así que no hay a qué sumarle un delta.
"""
from datetime import datetime

from django.apps import apps as django_apps

from exceptions import AccessDenied, UserError

from addons.authz_signup.models.signup_request import SignupRequest
from addons.authz_signup.models.policy import signup_open
from addons.authz_signup.models.token import (
    read_signup_payload,
    read_signup_payload_unchecked_age,
    sign_signup_payload,
)
from addons.base.models import SystemParameter

# ≙ ir.config_parameter de validez (res_partner.py:186-188), renombrados al
# namespace del addon nuestro. Default idéntico: signup 144h, reset 4h.
PARAM_SIGNUP_VALIDITY_HOURS = 'authz_signup.signup_validity_hours'
PARAM_RESET_VALIDITY_HOURS = 'authz_signup.reset_validity_hours'
# Forma propia (el tipo ``verify`` no existe en la referencia). 24 h es el TTL
# decidido en ``analisis-auto-login-verificacion-email`` y se conserva.
PARAM_VERIFY_VALIDITY_HOURS = 'authz_signup.verify_validity_hours'
_DEFAULT_SIGNUP_HOURS = 144
_DEFAULT_RESET_HOURS = 4
_DEFAULT_VERIFY_HOURS = 24


def _validity_seconds(signup_type):
    if signup_type == SignupRequest.TYPE_RESET:
        hours = int(SystemParameter.get_param(
            PARAM_RESET_VALIDITY_HOURS, str(_DEFAULT_RESET_HOURS)))
    elif signup_type == SignupRequest.TYPE_VERIFY:
        hours = int(SystemParameter.get_param(
            PARAM_VERIFY_VALIDITY_HOURS, str(_DEFAULT_VERIFY_HOURS)))
    else:
        hours = int(SystemParameter.get_param(
            PARAM_SIGNUP_VALIDITY_HOURS, str(_DEFAULT_SIGNUP_HOURS)))
    return hours * 3600


def _signup_type(partner):
    req = SignupRequest.objects.filter(partner=partner).first()
    return req.signup_type if req else None


def _get_login_date(partner):
    """≙ ``_get_login_date`` (res_partner.py:163-169): el último login entre
    los usuarios del partner (int timestamp), o ``None``."""
    dates = [
        u.last_login for u in partner.users.all() if u.last_login is not None
    ]
    if dates:
        return int(max(d.timestamp() for d in dates))
    return None


def signup_prepare(partner, signup_type=SignupRequest.TYPE_SIGNUP):
    """≙ ``signup_prepare`` (res_partner.py:113-116)."""
    SignupRequest.objects.update_or_create(
        partner=partner, defaults={'signup_type': signup_type})
    return True


def signup_cancel(partner):
    """≙ ``signup_cancel`` (res_partner.py:110-111): invalida el signup
    pendiente (borra la fila = signup_type None)."""
    SignupRequest.objects.filter(partner=partner).delete()
    return True


def _generate_signup_token(partner):
    """≙ ``_generate_signup_token`` (res_partner.py:171-191)."""
    signup_type = _signup_type(partner) or SignupRequest.TYPE_SIGNUP
    user_ids = sorted(partner.users.values_list('id', flat=True))
    payload = [partner.id, user_ids, _get_login_date(partner), signup_type]
    return sign_signup_payload(payload)


def _get_partner_from_token(token):
    """≙ ``_get_partner_from_token`` (res_partner.py:193-201).

    Verifica firma, edad (validez por tipo) y que el estado del partner
    (login_date / user_ids / signup_type) sigue coincidiendo con el payload —
    así el token queda invalidado al iniciar sesión o al cancelar el signup.
    """
    # Primero la firma sola, para leer el signup_type y su validez.
    peek = read_signup_payload_unchecked_age(token)
    if not peek:
        return None
    _pid, _uids, _ld, signup_type = peek
    payload = read_signup_payload(token, _validity_seconds(signup_type))
    if not payload:
        return None
    partner_id, user_ids, login_date, tok_type = payload

    ResPartner = django_apps.get_model('base', 'ResPartner')
    partner = ResPartner.objects.filter(pk=partner_id).first()
    if partner is None:
        return None
    current_uids = sorted(partner.users.values_list('id', flat=True))
    if (login_date == _get_login_date(partner)
            and user_ids == current_uids
            and tok_type == (_signup_type(partner) or None)):
        return partner
    return None


def _signup_retrieve_partner(token, raise_exception=True):
    """≙ ``_signup_retrieve_partner`` (``res_partner.py:119-130``).

    Resuelve el token a su partner. Es la entrada **pública** del par:
    ``_get_partner_from_token`` devuelve ``None`` ante cualquier fallo —firma,
    edad, o estado que ya no coincide— y ésta lo convierte en el
    ``UserError`` con el mensaje de la fuente, verbatim.

    Los dos existen a propósito y no son redundantes: quien necesita
    **decidir** consulta el que devuelve ``None``
    (``_signup_retrieve_info``), y quien necesita **parar** llama a éste.
    Colapsarlos obligaría a todo llamador a levantar su propia excepción, y
    el mensaje dejaría de ser uno solo.

    ``check_validity`` de la fuente no tiene receptor aquí: allá la validez
    es un chequeo aparte porque el token es una cadena aleatoria guardada en
    la fila; aquí es una firma con edad, así que
    ``_get_partner_from_token`` no puede resolver sin validar. Un token
    resuelto es un token válido, y por eso el parámetro no se porta.

    :param token: el token a resolver.
    :param raise_exception: si es ``False``, devuelve ``None`` en vez de
        levantar — la forma que la fuente declara y que su propio cuerpo
        ignora (levanta siempre). Aquí sí se respeta.
    """
    partner = _get_partner_from_token(token)
    if partner is None and raise_exception:
        raise UserError("Signup token '%s' is not valid or expired" % token)
    return partner


def _signup_retrieve_info(token):
    """≙ ``_signup_retrieve_info`` (res_partner.py:132-161): datos para la
    pantalla de set-password (``None`` si el token no es válido)."""
    partner = _signup_retrieve_partner(token, raise_exception=False)
    if partner is None:
        return None
    res = {'token': token, 'name': partner.name}
    user = partner.users.first()
    if user is not None:
        res['login'] = user.login
    else:
        res['email'] = res['login'] = partner.email or ''
    return res


def signup_get_auth_param(partner, requester):
    """≙ ``signup_get_auth_param`` (res_partner.py:91-108): token si no hay
    usuario y el signup público está abierto; login si ya existe. Sólo un
    usuario interno lo pide (el que comparte el documento del portal)."""
    if not requester._is_internal():
        raise AccessDenied('Only internal users can request a signup param.')
    user = partner.users.first()
    if user is not None:
        return {'auth_login': user.login}
    if signup_open():
        signup_prepare(partner)
        return {'auth_signup_token': _generate_signup_token(partner)}
    return {}
