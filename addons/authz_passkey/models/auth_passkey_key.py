"""``auth.passkey.key`` — la passkey (credencial WebAuthn) de un usuario.

Adaptación fiel de Odoo ``auth_passkey/models/auth_passkey_key.py`` (LGPL-3,
194 loc, leído completo). La librería ``webauthn`` que la referencia
vendoriza (``_vendor/``) es aquí la dependencia ``webauthn>=2.8.0`` — misma
API pública (verificado: los 8 símbolos importan).

Divergencias declaradas:

- ``groups='base.group_system'`` sobre ``credential_identifier``/
  ``public_key``/``sign_count`` → los campos NO salen por la API (el
  serializer sólo expone ``id``/``name``/``created_at``).
- El ``init()`` con ``ALTER TABLE`` (columna sin ORM para blindarla del
  prefetch) es mecánica del ORM de Odoo; Django no hace prefetch implícito
  de columnas — campo normal.
- ``@check_identity`` en delete/create → DEC-12: la capacidad
  ``account.security`` es sensible y exige ReauthSession fresca (mismo
  efecto: re-autenticarse antes de tocar passkeys).
- ``_VALID_APK_KEY_HASHES`` (orígenes de la app móvil de Odoo) no aplica.
- ``rp_id``/``origin`` salen de ``web.base.url`` (SystemParameter, con la
  petición como fallback) — la referencia usa ``get_base_url()``.
"""
import json
import logging
from urllib.parse import urlparse

from django.conf import settings

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

import fields
import models
from exceptions import AccessDenied

from addons.base.models import SystemParameter, TimeStampedModel

_logger = logging.getLogger(__name__)

PARAM_BASE_URL = 'web.base.url'
SESSION_CHALLENGE_KEY = 'webauthn_challenge'


def _base_url(request):
    """``get_base_url()`` de la referencia: el param ``web.base.url`` manda;
    sin él, el origen de la petición."""
    configured = str(SystemParameter.get_param(PARAM_BASE_URL, '') or '')
    if configured:
        return configured
    return request.build_absolute_uri('/').rstrip('/')


class PasskeyKey(TimeStampedModel):
    """≙ ``AuthPasskeyKey`` (auth_passkey_key.py:21-157)."""

    name = fields.Char(max_length=255, verbose_name='Nombre')
    credential_identifier = fields.Char(
        max_length=1024, unique=True,
        verbose_name='Identificador de credencial',
        help_text='NO expuesto por la API (group_system en la referencia).',
    )
    public_key = fields.Char(
        max_length=2048, blank=True, default='',
        verbose_name='Llave pública',
        help_text='NO expuesta por la API (group_system en la referencia).',
    )
    sign_count = fields.Integer(
        default=0, verbose_name='Contador de firmas',
    )
    user = fields.Many2one(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='passkeys', db_index=True, verbose_name='Usuario',
        help_text='≙ create_uid; el o2m auth_passkey_key_ids de res_users '
                  'es este reverso.',
    )

    class Meta:
        db_table = 'auth_passkey_key'
        ordering = ['-id']
        verbose_name = 'Passkey'
        verbose_name_plural = 'Passkeys'

    def __str__(self):
        return self.name

    # ------------------------------------------------------------------
    # Challenge de sesión — ≙ auth_passkey_key.py:62-67
    # ------------------------------------------------------------------

    @staticmethod
    def _get_session_challenge(request):
        challenge = request.session.pop(SESSION_CHALLENGE_KEY, None)
        if not challenge:
            raise AccessDenied('Cannot find a challenge for this session')
        return challenge

    # ------------------------------------------------------------------
    # Autenticación — ≙ auth_passkey_key.py:69-92
    # ------------------------------------------------------------------

    @classmethod
    def _start_auth(cls, request):
        """≙ ``_start_auth``: opciones de autenticación + challenge en la
        sesión."""
        authentication_options = json.loads(options_to_json(
            generate_authentication_options(
                rp_id=urlparse(_base_url(request)).hostname,
                user_verification=UserVerificationRequirement.REQUIRED,
            )))
        request.session[SESSION_CHALLENGE_KEY] = (
            authentication_options['challenge'])
        return authentication_options

    @classmethod
    def _verify_auth(cls, request, auth, public_key, sign_count):
        """≙ ``_verify_auth``: devuelve el nuevo ``sign_count``."""
        parsed = urlparse(_base_url(request))
        expected_origin = f'{parsed.scheme}://{parsed.netloc}'
        auth_verification = verify_authentication_response(
            credential=auth,
            expected_challenge=base64url_to_bytes(
                cls._get_session_challenge(request)),
            expected_origin=[expected_origin],
            expected_rp_id=parsed.hostname,
            credential_public_key=base64url_to_bytes(public_key),
            credential_current_sign_count=sign_count,
            require_user_verification=True,
        )
        return auth_verification.new_sign_count

    # ------------------------------------------------------------------
    # Registro — ≙ auth_passkey_key.py:94-124 + el wizard :160-194
    # ------------------------------------------------------------------

    @classmethod
    def _start_registration(cls, request, user):
        """≙ ``_start_registration``: opciones de registro + challenge."""
        registration_options = json.loads(options_to_json(
            generate_registration_options(
                rp_id=urlparse(_base_url(request)).hostname,
                rp_name='Kaupamex',
                user_id=str(user.id).encode(),
                user_name=user.login,
                authenticator_selection=AuthenticatorSelectionCriteria(
                    resident_key=ResidentKeyRequirement.REQUIRED,
                    user_verification=UserVerificationRequirement.REQUIRED,
                ),
            )))
        request.session[SESSION_CHALLENGE_KEY] = (
            registration_options['challenge'])
        return registration_options

    @classmethod
    def _verify_registration_options(cls, request, registration):
        """≙ ``_verify_registration_options``."""
        parsed = urlparse(_base_url(request))
        expected_origin = f'{parsed.scheme}://{parsed.netloc}'
        verification = verify_registration_response(
            credential=registration,
            expected_challenge=base64url_to_bytes(
                cls._get_session_challenge(request)),
            expected_origin=[expected_origin],
            expected_rp_id=parsed.hostname,
            require_user_verification=True,
        )
        return {
            'credential_id': verification.credential_id,
            'credential_public_key': verification.credential_public_key,
        }
