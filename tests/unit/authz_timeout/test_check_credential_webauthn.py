"""Tests — el despacho por tipo de credencial de la confirmación de identidad.

Lo que se mide es el **predicado de búsqueda**, no la criptografía. La capa
WebAuthn (``PasskeyKey.verify_auth``) se mockea, igual que en los tests
hermanos de ``authz_passkey``: sus respuestas grabadas están atadas al rp_id
y a los orígenes de la referencia y no son portables.

La diferencia entre el login y la confirmación de identidad es una sola línea
de filtro: el login busca la passkey en todo el registro porque el usuario es
desconocido; la confirmación la acota a las del usuario ya autenticado
(``odoo19c: auth_passkey/models/res_users.py:52-55``). El caso 2 es el control
que exige el sub-patrón D de ``metrica-decide-la-conclusion.md``: apunta a una
passkey que **existe**, para que su rechazo sólo pueda venir del acotamiento y
no de la ausencia del objeto.
"""
from unittest.mock import patch

import pytest

from addons.authz_passkey.models.auth_passkey_key import PasskeyKey
from addons.authz_timeout.models.ir_http import _check_credential
from exceptions import AccessDenied

from webauthn.helpers.exceptions import InvalidAuthenticationResponse


#: El reto vive en la sesión, así que el despachador recibe la petición y se
#: la pasa al verificador. Con ``verify_auth`` mockeado nada la lee, pero no
#: puede ser ``None``: ese valor es el corto-circuito de "sin sesión".
REQUEST = object()


@pytest.fixture
def owner(db, django_user_model):
    return django_user_model.objects.create_user(login='owner@kaupamex.test')


@pytest.fixture
def passkey(owner):
    return PasskeyKey.objects.create(
        user=owner, name='llave', credential_identifier='cred-1',
        public_key='pk', sign_count=3)


def _credential(credential_id='cred-1'):
    return {'type': 'webauthn',
            'webauthn_response': {'id': credential_id}}


# === 1. El caso positivo ================================================

def test_a_passkey_of_the_user_confirms_identity(owner, passkey):
    """≙ ``{'uid': …, 'auth_method': 'passkey', 'mfa': 'skip'}``.

    ``mfa='skip'`` es de la fuente: una passkey ya prueba posesión y
    verificación del usuario, así que cuenta como los dos factores.
    """
    with patch.object(PasskeyKey, 'verify_auth', return_value=4):
        auth = _check_credential(owner, _credential(), REQUEST)

    assert auth == {'auth_method': 'passkey', 'mfa': 'skip'}


# === 2. El control del control — sub-patrón D ===========================

def test_a_passkey_of_another_user_is_rejected(owner, passkey, django_user_model):
    """La passkey EXISTE y no es suya: el rechazo mide el acotamiento.

    Cae si alguien retira ``user=user`` del filtro de
    ``verify_webauthn_credential`` — y entonces cualquiera confirmaría su
    identidad con la passkey de otro, que es el fallo que este caso compra.
    """
    intruder = django_user_model.objects.create_user(login='otro@kaupamex.test')

    with patch.object(PasskeyKey, 'verify_auth', return_value=4) as verify:
        auth = _check_credential(intruder, _credential(), REQUEST)

    assert auth is None
    assert not verify.called, (
        'la passkey ajena no debe llegar siquiera al verificador')


# === 3. La aserción inválida no avanza el contador ======================

def test_an_invalid_assertion_does_not_advance_the_counter(owner, passkey):
    """Contrato local: ``None`` es rechazo, no excepción.

    La fuente levanta ``AccessDenied`` y su despachador la convierte; aquí la
    vista lee ``None`` y sella 401 ``CHECK_IDENTITY_FAILED``.
    """
    with patch.object(PasskeyKey, 'verify_auth',
                      side_effect=InvalidAuthenticationResponse('mala firma')):
        auth = _check_credential(owner, _credential(), REQUEST)

    assert auth is None
    passkey.refresh_from_db()
    assert passkey.sign_count == 3


# === 4. El contador nuevo se asienta — anti-reproducción ===============

def test_the_new_sign_count_is_persisted(owner, passkey):
    """Sin el asiento, la misma aserción capturada volvería a valer.

    El autenticador incrementa el contador en cada uso y ``verify_auth``
    rechaza uno que no supere al guardado — pero sólo si el guardado avanzó.
    """
    with patch.object(PasskeyKey, 'verify_auth', return_value=9):
        _check_credential(owner, _credential(), REQUEST)

    passkey.refresh_from_db()
    assert passkey.sign_count == 9


# === 5. La rama totp_mail traduce su excepción al contrato local ========

def test_a_wrong_mail_code_returns_none_instead_of_raising(owner):
    """``AccessDenied`` es un ``UserError``, no una ``APIException``.

    Dejarlo salir del despachador da un 500 —el manejador de DRF no lo
    convierte— donde a la vista le corresponde el 401 que ya documenta. Las
    ramas ``password`` y ``totp`` devuelven ``None``; ésta se alinea.
    """
    with patch('addons.authz_timeout.models.ir_http.verify_totp_mail_code',
               side_effect=AccessDenied('código incorrecto')):
        auth = _check_credential(
            owner, {'type': 'totp_mail', 'token': '000000'}, REQUEST)

    assert auth is None
