"""Tests — el canal RPC por clave de API, y la guarda que el 2FA le pone.

Contrato adaptado de ``odoo19c: odoo/addons/base/models/res_users.py:356`` y
``:387-400``, las dos mitades de la rama **no interactiva** de
``_check_credentials``, más los tres eslabones de ``_rpc_api_keys_only``
(``base:308``, ``auth_totp:66``, ``auth_totp_mail:135``).

Son dos mecanismos y hay que separarlos, porque uno abre y el otro cierra:

- **el canal** — por RPC la clave de API vale como credencial, en el campo de
  la contraseña. Sin él no hay integración externa posible.
- **la guarda** — con 2FA activo la contraseña **deja de valer** por ese canal.
  Sin ella el segundo factor se rodea entero: quien tenga la contraseña entra
  por RPC sin presentar nada más, y el 2FA sólo protege el navegador.

Los controles que exige el sub-patrón D de ``metrica-decide-la-conclusion.md``
—cada uno declara qué lo haría fallar—:

``TestChannel.test_a_valid_key_authenticates_over_rpc``
    El eje del canal. Qué lo haría fallar: retirar la rama de la clave. Ningún
    otro caso lo mide — los demás presentan contraseñas.

``TestChannel.test_the_key_of_another_user_is_refused``
    Qué lo haría fallar: que la rama no comparase el uid devuelto con el del
    user. La clave es **real y vigente** —la generó el caso hermano—, así
    que una comprobación de mera validez autenticaría a quien no es su dueño.

``TestChannel.test_the_key_does_not_work_interactively``
    CONTROL de la dirección contraria. La fuente encierra la rama en
    ``if not interactive``: una clave de API no abre sesión de navegador. Sin
    ese guard, una clave filtrada valdría como contraseña en el login web.

``TestGuard.test_2fa_denies_the_password_over_rpc``
    El eje de la guarda. Qué lo haría fallar: retirar la consulta a
    ``_rpc_api_keys_only`` de la condición de ``:356``.

``TestGuard.test_2fa_does_not_deny_the_password_interactively``
    CONTROL de la dirección contraria, y no es redundante: una guarda escrita
    sin el ``interactive or`` cerraría también el login web del user con
    2FA, que es precisamente quien tiene que poder llegar al segundo paso.

``TestGuard.test_the_user_with_2fa_still_gets_in_with_a_key``
    Qué lo haría fallar: poner la guarda antes de la rama de la clave en vez
    de después. El 2FA restringe el canal a claves; no lo cierra.

``TestChain.test_each_link_can_raise_the_flag_on_its_own``
    Qué lo haría fallar: encadenar sin ``combine=first_truthy``. Con el relevo
    por defecto, el eslabón externo devuelve ``False`` para el user que sólo
    tiene 2FA de app, la cadena se corta ahí y el eslabón interno —el único con
    razón para decir que sí— nunca responde.
"""
import base64

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from exceptions import AccessDenied
from orm.environments import user_scope

from addons.authz_totp.models.totp import TIMESTEP, hotp
from addons.authz_totp.services import begin_setup, confirm_setup
from addons.base.models.res_groups import ResGroups
from addons.base.models.res_users import ResUsersApikeys

User = get_user_model()

pytestmark = pytest.mark.integration

PASSWORD = 'CanalRpc123!'

INTERACTIVO = {'interactive': True}
RPC = {'interactive': False}


def _internal(login):
    """Un user interno — es quien la guarda de ``_generate`` deja crear."""
    account = User.objects.create_user(login=login, password=PASSWORD)
    group = ResGroups.objects.create(name=f'grupo-{login}',
                                     user_type='internal')
    account.group_ids.add(group)
    return account


def _key_for(user):
    """Una clave de API real y vigente del user, en claro."""
    with user_scope(user.pk):
        return ResUsersApikeys._generate(
            'rpc', 'clave de prueba',
            timezone.now() + timezone.timedelta(days=1))


