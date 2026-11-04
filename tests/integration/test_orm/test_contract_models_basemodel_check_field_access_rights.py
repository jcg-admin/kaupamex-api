"""``BaseModel.check_field_access_rights`` — ≙ ``odoo19c:
odoo/orm/models.py:3436-3466``. TASK-API-0485.

Bajo elevación devuelve los nombres pedidos, o todos los campos si no se
pidió ninguno. Sin elevación filtra los legibles cuando no se piden nombres,
levanta ``AccessError`` por un campo prohibido, e ignora un nombre que no es
campo: no se leerá ni se escribirá.
"""
import pytest

from exceptions import AccessError
from orm.environments import Environment
from orm.models import NO_ACCESS
from tests.factories.user_factory import UserFactory

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


@pytest.fixture
def forbidden_value2(env):
    field = env['test_orm.foo']._fields['value2']
    field.groups = NO_ACCESS
    yield field
    del field.groups


def _unelevated():
    """Un usuario común: ``SUPERUSER_ID`` eleva siempre, aquí y en la fuente
    (``odoo19c: odoo/orm/environments.py:66-67``)."""
    return Environment(None, UserFactory().pk, {})


def test_check_field_access_rights_elevated_returns_every_field(env):
    Foo = env['test_orm.foo']
    assert Foo.check_field_access_rights('read', None) == list(Foo._fields)
    assert Foo.check_field_access_rights('read', ['value1']) == ['value1']


def test_check_field_access_rights_lists_only_readable_fields(
        env, forbidden_value2):
    with _unelevated() as unelevated:
        names = unelevated['test_orm.foo'].check_field_access_rights(
            'read', None)
    assert 'value1' in names
    assert 'value2' not in names


def test_check_field_access_rights_refuses_a_forbidden_field(
        env, forbidden_value2):
    with _unelevated() as unelevated:
        Foo = unelevated['test_orm.foo']
        with pytest.raises(AccessError, match='value2'):
            Foo.check_field_access_rights('read', ['value1', 'value2'])


def test_check_field_access_rights_ignores_an_unknown_name(env):
    with _unelevated() as unelevated:
        Foo = unelevated['test_orm.foo']
        assert Foo.check_field_access_rights('read', ['nope']) == ['nope']
