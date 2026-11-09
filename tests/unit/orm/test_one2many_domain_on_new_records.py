"""El ``domain`` de cada One2many sobre registros de ``new()``.

≙ ``Many2one._update_inverses`` (``odoo19c: odoo/orm/fields_relational.py:
449-463``), que añade la línea a cada One2many inverso sólo si cumple su
``get_comodel_domain`` (``:921-922``), y ``test_60_one2many_domain`` /
``test_70_x2many_write`` (``odoo/addons/test_orm/tests/test_fields.py``).
Diseño en ``designs/one2many-domain-on-new-records.md`` del Workbench.

*Métrica:* ``_ids`` de los tres One2many de ``test_orm.discussion``.
*Ciega a:* el dueño real, que ya lee con el dominio en ``_read_one2many``.
"""
import pytest
from django.contrib.auth import get_user_model

from orm.environments import env as current_env
from orm.environments import sudo, user_scope

pytestmark = pytest.mark.django_db


@pytest.fixture
def models():
    user = get_user_model().objects.create_user(
        login='one2many-domain', password=None, name='u')
    with user_scope(user.pk), sudo():
        environment = current_env()
        yield environment['test_orm.discussion'], environment[
            'test_orm.message']


def test_a_plain_line_stays_out_of_the_filtered_fields(models):
    discussion, message = models
    owner = discussion.new({'name': 'd'})
    line = message.new({'discussion': owner.id, 'important': False})
    assert owner.messages._ids == (line.id,)
    assert owner.important_messages._ids == ()
    assert owner.very_important_messages._ids == ()


def test_an_important_line_is_in_the_three_fields(models):
    discussion, message = models
    owner = discussion.new({'name': 'd'})
    line = message.new({'discussion': owner.id, 'important': True})
    assert owner.messages._ids == (line.id,)
    assert owner.important_messages._ids == (line.id,)
    assert owner.very_important_messages._ids == (line.id,)


def test_the_field_without_domain_sees_every_line(models):
    discussion, message = models
    owner = discussion.new({'name': 'd'})
    plain = message.new({'discussion': owner.id, 'important': False})
    important = message.new({'discussion': owner.id, 'important': True})
    assert set(owner.messages._ids) == {plain.id, important.id}
    assert owner.important_messages._ids == (important.id,)
