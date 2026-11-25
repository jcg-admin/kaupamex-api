"""``write`` comprueba la lectura del comodelo de un Many2one con
``bypass_search_access`` — gemelo del check de ``create`` (TASK-API-0422).

≙ ``odoo19c: odoo/orm/fields_relational.py:407-411``: ``Many2one.write``, fuera
de modo superusuario, hace ``check_access('read')`` sobre el registro del
comodelo y envuelve el error con *"Failed to write field %s"*
(``designs/orm-write-bypass-search-access-check-0422.md``).

*Métrica:* si la escritura levanta ``AccessError`` con ese mensaje y si la
fila cambió.
*Ciega a:* comodelos cuyo manager no es un ``AccessQuerySet``.
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
def records(db, system_user):
    """Una barra oculta por regla, una visible y un ``foo`` sin barra."""
    with Environment(None, SUPERUSER_ID, {}) as env:
        _grant(env, 'test_orm.related_foo')
        label = _grant(env, 'test_orm.related_bar')
        IrRule.objects.create(name='hide secret', model_name=label,
                              domain_force="[('name', '!=', 'secret-bar')]")
        secret, visible = env['test_orm.related_bar'].create(
            [{'name': 'secret-bar'}, {'name': 'open-bar'}])
        foo = env['test_orm.related_foo'].create([{'name': 'f'}])
        return secret.id, visible.id, foo.id


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


def _bar_of(foo_id):
    with Environment(None, SUPERUSER_ID, {}) as env:
        return env['test_orm.related_foo'].browse(foo_id).bar_id.id


def test_writing_an_unreadable_record_is_refused(records, bypassed, reader):
    secret_id, _, foo_id = records
    with Environment(None, reader.pk, {}) as env:
        foo = env['test_orm.related_foo'].browse(foo_id)
        secret = env['test_orm.related_bar'].sudo().browse(secret_id)
        with pytest.raises(AccessError, match='^Failed to write field'):
            foo.write({'bar_id': secret})
    assert not _bar_of(foo_id)


def test_an_integer_id_is_refused_too(records, bypassed, reader):
    secret_id, _, foo_id = records
    with Environment(None, reader.pk, {}) as env:
        foo = env['test_orm.related_foo'].browse(foo_id)
        with pytest.raises(AccessError, match='^Failed to write field'):
            foo.write({'bar_id': secret_id})
    assert not _bar_of(foo_id)


def test_the_field_write_checks_too(records, bypassed, reader):
    secret_id, _, foo_id = records
    with Environment(None, reader.pk, {}) as env:
        foo = env['test_orm.related_foo'].browse(foo_id)
        with pytest.raises(AccessError, match='^Failed to write field'):
            bypassed.write(foo, secret_id)


def test_superuser_mode_skips_the_check(records, bypassed, reader):
    secret_id, _, foo_id = records
    with Environment(None, reader.pk, {}) as env:
        env['test_orm.related_foo'].sudo().browse(foo_id).write(
            {'bar_id': secret_id})
    assert _bar_of(foo_id) == secret_id


def test_without_the_flag_there_is_no_check(records, reader):
    secret_id, _, foo_id = records
    with Environment(None, reader.pk, {}) as env:
        env['test_orm.related_foo'].browse(foo_id).write(
            {'bar_id': secret_id})
    assert _bar_of(foo_id) == secret_id


def test_an_empty_or_readable_value_passes(records, bypassed, reader):
    _, visible_id, foo_id = records
    with Environment(None, reader.pk, {}) as env:
        foo = env['test_orm.related_foo'].browse(foo_id)
        foo.write({'bar_id': visible_id})
        assert _bar_of(foo_id) == visible_id
        foo.write({'bar_id': None})
    assert not _bar_of(foo_id)
