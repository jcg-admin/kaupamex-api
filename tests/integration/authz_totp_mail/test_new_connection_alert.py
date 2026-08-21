"""Tests — el aviso de conexión desde un dispositivo nuevo.

Contrato adaptado de ``odoo19c: auth_totp_mail/models/res_users.py:50-67``
(``_notify_security_new_connection``) y de su llamador, el ``authenticate`` que
ese mismo addon envuelve (``:44-48``). Docstring de la fuente, verbatim: *"Send
an alert on new connection. 2FA enabled -> only for new device. Not enabled ->
no alert"*.

Aquí el llamador es ``session_authenticate`` —una vista DRF, que no se
encadena— y la costura es el tercer eslabón vacío que ``base`` declara junto a
``_mfa_type``/``_mfa_url``. Las tres divergencias están declaradas en sus
docstrings; lo que estos casos miden es el **mecanismo**, no la costura.

Los controles que exige el sub-patrón D de ``metrica-decide-la-conclusion.md``
—cada uno declara qué lo haría fallar—:

``test_alert_fires_before_the_second_factor_answers``
    El eje entero. Un caso que sólo mirara "hay correo al terminar el login" no
    distingue *"avisa cuando la credencial acierta"* de *"avisa cuando la
    sesión se abre"*. Éste afirma que el correo **ya está** en el 401 de
    ``MFA_REQUIRED``, con el segundo paso todavía sin responder: mover el
    gancho a ``totp_login`` lo deja mudo justo ante quien tiene la contraseña
    y no el segundo factor, que es de quien el aviso protege.

``test_remembered_cookie_silences_the_alert``
    Qué lo haría fallar: retirar la rama de la cookie. Sin ella cada login
    desde el mismo navegador avisaría, y el aviso dejaría de significar
    "dispositivo nuevo" para significar "hubo login".

``test_cookie_of_another_user_still_alerts``
    Qué lo haría fallar: que la comprobación dejara de pasar ``uid``. La cookie
    es **real y vigente** —la emitió el caso hermano—, así que una comprobación
    de mera existencia silenciaría el aviso del usuario equivocado, que es
    exactamente la situación que el aviso existe para delatar.

``test_without_mfa_there_is_no_alert``
    Es el *"Not enabled -> no alert"* de la fuente. Qué lo haría fallar:
    retirar la guarda ``self._mfa_type()``. Ningún otro caso lo mide — todos
    los demás corren con 2FA activo.

``test_wrong_credential_does_not_alert``
    Qué lo haría fallar: subir la llamada por encima del ``if user is None``.
    Un aviso ahí convertiría el correo del titular en un oráculo de qué logins
    existen, que es lo que ese 401 de código único evita.
"""
import base64

import pytest
from django.contrib.auth import get_user_model
from django.core import mail as django_mail
from django.utils import timezone

from addons.authz_totp.models.auth_totp import TRUSTED_DEVICE_COOKIE
from addons.authz_totp.models.totp import TIMESTEP, hotp
from addons.authz_totp.services import begin_setup, confirm_setup
from addons.authz_totp_mail.data import seed as seed_totp_mail
from addons.authz_totp_mail.models.res_users import NEW_CONNECTION_SUBJECT

User = get_user_model()

pytestmark = pytest.mark.integration

AUTHENTICATE = '/api/v2/web/session/authenticate/'
TOTP_LOGIN = '/api/v2/authz/totp/login/'

PASSWORD = 'DispositivoNuevo123!'


def _current_code(secret, offset=0):
    """El código del intervalo actual desplazado ``offset`` pasos."""
    key = base64.b32decode(secret)
    counter = int(timezone.now().timestamp()) // TIMESTEP + offset
    return f'{hotp(key, counter):06d}'


def _with_totp(login, name):
    """Crea un usuario con 2FA de app confirmado y devuelve ``(user, secret)``.

    El alta dispara la señal *"2FA Activated"* de este mismo addon, así que la
    bandeja se vacía antes de devolver: lo que cada caso mide es el aviso de
    conexión, no el de activación.
    """
    user = User.objects.create_user(login=login, password=PASSWORD, name=name)
    secret, _uri = begin_setup(user)
    # Con el código del intervalo anterior: desde H-API-776 el alta asienta
    # su contador, y el login siguiente necesita uno más nuevo.
    assert confirm_setup(user, _current_code(secret, offset=-1)), \
        'el alta de 2FA falló'
    django_mail.outbox.clear()
    return user, secret


