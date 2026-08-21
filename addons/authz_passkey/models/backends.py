"""Backend de passkeys — ≙ ``auth_passkey/models/res_users.py:34-73``.

Adaptación de Odoo ``auth_passkey`` (LGPL-3). La referencia resuelve la
credencial ``{'type': 'webauthn', 'webauthn_response': ...}`` en dos pasos:
``_login`` traduce el ``credential_identifier`` al login del dueño, y
``_check_credentials`` verifica la respuesta WebAuthn y actualiza el
``sign_count``. Los dos colapsan aquí en ``authenticate()``.

``mfa: 'skip'`` de la referencia (una passkey ya es multifactor: posesión +
verificación del usuario) se hereda como semántica: el flujo que use este
backend no exige el segundo factor TOTP.

**Dos caminos, un verificador.** La fuente usa el mismo ``_verify_auth`` para
el login y para la confirmación de identidad; lo que cambia es el predicado
de búsqueda de la passkey. En el login el usuario es desconocido, así que
busca por ``credential_identifier`` sobre todo el registro
(``auth_passkey/models/res_users.py:38-46``); en la confirmación el usuario ya
está autenticado, así que acota a las suyas
(``("create_uid", "=", self.env.user.id)``, ``:52-55``). Aquí son
``PasskeyBackend.authenticate`` y ``verify_webauthn_credential``, y comparten
la cola en ``_consume_assertion``.
"""
import logging

from django.apps import apps as django_apps
from django.contrib.auth.backends import BaseBackend

from webauthn.helpers.exceptions import InvalidAuthenticationResponse

from addons.authz_passkey.models.auth_passkey_key import PasskeyKey

_logger = logging.getLogger(__name__)


def _consume_assertion(request, passkey, webauthn_response):
    """La cola común de ``_check_credentials`` — ≙ ``res_users.py:56-67``.

    Verifica la aserción contra el reto de la sesión y asienta el nuevo
    ``sign_count``. Devuelve ``True`` si la aserción es válida.

    El contador es lo que impide reproducir una aserción capturada: el
    autenticador lo incrementa en cada uso, y ``verify_auth`` rechaza uno que
    no supere al guardado. Por eso el asiento va **aquí** y no en cada
    llamador — un camino que verificara sin asentar dejaría la passkey
    reutilizable por el mismo valor.
    """
    try:
        new_sign_count = PasskeyKey.verify_auth(
            request, webauthn_response, passkey.public_key,
            passkey.sign_count)
    except InvalidAuthenticationResponse as exc:
        _logger.info('Passkey assertion failed for %r: %s',
                     passkey.user.login, exc)
        return False
    passkey.sign_count = new_sign_count
    passkey.save(update_fields=['sign_count', 'updated_at'])
    return True


def verify_webauthn_credential(user, request, webauthn_response):
    """≙ ``_check_credentials`` tipo ``webauthn`` (``res_users.py:48-72``).

    La passkey se busca **entre las del usuario ya autenticado**, no en todo
    el registro: es la diferencia que separa este camino del login. La fuente
    lo escribe como ``("create_uid", "=", self.env.user.id)`` porque allá el
    dueño es quien la creó; aquí el modelo declara la FK ``user`` explícita
    (``related_name='passkeys'``), que es el mismo predicado con nombre.

    **Divergencia de contrato, no de mecanismo.** La fuente levanta
    ``AccessDenied`` en los dos rechazos —passkey desconocida y aserción
    inválida— y su despachador la convierte en respuesta. Aquí devuelve
    ``None``, que es lo que ``_check_credential`` de ``authz_timeout`` espera
    de ``password`` y ``totp``, y lo que su vista sella como **401
    ``CHECK_IDENTITY_FAILED``**. ``AccessDenied`` es un ``UserError`` de la
    fachada, no una ``APIException``: levantarlo aquí saldría por el manejador
    de DRF sin conversión y el cliente vería un 500 donde le corresponde un
    401.
    """
    if not webauthn_response or request is None:
        return None
    passkey = (
        PasskeyKey.objects
        .select_related('user')
        .filter(user=user, credential_identifier=webauthn_response.get('id'))
        .first()
    )
    if passkey is None:
        # ≙ AccessDenied('Unknown passkey') — contrato local: None.
        _logger.info('Identity check (passkey): unknown passkey for %r',
                     user.login)
        return None
    if not _consume_assertion(request, passkey, webauthn_response):
        return None
    return {'uid': user.pk, 'auth_method': 'passkey', 'mfa': 'skip'}


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
        if not _consume_assertion(request, passkey, webauthn_response):
            return None
        return passkey.user

    def get_user(self, user_id):
        ResUsers = django_apps.get_model('base', 'ResUsers')
        return ResUsers.objects.filter(pk=user_id, active=True).first()
