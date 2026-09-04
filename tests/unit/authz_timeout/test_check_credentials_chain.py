"""Tests — la cadena de ``_check_credentials`` y su envoltorio de traducción.

Dos capas, y el archivo las separa a propósito:

- **La cadena** vive sobre ``res.users`` (#722): ``base`` atiende ``password``
  y es el eslabón **terminal**, y los tres addons de la familia cuelgan encima
  ``totp``, ``totp_mail`` y ``webauthn``. Cada uno atiende su tipo y devuelve
  ``None`` para el resto, que es el relevo perezoso de ``chain_method``
  ocupando el lugar del ``return super()._check_credentials(...)`` de la
  fuente. Se ejercita llamando al método del usuario.
- **El envoltorio** ``_check_credential`` de ``authz_timeout`` sólo traduce el
  rechazo: ``AccessDenied`` es un ``UserError`` de la fachada, no una
  ``APIException``, así que dejarlo salir daría un 500 donde a la vista le
  corresponde el **401 ``CHECK_IDENTITY_FAILED``**.

Lo que se mide es el **despacho** y el **predicado de búsqueda**, no la
criptografía. La capa WebAuthn (``PasskeyKey._verify_auth``) se mockea, igual
que en los tests hermanos de ``authz_passkey``: sus respuestas grabadas están
atadas al rp_id y a los orígenes de la referencia y no son portables.

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


#: El reto vive en la sesión, así que el envoltorio recibe la petición y la
#: pasa por ``env`` al eslabón de passkey. Con ``_verify_auth`` mockeado nada la
#: lee, pero no puede ser ``None``: ese valor es el corto-circuito de "sin
#: sesión".
REQUEST = object()

#: Lo que la cadena recibe del envoltorio. El eslabón de passkey lee de aquí la
#: petición porque la fuente la toma de un hilo-local y este árbol no lo tiene.
ENV = {'interactive': True, 'request': REQUEST}


@pytest.fixture
def owner(db, django_user_model):
    return django_user_model.objects.create_user(
        login='owner@kaupamex.test', password='contraseña-de-prueba')


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

    ``mfa='skip'`` es de la fuente (``:70``) y aquí es correcto: una passkey ya
    prueba posesión y verificación del usuario, así que cuenta como los dos
    factores. Es el **único** de los cuatro tipos que lo declara — ver el caso
    de la métrica más abajo.

    La asimetría ``type='webauthn'`` → ``auth_method='passkey'`` también es de
    la fuente (``:69``); ver :ref:`h-api-779`.
    """
    with patch.object(PasskeyKey, '_verify_auth', return_value=4):
        auth = _check_credential(owner, _credential(), REQUEST)

    assert auth == {'uid': owner.pk, 'auth_method': 'passkey', 'mfa': 'skip'}


# === 2. El control del control — sub-patrón D ===========================

def test_a_passkey_of_another_user_is_rejected(owner, passkey, django_user_model):
    """La passkey EXISTE y no es suya: el rechazo mide el acotamiento.

    Cae si alguien retira ``user=user`` del filtro de
    ``verify_webauthn_credential`` — y entonces cualquiera confirmaría su
    identidad con la passkey de otro, que es el fallo que este caso compra.
    """
    intruder = django_user_model.objects.create_user(login='otro@kaupamex.test')

    with patch.object(PasskeyKey, '_verify_auth', return_value=4) as verify:
        auth = _check_credential(intruder, _credential(), REQUEST)

    assert auth is None
    assert not verify.called, (
        'la passkey ajena no debe llegar siquiera al verificador')


# === 3. La aserción inválida no avanza el contador ======================

def test_an_invalid_assertion_does_not_advance_the_counter(owner, passkey):
    """Contrato del envoltorio: ``None`` es rechazo, no excepción.

    El eslabón levanta ``AccessDenied`` —como la fuente— y el envoltorio lo
    traduce; la vista lee ``None`` y sella 401 ``CHECK_IDENTITY_FAILED``.
    """
    with patch.object(PasskeyKey, '_verify_auth',
                      side_effect=InvalidAuthenticationResponse('mala firma')):
        auth = _check_credential(owner, _credential(), REQUEST)

    assert auth is None
    passkey.refresh_from_db()
    assert passkey.sign_count == 3


# === 4. El contador nuevo se asienta — anti-reproducción ===============

def test_the_new_sign_count_is_persisted(owner, passkey):
    """Sin el asiento, la misma aserción capturada volvería a valer.

    El autenticador incrementa el contador en cada uso y ``_verify_auth``
    rechaza uno que no supere al guardado — pero sólo si el guardado avanzó.
    """
    with patch.object(PasskeyKey, '_verify_auth', return_value=9):
        _check_credential(owner, _credential(), REQUEST)

    passkey.refresh_from_db()
    assert passkey.sign_count == 9


# === 5. La rama totp_mail traduce su excepción al contrato local ========

