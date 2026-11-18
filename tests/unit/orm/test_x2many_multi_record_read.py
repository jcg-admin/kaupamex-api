"""Un x2many leído sobre varios registros es la unión de sus valores.

≙ ``_Relational.__get__``, rama *multi-record* (``odoo19c: odoo/orm/
fields_relational.py:42-79``), más ``_RelationalMulti.
convert_to_record_multi`` (``odoo19c: odoo/orm/fields_relational.py:655``):
los ids de cada registro, en su orden, sin repetir.
Diseño en ``designs/x2many-multi-record-read.md`` del Workbench.

*Métrica:* los ids del recordset devuelto, comparados con los de leer
registro por registro.
*Ciega a:* la caché por campo y ``fetch``, que este árbol no tiene; y al
filtro ``active_test`` de la unión, porque ningún comodelo de estos casos
declara ``active``.
"""
import pytest
from django.contrib.auth import get_user_model

from orm.commands import Command
from orm.environments import env as current_env
from orm.environments import sudo, user_scope

pytestmark = pytest.mark.django_db


@pytest.fixture
def environment():
    user = get_user_model().objects.create_user(
        login='x2many-multi', password=None, name='u')
    with user_scope(user.pk), sudo():
        yield current_env()


def _multis(environment):
    """Dos ``test_orm.multi`` con dos y una línea."""
    Multi = environment['test_orm.multi']
    Line = environment['test_orm.multi.line']
    first, second = Multi.create({}), Multi.create({})
    a = Line.create({'multi': first.id, 'name': 'a'})
    b = Line.create({'multi': first.id, 'name': 'b'})
    c = Line.create({'multi': second.id, 'name': 'c'})
    environment.flush_all()
    return first, second, (a, b, c)


def test_reverse_accessor_is_the_union(environment):
    first, second, (a, b, c) = _multis(environment)
    lines = (first + second).lines
    assert lines._name == 'test_orm.multi.line'
    assert set(lines.ids) == {a.id, b.id, c.id}
    assert lines.ids == first.lines.ids + second.lines.ids


def test_reverse_accessor_follows_the_record_order(environment):
    first, second, _lines = _multis(environment)
    assert (second + first).lines.ids == second.lines.ids + first.lines.ids


def test_reverse_accessor_of_records_without_lines(environment):
    Multi = environment['test_orm.multi']
    empty = Multi.create({}) + Multi.create({})
    lines = empty.lines
    assert lines._name == 'test_orm.multi.line'
    assert not lines


def test_declared_one2many_is_the_union(environment):
    Discussion = environment['test_orm.discussion']
    Message = environment['test_orm.message']
    user = environment.user.id
    first = Discussion.create(
        {'name': 'a', 'participants': [Command.link(user)]})
    second = Discussion.create(
        {'name': 'b', 'participants': [Command.link(user)]})
    one = Message.create({'discussion': first.id})
    two = Message.create({'discussion': second.id})
    environment.flush_all()
    messages = (first + second).messages
    assert messages._name == 'test_orm.message'
    assert messages.ids == [one.id, two.id]


def test_many2many_is_the_union_without_duplicates(environment):
    Multi = environment['test_orm.multi']
    Tag = environment['test_orm.multi.tag']
    shared, own = Tag.create({'name': 'aa'}), Tag.create({'name': 'ab'})
    first = Multi.create({'tags': [Command.set([shared.id, own.id])]})
    second = Multi.create({'tags': [Command.set([shared.id])]})
    environment.flush_all()
    tags = (first + second).tags
    assert tags._name == 'test_orm.multi.tag'
    assert sorted(tags.ids) == sorted([shared.id, own.id])
    assert len(tags.ids) == 2
