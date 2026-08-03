"""Funciones de token de signup sobre el partner.

Adaptación fiel de Odoo ``auth_signup/models/res_partner.py`` (LGPL-3, 201 loc,
leído completo). La referencia extiende ``res.partner`` con ``_inherit``;
Django no lo permite, así que son funciones sobre el partner (mismo criterio
que ``authz_ldap.res_users``). El ``signup_type`` persiste en
``SignupRequest`` (OneToOne).

Métodos de la referencia → aquí:

- ``signup_prepare`` / ``signup_cancel`` → ``signup_prepare`` / ``signup_cancel``.
- ``_generate_signup_token`` → ``generate_signup_token``: firma
  ``[partner.id, user_ids, login_date, signup_type]`` (``../token.py``). El
  ``login_date`` en el payload invalida el token al iniciar sesión.
- ``_get_partner_from_token`` → ``get_partner_from_token``: verifica firma +
  edad (validez por tipo) + que login_date/user_ids/signup_type siguen
  coincidiendo con el estado actual.
- ``_signup_retrieve_info`` → ``signup_retrieve_info``: dict con db/token/
  name/login/email para la pantalla de set-password del SPA.
- ``_get_login_date`` → ``_login_date``.
- ``signup_get_auth_param`` → ``signup_get_auth_param`` (para el share url de
  portal): token si no hay usuario, login si ya existe.
- ``_get_signup_url*`` → NO portados: arman la URL ``/web/reset_password`` del
  frontend QWeb de Odoo; el SPA arma su propia URL con el token que devuelve
  ``signup_retrieve_info``/``signup_get_auth_param``.
"""
from datetime import datetime

from django.apps import apps as django_apps

from exceptions import AccessDenied, UserError

from addons.authz_signup.models.signup_request import SignupRequest
from addons.authz_signup.policy import signup_open
from addons.authz_signup.token import (
    read_signup_payload,
    read_signup_payload_unchecked_age,
    sign_signup_payload,
)
from addons.base.models import SystemParameter

# ≙ ir.config_parameter de validez (res_partner.py:186-188), renombrados al
# namespace del addon nuestro. Default idéntico: signup 144h, reset 4h.
PARAM_SIGNUP_VALIDITY_HOURS = 'authz_signup.signup_validity_hours'
PARAM_RESET_VALIDITY_HOURS = 'authz_signup.reset_validity_hours'
_DEFAULT_SIGNUP_HOURS = 144
_DEFAULT_RESET_HOURS = 4


def _validity_seconds(signup_type):
    if signup_type == SignupRequest.TYPE_RESET:
        hours = int(SystemParameter.get_param(
            PARAM_RESET_VALIDITY_HOURS, str(_DEFAULT_RESET_HOURS)))
    else:
        hours = int(SystemParameter.get_param(
            PARAM_SIGNUP_VALIDITY_HOURS, str(_DEFAULT_SIGNUP_HOURS)))
    return hours * 3600


def _signup_type(partner):
    req = SignupRequest.objects.filter(partner=partner).first()
    return req.signup_type if req else None


def _login_date(partner):
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


def generate_signup_token(partner):
    """≙ ``_generate_signup_token`` (res_partner.py:171-191)."""
    signup_type = _signup_type(partner) or SignupRequest.TYPE_SIGNUP
    user_ids = sorted(partner.users.values_list('id', flat=True))
    payload = [partner.id, user_ids, _login_date(partner), signup_type]
    return sign_signup_payload(payload)


def get_partner_from_token(token):
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
    if (login_date == _login_date(partner)
            and user_ids == current_uids
            and tok_type == (_signup_type(partner) or None)):
        return partner
    return None


def signup_retrieve_info(token):
    """≙ ``_signup_retrieve_info`` (res_partner.py:132-161): datos para la
    pantalla de set-password (``None`` si el token no es válido)."""
    partner = get_partner_from_token(token)
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
    if not requester.is_internal():
        raise AccessDenied('Only internal users can request a signup param.')
    user = partner.users.first()
    if user is not None:
        return {'auth_login': user.login}
    if signup_open():
        signup_prepare(partner)
        return {'auth_signup_token': generate_signup_token(partner)}
    return {}
