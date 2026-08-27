"""Tests — el segundo paso del login y la cookie ``td_id``.

Contrato adaptado de ``odoo19c: addons/auth_totp/controllers/home.py::web_totp``
(``odoo-tools@622ddc2a``), con las dos divergencias que el endpoint declara: la
fuente **redirige** y renderiza un formulario; aquí el cliente es REST, así que
el desenlace es un código y un cuerpo.

Lo que estos casos miden es el ciclo completo que ``H-API-772`` dejó abierto:
nadie ponía ni leía la cookie. Por eso el eje central no es "el endpoint
responde 200" sino **que la cookie emitida sirva para saltarse el segundo paso
la próxima vez, y sólo a su dueño**.

Los controles que exige el sub-patrón D de ``metrica-decide-la-conclusion.md``
—cada uno declara qué lo haría fallar—:

``TestTrustedDeviceCookie.test_cookie_of_another_user_does_not_skip``
    El caso hermano afirma que una cookie válida abre sesión sin código. Un
    verde ahí no distingue *"comprueba de quién es la clave"* de *"acepta
    cualquier clave que exista"*. Éste presenta **la misma cookie**, emitida de
    verdad, en la sesión parcial de **otro** usuario, y exige que el segundo
    paso se siga pidiendo. Es lo único que separa las dos lecturas, y es el
    argumento del ``uid`` de ``_check_credentials_for_uid``.

``TestFinalize.test_partial_keys_do_not_survive_login``
    ``login()`` de Django **preserva** los datos de una sesión anónima al
    ciclar la clave. Sin el ``pop`` explícito de ``_finalize`` las dos claves
    parciales sobreviven a la sesión ya abierta, y nada en un 200 lo delata.

``TestRemember.test_expiry_exceeds_the_default_api_key_cap``
    ``_check_expiration_date`` tope la caducidad al máximo del grupo, que por
    defecto es **1.0 día**, salvo con privilegio. Los 90 días del dispositivo
    lo exceden por construcción: si el ``sudo()`` desapareciera, este caso cae
    con ``ValidationError`` y ninguno de los otros lo notaría.
"""
import base64
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from addons.authz_totp.models.auth_totp import (
    TRUSTED_DEVICE_COOKIE, AuthTotpDevice)
from addons.authz_totp.models.totp import TOTP, TIMESTEP, hotp
from addons.authz_totp.services import begin_setup, confirm_setup

User = get_user_model()

pytestmark = pytest.mark.integration

AUTHENTICATE = '/api/v2/web/session/authenticate/'
SESSION      = '/api/v2/web/session/'
TOTP_LOGIN   = '/api/v2/authz/totp/login/'

PASSWORD = 'SegundoPaso123!'


def _current_code(secret, offset=0):
    """El código del intervalo actual desplazado ``offset`` pasos."""
    key = base64.b32decode(secret)
    counter = int(timezone.now().timestamp()) // TIMESTEP + offset
    return f'{hotp(key, counter):06d}'


def _enable_totp(user):
    """Deja al usuario con 2FA activo y devuelve ``(secret, recovery_codes)``.

    El alta usa el código del intervalo **anterior**, no el actual. Desde
    H-API-776 el contador del alta se asienta (≙ ``_totp_try_setting``,
    ``odoo19c: auth_totp/models/res_users.py:110``), así que reusar el mismo
    código para el login siguiente es exactamente la repetición que la fuente
    prohíbe — y es lo que un usuario real tampoco hace: teclea el que ve, y el
    segundo paso llega después.
    """
    secret, _uri = begin_setup(user)
    recovery = confirm_setup(user, _current_code(secret, offset=-1))
    assert recovery, 'el alta de 2FA no se confirmó'
    return secret, recovery


@pytest.fixture
def totp_user(db):
    user = User.objects.create_user(
        login='segundo.paso@practicayoruba.mx',
        password=PASSWORD,
        name='Usuario Con Segundo Factor',
    )
    user.totp_secret_value, user.recovery_codes = _enable_totp(user)
    return user


@pytest.fixture
def partial_session(api_client, totp_user):
    """Deja al cliente con la sesión **parcial** que el 401 de MFA produce."""
    r = api_client.post(
        AUTHENTICATE,
        {'login': totp_user.login, 'password': PASSWORD},
        format='json')
    assert r.status_code == 401
    assert r.data['codigo_error'] == 'MFA_REQUIRED'
    return api_client


