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
    # ``su=False`` explícito: es el defecto de la fuente
    # (``odoo19c: odoo/orm/environments.py:64``); aquí el defecto ``None``
    # hereda la elevación del entorno exterior del fixture.
    with Environment(None, user.pk, {}, su=False) as environment:
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
