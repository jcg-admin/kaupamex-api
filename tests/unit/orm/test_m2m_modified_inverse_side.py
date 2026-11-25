"""Escribir el lado inverso de un Many2many recalcula al comodelo.

≙ ``odoo19c: odoo/orm/fields_relational.py:1586-1593``: tras escribir la tabla
relacional, la fuente llama ``modified`` sobre los registros del comodelo con
los campos inversos. ``test_orm.user.group_count`` es almacenado y depende de
``group_ids``; ``test_orm.group.user_ids`` es su inverso sobre la misma tabla
(``designs/orm-m2m-modified-inverse-side-0356.md``).

Se escribe con el manager de Django (``related_manager``: leer el campo
devuelve un recordset), que es por donde escribe
``_many2many_write_relation`` y lo que emite ``m2m_changed``; así los casos no
dependen de la política ``_allow_sudo_commands`` de estos dos modelos.
"""
import pytest

from orm.commands import related_manager
from orm.environments import env as current_env
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    """Un usuario con su ``group_count`` ya volcado: sin eso, el cómputo
    pendiente de la creación se resolvería al leer y el caso pasaría con o
    sin aviso."""
    record = MODELS_BY_NAME['test_orm.user']._base_manager.create(name='Ana')
    assert stored_count(record) == 0
    return record


@pytest.fixture
def group():
    return MODELS_BY_NAME['test_orm.group']._base_manager.create(name='Staff')


def stored_count(user):
    """El valor de la base tras volcar los recómputos pendientes."""
    current_env().flush_all()
    return type(user)._base_manager.filter(pk=user.pk).values_list(
        'group_count', flat=True).get()


def test_linking_from_the_group_recomputes_the_user(user, group):
    related_manager(group, 'user_ids').add(user)
    assert stored_count(user) == 1


def test_unlinking_from_the_group_recomputes_the_user(user, group):
    related_manager(user, 'group_ids').add(group)
    assert stored_count(user) == 1
    related_manager(group, 'user_ids').remove(user)
    assert stored_count(user) == 0


def test_clearing_from_the_group_recomputes_the_user(user, group):
    related_manager(user, 'group_ids').add(group)
    assert stored_count(user) == 1
    related_manager(group, 'user_ids').clear()
    assert stored_count(user) == 0


def test_writing_from_the_user_already_recomputed(user, group):
    """Control: el lado dueño ya se avisaba antes de esta unidad."""
    related_manager(user, 'group_ids').add(group)
    assert stored_count(user) == 1