def _new_connection_alerts():
    """Los correos de la bandeja que son el aviso de conexión, y sólo ésos."""
    return [m for m in django_mail.outbox
            if m.subject == NEW_CONNECTION_SUBJECT]


@pytest.fixture
def totp_user(db):
    seed_totp_mail()
    user, secret = _with_totp('nuevo.dispositivo@practicayoruba.mx',
                              'Usuario Con Segundo Factor')
    user.totp_secret_value = secret
    return user


def _remembered_cookie(api_client, user):
    """Completa un login con ``remember`` y devuelve la clave de la cookie."""
    api_client.post(
        AUTHENTICATE, {'login': user.login, 'password': PASSWORD},
        format='json')
    r = api_client.post(
        TOTP_LOGIN,
        {'code': _current_code(user.totp_secret_value), 'remember': True},
        format='json')
    key = r.cookies[TRUSTED_DEVICE_COOKIE].value
    api_client.logout()
    django_mail.outbox.clear()
    return key


class TestNewConnectionAlert:
    """≙ ``_notify_security_new_connection`` (``:50-67``)."""

    def test_alert_fires_before_the_second_factor_answers(self, api_client,
                                                          totp_user):
        """CONTROL — el momento es la mitad del mecanismo.

        La fuente lo cuelga de ``authenticate``, no del final del login. El
        aviso tiene que estar puesto **con la sesión todavía parcial**.
        """
        r = api_client.post(
            AUTHENTICATE, {'login': totp_user.login, 'password': PASSWORD},
            format='json')
        assert r.status_code == 401
        assert r.data['codigo_error'] == 'MFA_REQUIRED'

        alerts = _new_connection_alerts()
        assert len(alerts) == 1
        # El correo es el `login`: este árbol no declara un campo `email`
        # aparte, igual que en `send_totp_mail_code` y en `../signals.py`.
        assert alerts[0].to == [totp_user.login]

    def test_remembered_cookie_silences_the_alert(self, api_client, totp_user):
        """El dispositivo ya recordado no es nuevo — la fuente tampoco avisa."""
        api_client.cookies[TRUSTED_DEVICE_COOKIE] = _remembered_cookie(
            api_client, totp_user)
        api_client.post(
            AUTHENTICATE, {'login': totp_user.login, 'password': PASSWORD},
            format='json')
        assert _new_connection_alerts() == []

    def test_cookie_of_another_user_still_alerts(self, api_client, totp_user):
        """CONTROL — la clave es de su dueño, no de quien la presente."""
        key = _remembered_cookie(api_client, totp_user)
        intruder, secret = _with_totp('intruso.aviso@practicayoruba.mx',
                                      'Usuario Distinto')
        intruder.totp_secret_value = secret

        api_client.cookies[TRUSTED_DEVICE_COOKIE] = key
        api_client.post(
            AUTHENTICATE, {'login': intruder.login, 'password': PASSWORD},
            format='json')

        alerts = _new_connection_alerts()
        assert len(alerts) == 1
        assert alerts[0].to == [intruder.login]

    def test_without_mfa_there_is_no_alert(self, api_client, db):
        """≙ *"Not enabled -> no alert"* — la tercera guarda de la fuente."""
        seed_totp_mail()
        plain = User.objects.create_user(
            login='sin.segundo.factor@practicayoruba.mx',
            password=PASSWORD, name='Usuario Sin Segundo Factor')
        r = api_client.post(
            AUTHENTICATE, {'login': plain.login, 'password': PASSWORD},
            format='json')
        assert r.status_code == 200  # sin 2FA la sesión se abre de una vez
        assert _new_connection_alerts() == []

    def test_wrong_credential_does_not_alert(self, api_client, totp_user):
        """CONTROL — el aviso vive DESPUÉS de aceptar la credencial."""
        r = api_client.post(
            AUTHENTICATE,
            {'login': totp_user.login, 'password': 'no-es-la-contrasena'},
            format='json')
        assert r.status_code == 401
        assert r.data['codigo_error'] == 'INVALID_CREDENTIAL'
        assert _new_connection_alerts() == []