def test_a_wrong_mail_code_returns_none_instead_of_raising(owner):
    """``AccessDenied`` es un ``UserError``, no una ``APIException``.

    Dejarlo salir del envoltorio da un 500 —el manejador de DRF no lo
    convierte— donde a la vista le corresponde el 401 que ya documenta. El
    rechazo nace en el eslabón de ``authz_totp_mail`` y atraviesa la cadena
    entera sin que ningún otro eslabón lo atienda, que es el contrato.
    """
    with patch('addons.authz_totp_mail.models.res_users.verify_totp_mail_code',
               side_effect=AccessDenied('código incorrecto')):
        auth = _check_credential(
            owner, {'type': 'totp_mail', 'token': '000000'}, REQUEST)

    assert auth is None


# === 6. La contraseña llega al eslabón terminal =========================

def test_the_password_type_reaches_the_terminal_link(owner):
    """Ningún addon de la familia atiende ``password``: la cadena relega.

    Los tres eslabones colgados devuelven ``None`` para un tipo ajeno, así que
    la credencial recorre la pila entera hasta ``base``, que es el terminal.
    Si alguno dejara de relegar —p. ej. con un ``combine`` equivocado— este
    caso cae.
    """
    auth = _check_credential(
        owner, {'type': 'password', 'password': 'contraseña-de-prueba'},
        REQUEST)

    assert auth == {'uid': owner.pk, 'auth_method': 'password',
                    'mfa': 'default'}


def test_a_wrong_password_is_rejected(owner):
    """El tipo es suyo y el valor está mal: rechazo, no relevo."""
    auth = _check_credential(
        owner, {'type': 'password', 'password': 'la-otra'}, REQUEST)

    assert auth is None


# === 7. El tipo desconocido muere en el terminal ========================

def test_an_unknown_credential_type_is_rejected_by_the_terminal_link(owner):
    """≙ ``:351-353`` — el terminal **rechaza**, no releva.

    Es la mitad del contrato que la orquestación a mano no podía expresar: un
    tipo que nadie atiende tiene que morir en el último eslabón. Se mide sobre
    el método del usuario, no sobre el envoltorio, porque el envoltorio traduce
    la excepción a ``None`` y los dos rechazos se verían iguales.
    """
    with pytest.raises(AccessDenied):
        owner._check_credentials({'type': 'inventado', 'token': 'x'}, ENV)

    assert _check_credential(
        owner, {'type': 'inventado', 'token': 'x'}, REQUEST) is None


# === 8. El defecto que este porte corrige — H-API-780 ===================

def test_totp_asks_for_a_second_factor(owner):
    """``mfa='default'``, NO ``'skip'`` — y no es cosmético.

    Su consumidor compara ``auth['mfa'] != 'skip'`` para decidir si exige el
    segundo factor (``ir_http.py``; ≙ ``auth_timeout/models/ir_http.py:106``).
    El despachador a mano devolvía ``'skip'`` para ``totp``, así que esa rama
    estaba **muerta** y la confirmación de dos factores colapsaba a uno.
    """
    with patch('addons.authz_totp.services.verify_code', return_value=True):
        auth = _check_credential(
            owner, {'type': 'totp', 'token': '123456'}, REQUEST)

    assert auth == {'uid': owner.pk, 'auth_method': 'totp', 'mfa': 'default'}
    assert auth['mfa'] != 'skip', (
        'con skip, el candado por tiempo no pide el segundo factor')


def test_totp_mail_asks_for_a_second_factor(owner):
    """Mismo defecto, mismo tipo de eslabón — ≙ ``:154`` de la fuente."""
    with patch('addons.authz_totp_mail.models.res_users.verify_totp_mail_code',
               return_value=None):
        auth = _check_credential(
            owner, {'type': 'totp_mail', 'token': '123456'}, REQUEST)

    assert auth == {'uid': owner.pk, 'auth_method': 'totp_mail',
                    'mfa': 'default'}


def test_only_the_passkey_declares_skip(owner, passkey):
    """El control que separa el defecto de la excepción legítima.

    Si alguien "uniformara" los cuatro tipos a un mismo ``mfa``, o este caso o
    los dos de arriba caen. Sin él, un cambio que devolviera ``'skip'`` en los
    cuatro pasaría por correcto.
    """
    with patch.object(PasskeyKey, '_verify_auth', return_value=4):
        passkey_auth = _check_credential(owner, _credential(), REQUEST)
    password_auth = _check_credential(
        owner, {'type': 'password', 'password': 'contraseña-de-prueba'},
        REQUEST)

    assert passkey_auth['mfa'] == 'skip'
    assert password_auth['mfa'] == 'default'


# === 9. Sin petición, la passkey se rechaza — no releva =================

def test_a_passkey_without_a_request_is_rejected(owner, passkey):
    """El reto vive en la sesión: sin petición no hay nada contra qué medir.

    Devolver ``None`` desde el eslabón haría que la cadena delegara el tipo
    ``webauthn`` a un eslabón que no lo atiende, y el rechazo saldría del
    terminal con el mensaje equivocado.
    """
    with pytest.raises(AccessDenied):
        owner._check_credentials(_credential(), {'interactive': True})