class TestPartialSession:
    """El corte del login — ≙ ``odoo19c: odoo/http.py:1250-1258``."""

    def test_credential_alone_does_not_open_session(self, partial_session):
        """La credencial correcta NO abre sesión mientras haya segundo factor.

        Es la mitad que ``session_authenticate`` aporta al ciclo: sin ella el
        segundo paso sería decorativo.
        """
        assert partial_session.get(SESSION).status_code in (401, 403)

    def test_mfa_url_points_at_the_second_step_screen(
            self, api_client, totp_user):
        r = api_client.post(
            AUTHENTICATE,
            {'login': totp_user.login, 'password': PASSWORD},
            format='json')
        assert r.data['mfa_url'] == '/login/totp'

    def test_without_partial_session_the_second_step_refuses(self, api_client):
        r = api_client.post(TOTP_LOGIN, {'code': '000000'}, format='json')
        assert r.status_code == 401
        assert r.data['codigo_error'] == 'NO_PARTIAL_SESSION'


class TestCode:
    """El POST del código — ≙ ``:42-57``."""

    def test_valid_code_opens_session(self, partial_session, totp_user):
        r = partial_session.post(
            TOTP_LOGIN,
            {'code': _current_code(totp_user.totp_secret_value)},
            format='json')
        assert r.status_code == 200
        assert r.data['uid'] == totp_user.pk
        # El cuerpo es el mismo que habría devuelto `session_authenticate`.
        assert r.data['login'] == totp_user.login
        assert partial_session.get(SESSION).status_code == 200

    def test_recovery_code_opens_session(self, partial_session, totp_user):
        """Divergencia declarada: la fuente sólo admite el código de la app."""
        r = partial_session.post(
            TOTP_LOGIN, {'code': totp_user.recovery_codes[0]}, format='json')
        assert r.status_code == 200
        assert r.data['uid'] == totp_user.pk

    def test_recovery_code_is_single_use(self, partial_session, totp_user):
        code = totp_user.recovery_codes[0]
        assert partial_session.post(
            TOTP_LOGIN, {'code': code}, format='json').status_code == 200
        partial_session.logout()
        partial_session.post(
            AUTHENTICATE,
            {'login': totp_user.login, 'password': PASSWORD},
            format='json')
        r = partial_session.post(TOTP_LOGIN, {'code': code}, format='json')
        assert r.status_code == 401
        assert r.data['codigo_error'] == 'TOTP_INVALID'

    def test_wrong_code_keeps_the_session_partial(self, partial_session,
                                                  totp_user):
        r = partial_session.post(TOTP_LOGIN, {'code': '000000'}, format='json')
        assert r.status_code == 401
        assert r.data['codigo_error'] == 'TOTP_INVALID'
        # Sigue a medias: el reintento con el código bueno debe funcionar.
        ok = partial_session.post(
            TOTP_LOGIN,
            {'code': _current_code(totp_user.totp_secret_value)},
            format='json')
        assert ok.status_code == 200


class TestFinalize:
    """≙ ``request.session.finalize(env)`` (``odoo19c: odoo/http.py:1265``)."""

    def test_partial_keys_do_not_survive_login(self, partial_session,
                                               totp_user):
        """CONTROL — ``login()`` cicla la clave pero conserva los datos.

        Qué lo haría fallar: retirar los dos ``pop`` de ``_finalize``. Sin
        ellos ``pre_uid`` sigue en la sesión ya abierta, y una petición
        posterior volvería a entrar por la rama del segundo paso.
        """
        partial_session.post(
            TOTP_LOGIN,
            {'code': _current_code(totp_user.totp_secret_value)},
            format='json')
        assert 'pre_uid' not in partial_session.session
        assert 'pre_login' not in partial_session.session

    def test_second_step_on_an_open_session_is_a_no_op(self, partial_session,
                                                       totp_user):
        """≙ ``if request.session.uid: redirect(...)`` (``:24-25``)."""
        partial_session.post(
            TOTP_LOGIN,
            {'code': _current_code(totp_user.totp_secret_value)},
            format='json')
        r = partial_session.get(TOTP_LOGIN)
        assert r.status_code == 200
        assert r.data['uid'] == totp_user.pk


