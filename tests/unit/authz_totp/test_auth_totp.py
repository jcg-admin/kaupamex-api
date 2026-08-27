"""Tests — ``auth_totp.device``, el dispositivo de confianza del segundo factor.

Adaptación del contrato que ``odoo19c: auth_totp/models/auth_totp.py`` fija en
sus dos métodos, más la propiedad que su comentario de cabecera declara y que
ningún método expresa:

    # init is overriden in res.users.apikeys to create a secret column 'key'
    # use a different model to benefit from the secured methods while not mixing
    # two different concepts

*"while not mixing two different concepts"* es una afirmación **verificable**:
una clave de API no vale como dispositivo de confianza, y al revés. Los casos 1
y 2 la miden; sin ellos, el porte pasaría igual con las dos filas en la misma
tabla y nadie lo notaría hasta que revocar una cosa revocara la otra.

**El caso 4 es el control que exige el sub-patrón D de
``metrica-decide-la-conclusion.md``.** El 3 afirma que
``_check_credentials_for_uid`` acepta la clave de su dueño; un verde ahí no
distingue «comprueba el uid» de «devuelve verdadero cuando la clave existe».
El 4 presenta la **misma clave válida** con el uid de otro usuario y exige
falso — es lo único que separa las dos lecturas.
"""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from addons.authz_totp.models.auth_totp import (
    TRUSTED_DEVICE_AGE_DAYS, AuthTotpDevice, revoke_all_devices)
from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.res_users import ResUsersApikeys
from orm.environments import user_scope

User = get_user_model()

pytestmark = pytest.mark.django_db

#: El parámetro que la fuente lee en ``_get_trusted_device_age`` (``:27``).
PARAM = 'auth_totp.trusted_device_age'


@pytest.fixture
def user():
    return User.objects.create_user(
        login='confianza@practicayoruba.mx',
        password='ConfianzaPass123!',
        name='Duena del Dispositivo',
    )


@pytest.fixture
def other_user():
    return User.objects.create_user(
        login='ajena@practicayoruba.mx',
        password='AjenaPass123!',
        name='Usuaria Ajena',
    )


def _generate_for(model, user, scope='browser'):
    """Genera una clave de ``model`` actuando como ``user``.

    ``_generate`` toma al actor del contexto — ≙ ``self.env.user`` — así que el
    caso lo fija con ``user_scope`` en vez de pasarlo, que es el mecanismo real.
    """
    with user_scope(user.pk):
        return model._generate(scope, 'de prueba',
                               timezone.now() + timedelta(hours=1))


# === 1-2. Los dos conceptos NO se mezclan ================================

def test_the_device_key_lands_on_its_own_table(user):
    """≙ ``_name`` propio con ``_inherit`` — herencia por prototipo.

    La forma Django del prototipo es la base abstracta
    ``_ResUsersApikeysBase``; lo que esto mide es su consecuencia observable:
    la fila cae en ``auth_totp_device`` y **no** en ``res_users_apikeys``.
    """
    _generate_for(AuthTotpDevice, user)

    assert AuthTotpDevice.objects.filter(user=user).count() == 1
    assert ResUsersApikeys.objects.filter(user=user).count() == 0


def test_a_trusted_device_is_not_an_api_key(user):
    """Un dispositivo de confianza NO autentica una llamada RPC.

    Es la mitad que el comentario de la fuente promete y que ningún método
    suyo enuncia. Los métodos heredados son ``classmethod`` precisamente para
    esto: ``cls`` es el modelo sobre el que se invocan, así que
    ``ResUsersApikeys._check_credentials`` sólo mira su propia tabla.
    """
    key = _generate_for(AuthTotpDevice, user)

    assert AuthTotpDevice._check_credentials(scope='browser', key=key) == user.pk
    assert ResUsersApikeys._check_credentials(scope='browser', key=key) is None


def test_an_api_key_is_not_a_trusted_device(user):
    """Y el reverso: revocar una cosa no puede revocar la otra."""
    key = _generate_for(ResUsersApikeys, user)

    assert ResUsersApikeys._check_credentials(scope='browser', key=key) == user.pk
    assert AuthTotpDevice._check_credentials(scope='browser', key=key) is None


