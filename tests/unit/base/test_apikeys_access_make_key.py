"""``check_access_make_key`` — sólo un usuario interno crea claves de API.

Porta ``odoo19c: odoo/addons/base/models/res_users.py:1832-1834``, la guarda
de la via **interactiva**. Es otra puerta que
``_ensure_can_manage_keys_programmatically``, que gobierna la programatica.

El control que puede fallar
---------------------------

La guarda se prueba en sus dos sentidos —niega al de portal, deja pasar al
interno— y ademas contra el flujo que NO debe romper: el dispositivo de
confianza de 2FA llama a ``_generate`` para un usuario de portal con todo
derecho, asi que un caso comprueba que la primitiva sigue abierta. Si alguien
mueve la guarda dentro de ``_generate``, ese caso cae. Medido: moviendola,
el subconjunto pasa de 6 passed a 1 failed, 5 passed.
"""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from addons.base.models.res_groups import ResGroups
from addons.base.models.res_users import ResUsersApikeys
from exceptions import AccessError
from orm.environments import user_scope

User = get_user_model()


def _user_of_type(login, user_type):
    account = User.objects.create_user(login=login, password='Clave123!')
    group = ResGroups.objects.create(name=f'grupo-{user_type}',
                                     user_type=user_type)
    account.group_ids.add(group)
    return account


@pytest.fixture
def internal(db):
    return _user_of_type('interno@example.com', 'internal')


@pytest.fixture
def portal(db):
    return _user_of_type('portal@example.com', 'portal')


def test_an_internal_user_passes(internal):
    with user_scope(internal.pk):
        assert ResUsersApikeys.check_access_make_key() is None


def test_a_portal_user_is_refused(portal):
    with user_scope(portal.pk):
        with pytest.raises(AccessError):
            ResUsersApikeys.check_access_make_key()


def test_a_user_with_no_type_is_refused(db):
    """Sin grupo no hay tipo, y la guarda es fail-closed."""
    account = User.objects.create_user(login='suelto@example.com',
                                       password='Clave123!')
    with user_scope(account.pk):
        with pytest.raises(AccessError):
            ResUsersApikeys.check_access_make_key()


def test_outside_a_user_context_it_is_refused(db):
    """Sin usuario resuelto tampoco pasa: la guarda no cede por ausencia."""
    with pytest.raises(AccessError):
        ResUsersApikeys.check_access_make_key()


def test_the_message_says_why(portal):
    with user_scope(portal.pk):
        with pytest.raises(AccessError) as excinfo:
            ResUsersApikeys.check_access_make_key()
    assert 'interno' in str(excinfo.value)


def test_generate_stays_open_for_a_portal_user(portal):
    """El flujo que la guarda NO debe romper.

    ``authz_totp`` llama a ``_generate`` con ``BROWSER_SCOPE`` para el
    dispositivo de confianza, y un usuario de portal con segundo factor tiene
    todo el derecho. Por eso la fuente pone la guarda en ``make_key`` y no en
    la primitiva.

    La caducidad es explicita y dentro del tope del grupo: la clave
    **permanente** (``expiration_date=None``) si esta reservada al usuario de
    sistema, y eso lo decide ``_check_expiration_date``, que es otra regla y
    ya estaba portada.
    """
    caduca = timezone.now() + timedelta(hours=12)
    with user_scope(portal.pk):
        key = ResUsersApikeys._generate('browser', 'este navegador', caduca)
    assert key