def _credential(password):
    return {'type': 'password', 'login': 'x', 'password': password}


def _enable_totp(user):
    """Activa el 2FA de app; devuelve el secreto."""
    secret, _uri = begin_setup(user)
    key = base64.b32decode(secret)
    counter = int(timezone.now().timestamp()) // TIMESTEP - 1
    assert confirm_setup(user, f'{hotp(key, counter):06d}'), 'el alta falló'
    return secret


@pytest.fixture
def user(db):
    return _internal('canal.rpc@kaupamex.mx')


class TestChannel:
    """≙ la rama de la clave de API (``:387-394``)."""

    def test_a_valid_key_authenticates_over_rpc(self, user):
        clave = _key_for(user)
        info = user._check_credentials(_credential(clave), RPC)
        assert info == {'uid': user.pk, 'auth_method': 'apikey',
                        'mfa': 'default'}

    def test_the_key_of_another_user_is_refused(self, user):
        """CONTROL — la clave es de su dueño, no de quien la presente."""
        clave = _key_for(user)
        otro = _internal('otro.canal@kaupamex.mx')
        with pytest.raises(AccessDenied):
            otro._check_credentials(_credential(clave), RPC)

    def test_the_key_does_not_work_interactively(self, user):
        """CONTROL — una clave de API no abre sesión de navegador."""
        clave = _key_for(user)
        with pytest.raises(AccessDenied):
            user._check_credentials(_credential(clave), INTERACTIVO)

    def test_the_password_still_works_over_rpc_without_2fa(self, user):
        """Sin 2FA la contraseña sigue valiendo por RPC — ``:356``."""
        info = user._check_credentials(_credential(PASSWORD), RPC)
        assert info['auth_method'] == 'password'


class TestGuard:
    """≙ ``_rpc_api_keys_only`` en la condición de ``:356``."""

    def test_2fa_denies_the_password_over_rpc(self, user):
        """El eje: con segundo factor, la contraseña no vale por RPC."""
        _enable_totp(user)
        assert user._rpc_api_keys_only() is True
        with pytest.raises(AccessDenied):
            user._check_credentials(_credential(PASSWORD), RPC)

    def test_2fa_does_not_deny_the_password_interactively(self, user):
        """CONTROL — el login web del user con 2FA sigue abierto.

        Es quien tiene que llegar al segundo paso; cerrarle la puerta aquí
        dejaría la cuenta inaccesible por navegador.
        """
        _enable_totp(user)
        info = user._check_credentials(_credential(PASSWORD), INTERACTIVO)
        assert info['auth_method'] == 'password'

    def test_the_user_with_2fa_still_gets_in_with_a_key(self, user):
        """CONTROL — el 2FA restringe el canal a claves; no lo cierra."""
        clave = _key_for(user)
        _enable_totp(user)
        info = user._check_credentials(_credential(clave), RPC)
        assert info['auth_method'] == 'apikey'


class TestChain:
    """≙ ``<lo propio> or super()`` — los tres eslabones, y su ``combine``."""

    def test_the_base_link_says_no(self, user):
        """Sin ninguna razón, ``base`` responde ``False`` (``:308-310``)."""
        assert user._rpc_api_keys_only() is False

    def test_each_link_can_raise_the_flag_on_its_own(self, user):
        """CONTROL del ``combine`` — el eslabón INTERNO tiene que llegar.

        Con el relevo por defecto de ``chain_method``, el eslabón externo
        (``authz_totp_mail``) devuelve ``False`` para este user —no hay
        política de correo— y cortaría la cadena antes del de ``authz_totp``,
        que es el único con razón para decir que sí.
        """
        _enable_totp(user)
        assert user.totp_enabled is True
        assert user._mfa_type() == 'totp', 'gana el eslabón interno'
        assert user._rpc_api_keys_only() is True