class TestRemember:
    """``remember`` → ``_generate`` + ``set_cookie`` — ≙ ``:59-81``."""

    def test_without_remember_no_cookie_and_no_device(self, partial_session,
                                                      totp_user):
        r = partial_session.post(
            TOTP_LOGIN,
            {'code': _current_code(totp_user.totp_secret_value)},
            format='json')
        assert TRUSTED_DEVICE_COOKIE not in r.cookies
        assert not AuthTotpDevice.objects.filter(user_id=totp_user.pk).exists()

    def test_remember_emits_the_cookie_and_the_device(self, partial_session,
                                                      totp_user):
        r = partial_session.post(
            TOTP_LOGIN,
            {'code': _current_code(totp_user.totp_secret_value),
             'remember': True},
            format='json')
        assert r.status_code == 200
        cookie = r.cookies[TRUSTED_DEVICE_COOKIE]
        assert cookie.value
        # La fuente fija las dos, y por eso se comprueban: sin `httponly` la
        # clave queda al alcance de cualquier script de la página.
        assert cookie['httponly']
        assert cookie['samesite'] == 'Lax'
        assert AuthTotpDevice.objects.filter(
            user_id=totp_user.pk, scope='browser').count() == 1

    def test_expiry_exceeds_the_default_api_key_cap(self, partial_session,
                                                    totp_user):
        """CONTROL — los 90 días sólo caben con privilegio.

        Qué lo haría fallar: retirar el ``sudo()`` del bloque de ``remember``.
        ``_check_expiration_date`` tope la caducidad al máximo declarado por
        los grupos del actor, y **sin ninguno el tope es 1.0 día**, así que la
        generación levantaría ``ValidationError``. Ningún otro caso lo mide:
        los demás sólo miran que haya cookie.
        """
        partial_session.post(
            TOTP_LOGIN,
            {'code': _current_code(totp_user.totp_secret_value),
             'remember': True},
            format='json')
        device = AuthTotpDevice.objects.get(user_id=totp_user.pk)
        assert device.expiration_date > timezone.now() + timedelta(days=2)


class TestTrustedDeviceCookie:
    """La vía del GET — ≙ ``:31-40``, la razón de ser de #727."""

    def _remembered_cookie(self, api_client, totp_user):
        api_client.post(
            AUTHENTICATE,
            {'login': totp_user.login, 'password': PASSWORD},
            format='json')
        r = api_client.post(
            TOTP_LOGIN,
            {'code': _current_code(totp_user.totp_secret_value),
             'remember': True},
            format='json')
        return r.cookies[TRUSTED_DEVICE_COOKIE].value

    def test_get_without_cookie_asks_for_the_code(self, partial_session):
        r = partial_session.get(TOTP_LOGIN)
        assert r.status_code == 401
        assert r.data['codigo_error'] == 'TRUSTED_DEVICE_REQUIRED'

    def test_remembered_cookie_skips_the_second_step(self, api_client,
                                                     totp_user):
        """El ciclo completo: la cookie emitida vale en el login siguiente."""
        key = self._remembered_cookie(api_client, totp_user)
        api_client.logout()
        api_client.cookies[TRUSTED_DEVICE_COOKIE] = key
        api_client.post(
            AUTHENTICATE,
            {'login': totp_user.login, 'password': PASSWORD},
            format='json')
        r = api_client.get(TOTP_LOGIN)
        assert r.status_code == 200
        assert r.data['uid'] == totp_user.pk
        assert api_client.get(SESSION).status_code == 200

    def test_cookie_of_another_user_does_not_skip(self, api_client, totp_user,
                                                  django_user_model):
        """CONTROL — la clave es de su dueño, no de quien la presente.

        Qué lo haría fallar: que ``_check_credentials_for_uid`` dejara de
        comparar el ``uid``. La cookie es **real y vigente** —la emitió el
        caso hermano—, así que un endpoint que sólo comprobara existencia
        abriría aquí la sesión del usuario equivocado.
        """
        key = self._remembered_cookie(api_client, totp_user)
        api_client.logout()

        intruder = django_user_model.objects.create_user(
            login='intruso@practicayoruba.mx',
            password=PASSWORD,
            name='Usuario Distinto',
        )
        intruder.totp_secret_value, _ = _enable_totp(intruder)

        api_client.cookies[TRUSTED_DEVICE_COOKIE] = key
        api_client.post(
            AUTHENTICATE,
            {'login': intruder.login, 'password': PASSWORD},
            format='json')
        r = api_client.get(TOTP_LOGIN)
        assert r.status_code == 401
        assert r.data['codigo_error'] == 'TRUSTED_DEVICE_REQUIRED'

    def test_a_bogus_cookie_asks_for_the_code(self, partial_session):
        partial_session.cookies[TRUSTED_DEVICE_COOKIE] = 'no-es-una-clave'
        r = partial_session.get(TOTP_LOGIN)
        assert r.status_code == 401
        assert r.data['codigo_error'] == 'TRUSTED_DEVICE_REQUIRED'
