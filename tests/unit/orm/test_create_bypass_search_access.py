"""``create`` comprueba la lectura del comodelo de un Many2one con
``bypass_search_access`` — TASK-API-0422.

≙ ``odoo19c: odoo/orm/models.py:4686-4687``: en el bucle de clasificación de
``create``, para cada Many2one con ``bypass_search_access`` y fuera de modo
superusuario, ``check_access('read')`` sobre el registro del comodelo. Así un
usuario no enlaza un registro que no puede leer por un campo que salta la
búsqueda del comodelo
(``designs/orm-create-bypass-search-access-check-0422.md``).

*Métrica:* si ``create`` levanta ``AccessError`` y si la fila se creó.
*Ciega a:* comodelos cuyo manager no es un ``AccessQuerySet``; ahí el check no
tiene con qué comprobar, como ``inherits._check_delegate_access``.
"""
import pytest

from addons.base.models.ir_model import IrModel, IrModelAccess
from addons.base.models.ir_rule import IrRule
from exceptions import AccessError
from orm import registry
from orm.environments import Environment
from orm.utils import SUPERUSER_ID
from tests.factories.user_factory import UserFactory

pytestmark = pytest.mark.django_db


def _grant(env, model_name):
    label = registry.identity_of(env[model_name])
    row, _ = IrModel.objects.get_or_create(
        model=label, defaults={'name': model_name})
    IrModelAccess.objects.create(
        name=f'rw {model_name}', model_id=row, perm_read=True,
        perm_create=True, perm_write=True)
    return label


@pytest.fixture
def bars(db, system_user):
    with Environment(None, SUPERUSER_ID, {}) as env:
        _grant(env, 'test_orm.related_foo')
        label = _grant(env, 'test_orm.related_bar')
        IrRule.objects.create(name='hide secret', model_name=label,
                              domain_force="[('name', '!=', 'secret-bar')]")
        secret, visible = env['test_orm.related_bar'].create(
            [{'name': 'secret-bar'}, {'name': 'open-bar'}])
        return secret.id, visible.id


@pytest.fixture
def bypassed():
    """Activa ``bypass_search_access`` en ``bar_id`` y lo restaura."""
    with Environment(None, SUPERUSER_ID, {}) as env:
        field = type(env['test_orm.related_foo'])._meta.get_field('bar_id')
    previous = getattr(field, 'bypass_search_access', False)
    field.bypass_search_access = True
    try:
        yield field
    finally:
        field.bypass_search_access = previous


@pytest.fixture
def reader(db):
    return UserFactory()


def _foos(env):
    return env['test_orm.related_foo']


def test_a_record_the_user_cannot_read_is_refused(bars, bypassed, reader):
    secret_id, _ = bars
    with Environment(None, reader.pk, {}) as env:
        secret = env['test_orm.related_bar'].sudo().browse(secret_id)
        with pytest.raises(AccessError):
            _foos(env).create([{'name': 'x', 'bar_id': secret}])
    with Environment(None, SUPERUSER_ID, {}) as env:
        assert not _foos(env).search([('name', '=', 'x')])


def test_an_integer_id_is_refused_too(bars, bypassed, reader):
    secret_id, _ = bars
    with Environment(None, reader.pk, {}) as env:
        with pytest.raises(AccessError):
            _foos(env).create([{'name': 'y', 'bar_id': secret_id}])


def test_superuser_mode_skips_the_check(bars, bypassed, reader):
    secret_id, _ = bars
    with Environment(None, reader.pk, {}) as env:
        created = _foos(env).sudo().create(
            [{'name': 'z', 'bar_id': secret_id}])
        assert created.bar_id.id == secret_id


def test_without_the_flag_there_is_no_check(bars, reader):
    secret_id, _ = bars
    with Environment(None, reader.pk, {}) as env:
        created = _foos(env).create([{'name': 'w', 'bar_id': secret_id}])
        assert created.id


def test_an_empty_or_readable_value_passes(bars, bypassed, reader):
    _, visible_id = bars
    with Environment(None, reader.pk, {}) as env:
        empty, readable = _foos(env).create(
            [{'name': 'e', 'bar_id': None},
             {'name': 'r', 'bar_id': visible_id}])
        assert not empty.bar_id
        assert readable.bar_id.id == visible_id