# === 3-4. _check_credentials_for_uid, con su control ====================

def test_the_owner_uid_passes(user):
    """≙ ``_check_credentials_for_uid`` (``:20-23``)."""
    key = _generate_for(AuthTotpDevice, user)

    assert AuthTotpDevice._check_credentials_for_uid(
        scope='browser', key=key, uid=user.pk) is True


def test_a_valid_key_of_another_user_does_not_pass(user, other_user):
    """CONTROL del sub-patrón D — la clave es válida; el uid, ajeno.

    Sin la comparación ``== uid``, una cookie de confianza legítima de otro
    usuario pasaría el segundo factor del que se está autenticando. El caso 3
    seguiría en verde: por eso este existe.
    """
    key = _generate_for(AuthTotpDevice, user)

    assert AuthTotpDevice._check_credentials_for_uid(
        scope='browser', key=key, uid=other_user.pk) is False


def test_a_missing_uid_is_rejected_loudly(user):
    """≙ ``assert uid, 'uid is required'`` (``:21``).

    La fuente falla ruidoso en vez de devolver falso: un ``uid`` vacío es un
    error de quien llama, no una credencial que no cuadra.
    """
    key = _generate_for(AuthTotpDevice, user)

    with pytest.raises(AssertionError):
        AuthTotpDevice._check_credentials_for_uid(
            scope='browser', key=key, uid=None)


# === 5-8. _get_trusted_device_age =======================================

def test_the_default_age_is_ninety_days_in_seconds():
    """≙ ``TRUSTED_DEVICE_AGE_DAYS`` sin parámetro puesto (``:29``)."""
    assert AuthTotpDevice._get_trusted_device_age() == (
        TRUSTED_DEVICE_AGE_DAYS * 86400)


def test_the_parameter_overrides_the_default():
    SystemParameter.set_param(PARAM, '7')

    assert AuthTotpDevice._get_trusted_device_age() == 7 * 86400


@pytest.mark.parametrize('bad', ['no-es-un-numero', '0', '-3'])
def test_an_invalid_value_falls_back_to_the_default(bad):
    """≙ las dos ramas que la fuente colapsa en el mismo desenlace (``:30-36``).

    Un valor no numérico (``ValueError``) y uno ``<= 0`` degradan a 90 días.
    Los tres casos entran por caminos distintos y salen por el mismo.
    """
    SystemParameter.set_param(PARAM, bad)

    assert AuthTotpDevice._get_trusted_device_age() == (
        TRUSTED_DEVICE_AGE_DAYS * 86400)


# === 9-11. revoke_all_devices ===========================================

def test_revoking_removes_only_the_devices_of_that_user(user, other_user):
    """≙ ``_revoke_all_devices`` (``:209-210``)."""
    _generate_for(AuthTotpDevice, user)
    _generate_for(AuthTotpDevice, user)
    _generate_for(AuthTotpDevice, other_user)

    assert revoke_all_devices(user) == 2

    assert AuthTotpDevice.objects.filter(user=user).count() == 0
    assert AuthTotpDevice.objects.filter(user=other_user).count() == 1


def test_revoking_does_not_touch_the_api_keys(user):
    """La otra mitad de *"not mixing two different concepts"*.

    Es el escenario concreto que compartir tabla habría roto: cerrar sesión en
    todos los navegadores no puede tumbar las integraciones externas.
    """
    _generate_for(AuthTotpDevice, user)
    _generate_for(ResUsersApikeys, user)

    revoke_all_devices(user)

    assert ResUsersApikeys.objects.filter(user=user).count() == 1


def test_revoking_without_an_actor_is_a_noop(user):
    """Sin usuario en el contexto no hay a quién revocarle nada.

    Devuelve 0 en vez de barrer la tabla — el modo de fallo que un
    ``filter(user_id=None).delete()`` habría tenido.
    """
    _generate_for(AuthTotpDevice, user)

    assert revoke_all_devices() == 0
    assert AuthTotpDevice.objects.filter(user=user).count() == 1
