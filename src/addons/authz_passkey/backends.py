"""Backend de passkeys — ≙ ``auth_passkey/models/res_users.py:34-73``.

Adaptación de Odoo ``auth_passkey`` (LGPL-3). La referencia resuelve la
credencial ``{'type': 'webauthn', 'webauthn_response': ...}`` en dos pasos:
``_login`` traduce el ``credential_identifier`` al login del dueño, y
``_check_credentials`` verifica la respuesta WebAuthn y actualiza el
``sign_count``. Los dos colapsan aquí en ``authenticate()``.

``mfa: 'skip'`` de la referencia (una passkey ya es multifactor: posesión +
verificación del usuario) se hereda como semántica: el flujo que use este
backend no exige el segundo factor TOTP.
"""
import logging

from django.apps import apps as django_apps
from django.contrib.auth.backends import BaseBackend

from webauthn.helpers.exceptions import InvalidAuthenticationResponse

from addons.authz_passkey.models.auth_passkey_key import PasskeyKey

_logger = logging.getLogger(__name__)


class PasskeyBackend(BaseBackend):

    def authenticate(self, request, webauthn_response=None, **kwargs):
        if not webauthn_response or request is None:
            return None
        credential_id = webauthn_response.get('id')
        passkey = (
            PasskeyKey.objects
            .select_related('user')
            .filter(credential_identifier=credential_id, user__active=True)
            .first()
        )
        if passkey is None:
            # ≙ AccessDenied('Unknown passkey') — contrato de backend: None.
            return None
        try:
            new_sign_count = PasskeyKey.verify_auth(
                request, webauthn_response, passkey.public_key,
                passkey.sign_count)
        except InvalidAuthenticationResponse as exc:
            _logger.info('Passkey auth failed for %r: %s',
                         passkey.user.login, exc)
            return None
        passkey.sign_count = new_sign_count
        passkey.save(update_fields=['sign_count', 'updated_at'])
        return passkey.user

    def get_user(self, user_id):
        ResUsers = django_apps.get_model('base', 'ResUsers')
        return ResUsers.objects.filter(pk=user_id, active=True).first()
