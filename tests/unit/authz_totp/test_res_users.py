"""Tests — la cadena de tres eslabones de ``_mfa_type`` / ``_mfa_url``.

La referencia declara el mismo método en tres archivos distintos y cada uno
consulta ``super()`` **primero**::

    base (None) → auth_totp ('totp') → auth_totp_mail ('totp_mail')

Con ese idioma la precedencia la gana el eslabón **más interno**, y el orden lo
fija la cadena de ``depends``. Aquí eso se expresa con
``combine=keep_previous`` (``orm.method_chain``), porque el relevo por defecto
de ``chain_method`` da la precedencia contraria.

**Por qué la cadena entera se prueba desde aquí** y no repartida entre
``authz_totp`` y ``authz_totp_mail``: el caso 4 —el usuario que tiene los dos
métodos disponibles— sólo existe con los dos eslabones vivos. Un control
partido en dos módulos deja de ser un control.

La referencia **no** prueba estos métodos: su única mención en los tests es un
``patch.object(..., '_mfa_type', lambda u: 'totp')``
(``odoo19c: auth_totp_mail/tests/test_auth_signup.py:79``). Los casos de abajo
son propios.

El caso 6 es el que exige el sub-patrón D de
``metrica-decide-la-conclusion.md``: reinstala el eslabón externo con el relevo
**por defecto** y comprueba que el veredicto se invierte. Sin él, el verde del
caso 4 no distingue «la precedencia es la de la fuente» de «el usuario nunca
tuvo los dos métodos a la vez».
"""
import pytest

from orm.method_chain import chain_method

from addons.authz_totp.models import TotpSecret
from addons.authz_totp_mail.models.res_users import (
    PARAM_TOTP_POLICY,
    totp_mail_policy_applies,
)
from addons.base.models import SystemParameter
from addons.base.models.res_groups import ResGroups
from addons.base.models.res_users import ResUsers

pytestmark = pytest.mark.django_db

TOTP_URL = '/login/totp'


@pytest.fixture
def user():
    return ResUsers.objects.create_user(
        login='mfa-chain@kaupamex.mx', password='Str0ng-Passw0rd!')


def _enable_app_totp(user):
    """El usuario tiene la app de 2FA configurada y confirmada."""
    TotpSecret.objects.create(
        user=user, secret='JBSWY3DPEHPK3PXP', confirmed=True)


def _set_policy(value):
    """Fija la política L2 que gobierna el fallback por correo."""
    SystemParameter.set_param(PARAM_TOTP_POLICY, value)


def _mfa_type_default_relay(self):
    """Mismo cuerpo que el eslabón externo, otro objeto de función.

    Lo consume el control del caso 6. ``chain_method`` es idempotente por
    identidad —reinstalar la misma función sería un no-op—, así que el control
    necesita una distinta para poder encadenarla con el relevo por defecto.
    """
    if totp_mail_policy_applies(self):
        return 'totp_mail'


# === 1. Sin ningún método activo: el eslabón base es el que responde =====

def test_chain_returns_none_without_any_second_factor(user):
    _set_policy('')
    assert user._mfa_type() is None
    assert user._mfa_url() is None


def test_unconfirmed_secret_does_not_activate_the_second_factor(user):
    TotpSecret.objects.create(
        user=user, secret='JBSWY3DPEHPK3PXP', confirmed=False)
    _set_policy('')
    assert user._mfa_type() is None


# === 2. Eslabón medio — la app de 2FA ====================================

def test_configured_app_yields_totp(user):
    _enable_app_totp(user)
    _set_policy('')
    assert user._mfa_type() == 'totp'
    assert user._mfa_url() == TOTP_URL


# === 3. Eslabón externo — el fallback por correo =========================

def test_all_required_policy_without_app_yields_totp_mail(user):
    _set_policy('all_required')
    assert user._mfa_type() == 'totp_mail'
    assert user._mfa_url() == TOTP_URL


def test_employee_required_policy_only_reaches_internal_users(user):
    _set_policy('employee_required')
    assert user._mfa_type() is None, 'sin grupo interno la política no aplica'

    internal = ResGroups.objects.create(
        name='Empleados', user_type=ResGroups.USER_TYPE_INTERNAL)
    internal.user_ids.add(user)
    assert user._mfa_type() == 'totp_mail'


# === 4. La precedencia: el eslabón INTERNO gana ==========================

def test_app_and_policy_together_yield_totp(user):
    """El caso que la fuente resuelve consultando ``super()`` primero.

    Los dos métodos están disponibles: la app está confirmada **y** la política
    exige 2FA. La referencia devuelve ``'totp'`` porque ``auth_totp_mail``
    depende de ``auth_totp`` y por tanto se instala después.
    """
    _enable_app_totp(user)
    _set_policy('all_required')
    assert user._mfa_type() == 'totp'
    assert user._mfa_url() == TOTP_URL


# === 5. El consumidor: authz_timeout lee el resultado ====================

def test_get_auth_methods_consumes_the_chain(user):
    """``_get_auth_methods`` de ``authz_timeout`` no sabe cuántos eslabones hay."""
    _enable_app_totp(user)
    _set_policy('')
    assert user._get_auth_methods() == ['totp', 'password']

    TotpSecret.objects.filter(user=user).delete()
    assert user._get_auth_methods() == ['password']


# === 6. El control — sin ``keep_previous`` la precedencia se invierte ====

def test_default_relay_would_invert_the_precedence(user):
    """Control del sub-patrón D: mide qué haría fallar al caso 4.

    Encadena un eslabón de correo con el relevo **por defecto** de
    ``chain_method`` —el que da la precedencia al que se instala después— y
    comprueba que el mismo usuario del caso 4 pasa a ``'totp_mail'``.

    Mismo usuario, mismos datos, único cambio el ``combine``: eso es lo que
    hace del caso 4 un control y no un adorno. Si alguien retira el
    ``keep_previous`` de producción el caso 4 se pone rojo, y este caso
    demuestra que ese rojo es alcanzable.
    """
    _enable_app_totp(user)
    _set_policy('all_required')
    assert user._mfa_type() == 'totp', 'precondición: la cadena real da totp'

    original = ResUsers.__dict__['_mfa_type']
    try:
        chain_method(ResUsers, '_mfa_type', _mfa_type_default_relay)
        assert user._mfa_type() == 'totp_mail'
    finally:
        setattr(ResUsers, '_mfa_type', original)

    assert user._mfa_type() == 'totp', 'la cadena real quedó restaurada'
