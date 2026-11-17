"""``SET`` y ``CLEAR`` de un One2many sólo retiran lo que cumple su dominio.

≙ ``One2many.write_real``, rama almacenada (``odoo19c: odoo/orm/
fields_relational.py:1027-1043``): lo que se retira sale de
``comodel.search(get_comodel_domain & inverse in recs & id not in lines)``.
Diseño en ``designs/one2many-clear-set-domain.md`` del Workbench.

*Métrica:* filas de ``test_orm.message`` con ``discussion`` apuntando al
registro, leídas de la base tras la escritura.
*Ciega a:* el ``context`` del campo y la rama no almacenada.
"""
import pytest
from django.apps import apps as django_apps
from django.contrib.auth import get_user_model

from orm.commands import Command
from orm.environments import env as current_env
from orm.environments import sudo, user_scope

pytestmark = pytest.mark.django_db

Message = django_apps.get_model('test_orm', 'TestOrmMessage')


@pytest.fixture
def owner():
    user = get_user_model().objects.create_user(
        login='one2many-clear', password=None, name='u')
    with user_scope(user.pk), sudo():
        environment = current_env()
        yield environment['test_orm.discussion'].create(
            {'name': 'd', 'participants': [Command.link(user.pk)]})


def _line(owner, important):
    line = owner.env['test_orm.message'].create(
        {'discussion': owner.id, 'important': important})
    owner.env.flush_all()
    return line.id


def _linked(owner):
    owner.env.flush_all()
    return set(Message._base_manager.filter(
        discussion=owner.id).values_list('pk', flat=True))


def test_clear_on_a_filtered_field_keeps_the_other_lines(owner):
    plain = _line(owner, False)
    _line(owner, True)
    owner.write({'important_messages': [Command.clear()]})
    assert _linked(owner) == {plain}


def test_set_on_a_filtered_field_keeps_the_other_lines(owner):
    plain = _line(owner, False)
    _line(owner, True)
    kept = _line(owner, True)
    owner.write({'important_messages': [Command.set([kept])]})
    assert _linked(owner) == {plain, kept}


def test_clear_on_the_unfiltered_field_removes_every_line(owner):
    _line(owner, False)
    _line(owner, True)
    owner.write({'messages': [Command.clear()]})
    assert _linked(owner) == set()
