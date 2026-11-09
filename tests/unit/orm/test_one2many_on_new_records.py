"""El One2many declarado sobre registros de ``new()``.

≙ la caché de un registro nuevo y ``_RelationalMulti._update_inverse``
(``odoo19c: odoo/orm/fields_relational.py:564-573``), que
``BaseModel._update_cache`` llama para los registros nuevos del comodelo.
Diseño en ``designs/one2many-on-new-records.md`` del Workbench.

*Métrica:* ``_ids`` del One2many de un dueño nuevo; ``ids`` descarta los
ids nuevos sin origen (``OriginIds``, ``odoo/orm/utils.py:129-141``).
*Ciega a:* la caché de un dueño real, que aquí se lee de la base.
"""
import pytest
from django.contrib.auth import get_user_model

from orm.environments import env as current_env
from orm.environments import sudo, user_scope

pytestmark = pytest.mark.django_db


@pytest.fixture
def models():
    user = get_user_model().objects.create_user(
        login='one2many-new', password=None, name='u')
    with user_scope(user.pk), sudo():
        environment = current_env()
        yield environment['test_orm.discussion'], environment[
            'test_orm.message']


def test_a_new_owner_starts_without_lines(models):
    discussion, _message = models
    assert discussion.new({'name': 'd'}).messages._ids == ()


def test_a_new_line_pointing_to_a_new_owner_joins_its_lines(models):
    discussion, message = models
    owner = discussion.new({'name': 'd'})
    line = message.new({'discussion': owner.id})
    assert owner.messages._ids == (line.id,)
