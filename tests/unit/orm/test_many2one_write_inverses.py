"""Asignar el Many2one de un registro nuevo ajusta el One2many inverso.

≙ ``Many2one.write`` (``odoo19c: odoo/orm/fields_relational.py:400-424``)
con ``_remove_inverses`` (``:426-447``) y ``_update_inverses``
(``:449-463``): el registro sale de las líneas en caché del corregistro
anterior y entra en las del nuevo, si estaban en caché o si el corregistro es
nuevo. Diseño en ``designs/one2many-on-new-records.md`` (paso 3).

*Métrica:* ``_ids`` del One2many de dueños nuevos.
*Ciega a:* dueños reales, cuyo One2many aquí se lee de la base.
"""
import pytest
from django.contrib.auth import get_user_model

from orm.environments import env as current_env
from orm.environments import sudo, user_scope

pytestmark = pytest.mark.django_db


@pytest.fixture
def models():
    user = get_user_model().objects.create_user(
        login='many2one-inverses', password=None, name='u')
    with user_scope(user.pk), sudo():
        environment = current_env()
        yield environment['test_orm.discussion'], environment[
            'test_orm.message']


def test_assigning_a_new_owner_adds_the_line(models):
    discussion, message = models
    owner = discussion.new({'name': 'd'})
    line = message.new({})
    line.discussion = owner
    assert owner.messages._ids == (line.id,)


def test_moving_the_line_removes_it_from_the_previous_owner(models):
    discussion, message = models
    first = discussion.new({'name': 'a'})
    second = discussion.new({'name': 'b'})
    line = message.new({'discussion': first.id})
    assert first.messages._ids == (line.id,)
    line.discussion = second
    assert first.messages._ids == ()
    assert second.messages._ids == (line.id,)
