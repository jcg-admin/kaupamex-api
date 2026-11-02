"""Porte semántico de ``TestSearchAny`` (``odoo19c: odoo/addons/test_orm/
tests/test_search.py:1360-1572``).

Revisión de referencia: ``odoo-tools@abe4040ec1``. La fuente instala una
regla de fila por modelo y afirma el SQL: con ``any`` la subconsulta del
comodelo lleva su regla; con ``any!`` no. Aquí se afirman las filas: la regla
oculta un registro del comodelo, y sólo ``any!`` lo alcanza.
"""

import pytest
from django.contrib.auth import get_user_model

from addons.base.models.ir_model import IrModel, IrModelAccess
from addons.base.models.ir_rule import IrRule
from orm.domains import Domain
from orm.environments import Environment

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

LABELS = ('test_orm.TestOrmRelated', 'test_orm.TestOrmRelatedFoo',
          'test_orm.TestOrmRelatedBar')


@pytest.fixture
def records(env):
    Bar = env['test_orm.related_bar']
    Foo = env['test_orm.related_foo']
    Related = env['test_orm.related']
    hidden_bar = Bar.create({'name': 'a', 'active': True})
    hidden = Foo.create({'name': 'a', 'bar_id': hidden_bar.id})
    shown = Foo.create({'name': 'b'})
    return {
        'via_hidden': Related.create({'name': 'r1', 'foo_id': hidden.id}),
        'via_shown': Related.create({'name': 'r2', 'foo_id': shown.id}),
    }


@pytest.fixture
def ruled_user(db):
    """Un usuario con lectura sobre los tres modelos y una regla que oculta
    el ``related_foo`` llamado ``a``."""
    for label in LABELS:
        row, _ = IrModel.objects.get_or_create(
            model=label, defaults={'name': label})
        IrModelAccess.objects.create(
            name=f'any {label}', model_id=row, perm_read=True)
    IrRule.objects.create(
        name='related_foo sin a', model_name='test_orm.TestOrmRelatedFoo',
        domain_force="[('name', '!=', 'a')]")
    return get_user_model().objects.create_user(
        login='search.any@kaupamex.mx', password='SearchAny123!')


def _found_as(user, domain):
    # Sin ``su``: con un usuario declarado el defecto es no elevar, como en la
    # fuente (``odoo19c: odoo/orm/environments.py:64``), aunque el fixture
    # haya abierto un entorno de super-usuario.
    with Environment(None, user.pk, {}) as environment:
        return set(environment['test_orm.related'].search(domain).ids)


def test_any_applies_the_rule_of_the_comodel(records, ruled_user):
    assert _found_as(ruled_user, Domain('foo_id', 'any',
                                        Domain('name', '=', 'a'))) == set()


def test_any_bang_bypasses_the_rule(records, ruled_user):
    assert _found_as(ruled_user, Domain('foo_id', 'any!',
                                        Domain('name', '=', 'a'))) == {
        records['via_hidden'].id}


def test_any_keeps_the_rows_the_rule_allows(records, ruled_user):
    assert _found_as(ruled_user, Domain('foo_id', 'any',
                                        Domain('name', '=', 'b'))) == {
        records['via_shown'].id}


@pytest.fixture
def x2many_rules(db):
    """Reglas que ocultan el ``related`` llamado ``r2`` y el ``related_bar``
    llamado ``a``: son los comodelos de ``foo_ids`` y ``bar_ids``."""
    IrRule.objects.create(
        name='related sin r2', model_name='test_orm.TestOrmRelated',
        domain_force="[('name', '!=', 'r2')]")
    IrRule.objects.create(
        name='related_bar sin a', model_name='test_orm.TestOrmRelatedBar',
        domain_force="[('name', '!=', 'a')]")


def _foos_as(user, domain):
    with Environment(None, user.pk, {}) as environment:
        return set(environment['test_orm.related_foo'].search(domain).ids)


def test_one2many_any_applies_the_rule_of_the_comodel(
        env, records, ruled_user, x2many_rules):
    shown_foo = records['via_shown'].foo_id
    domain = Domain('foo_ids', 'any', Domain('name', '=', 'r2'))
    assert _foos_as(ruled_user, domain) == set()
    assert _foos_as(ruled_user, Domain('foo_ids', 'any!', Domain(
        'name', '=', 'r2'))) == {shown_foo.id}


def test_many2many_any_applies_the_rule_of_the_comodel(
        env, ruled_user, x2many_rules):
    Bar, Foo = env['test_orm.related_bar'], env['test_orm.related_foo']
    bar = Bar.create({'name': 'a'})
    foo = Foo.create({'name': 'b', 'bar_ids': [bar.id]})
    assert _foos_as(ruled_user, Domain(
        'bar_ids', 'any', Domain('name', '=', 'a'))) == set()
    assert _foos_as(ruled_user, Domain(
        'bar_ids', 'any!', Domain('name', '=', 'a'))) == {foo.id}


# ---------------------------------------------------------------------------
# ``TestSearchRelated.test_related_simple`` (``tests/test_search.py:437``):
# un ``related`` con ``related_sudo=False`` busca con ``any`` (aplica la regla
# del comodelo) y uno con ``related_sudo=True``, con ``any!``.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(('fname', 'reaches_hidden'), [
    ('foo_name', False),
    ('foo_name_sudo', True),
    ('foo_bar_name', False),
    ('foo_bar_name_sudo', True),
])
def test_related_sudo_decides_the_rule(records, ruled_user, fname,
                                       reaches_hidden):
    found = _found_as(ruled_user, [(fname, '=', 'a')])
    assert found == ({records['via_hidden'].id} if reaches_hidden else set())


# ``TestSearchRelated.test_related_many2one`` (``tests/test_search.py:474``):
# lo mismo sobre un Many2one ``related``, por igualdad y por ruta.


@pytest.mark.parametrize(('fname', 'reaches_hidden'), [
    ('foo_bar_id', False),
    ('foo_bar_sudo_id', True),
])
def test_related_many2one_by_id_and_by_path(records, ruled_user, fname,
                                            reaches_hidden):
    hidden_bar = records['via_hidden'].foo_id.bar_id
    expected = {records['via_hidden'].id} if reaches_hidden else set()
    assert _found_as(ruled_user, [(fname, '=', hidden_bar.id)]) == expected
    assert _found_as(ruled_user, [(f'{fname}.name', '=', 'a')]) == expected


# ``TestSearchRelated.test_related_inherited`` (``tests/test_search.py:1263``):
# un campo heredado por ``_inherits`` —también un ``related`` heredado— se
# busca a través de la FK del padre, con la regla del padre.


@pytest.mark.parametrize(('fname', 'reaches_hidden'), [
    ('name', True),
    ('foo_name', False),
    ('foo_name_sudo', True),
])
def test_related_inherited(env, records, ruled_user, fname, reaches_hidden):
    Inherits = env['test_orm.related_inherits']
    child = Inherits.create({'base_id': records['via_hidden'].id})
    row, _ = IrModel.objects.get_or_create(
        model='test_orm.TestOrmRelatedInherits',
        defaults={'name': 'related_inherits'})
    IrModelAccess.objects.create(
        name='any related_inherits', model_id=row, perm_read=True)
    value = 'r1' if fname == 'name' else 'a'
    with Environment(None, ruled_user.pk, {}) as environment:
        found = set(environment['test_orm.related_inherits'].search(
            [(fname, '=', value)]).ids)
    assert found == ({child.id} if reaches_hidden else set())
