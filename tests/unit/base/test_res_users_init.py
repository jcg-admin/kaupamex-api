"""``res.users.init``: cifra al arrancar las contraseñas escritas en claro.

≙ ``odoo19c: odoo/addons/base/models/res_users.py:277-292``. Diseño, con la
divergencia del prefijo ``!`` y su medición: ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/res-users-init.md``.
"""
import pytest
from django.db import connection

from addons.base.models import ResUsers
from orm.registry import Registry
from tests.factories.user_factory import UserFactory

pytestmark = pytest.mark.django_db


def _store(user, raw):
    """Escribe ``password`` tal cual, sin cifrar — la vía SQL que la fuente
    admite y que ``init`` existe para corregir."""
    ResUsers.objects.filter(pk=user.pk).update(password=raw)


def _stored(user):
    return ResUsers.objects.filter(pk=user.pk).values_list(
        'password', flat=True).get()


def test_a_plaintext_password_is_encrypted_and_still_checks():
    user = UserFactory()
    _store(user, 'clave-en-claro')
    ResUsers.init(using=connection.alias)
    stored = _stored(user)
    assert stored != 'clave-en-claro'
    assert ResUsers._crypt_context().identify(stored) != 'plaintext'
    user.refresh_from_db()
    assert user.check_password('clave-en-claro')


def test_an_encrypted_password_is_left_byte_for_byte():
    user = UserFactory()
    before = _stored(user)
    ResUsers.init(using=connection.alias)
    assert _stored(user) == before


def test_an_unusable_password_stays_unusable():
    """La divergencia: ``!…`` no es MCF y un porte literal lo cifraría,
    dejando la cuenta con una contraseña conocida."""
    user = UserFactory()
    user.set_unusable_password()
    user.save(update_fields=['password'])
    before = _stored(user)
    ResUsers.init(using=connection.alias)
    assert _stored(user) == before
    user.refresh_from_db()
    assert not user.has_usable_password()


def test_an_empty_password_is_left_alone():
    """La fuente filtra ``password IS NOT NULL``; aquí la columna es
    ``NOT NULL`` (divergencia de esquema declarada en el diseño), así que el
    vacío que puede existir es la cadena vacía."""
    user = UserFactory()
    _store(user, '')
    ResUsers.init(using=connection.alias)
    assert _stored(user) == ''


def test_init_models_runs_the_users_init():
    user = UserFactory()
    _store(user, 'otra-clave')
    registry = Registry(connection.alias)
    with connection.cursor() as cr:
        registry.init_models(cr, ['res.users'], {'module': 'base'},
                             install=False)
    assert ResUsers._crypt_context().identify(_stored(user)) != 'plaintext'
