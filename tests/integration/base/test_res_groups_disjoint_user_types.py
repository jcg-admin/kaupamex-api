"""Grupos de tipo de usuario disjuntos, por pertenencia transitiva.

``odoo19c: odoo/addons/base/models/res_users.py:536-548`` comprueba la
exclusión sobre ``user.all_group_ids`` —la clausura—, y su docstring dice por
qué: *"This could typically happen because of implied groups."*
``odoo19c: odoo/addons/base/models/res_groups.py:92-112`` busca, entre los
usuarios **activos** del grupo, uno cuya clausura toque dos grupos de tipo de
usuario, y delega el error en ``_check_disjoint_groups``. Es el escenario de
``odoo19c: odoo/addons/base/tests/test_user_has_group.py:69-110``: un grupo
sin tipo que implica el de portal, sobre un usuario interno.

``_apply_group`` y ``_remove_group`` (``res_groups.py:308-320``) son privados
en la fuente y se usan como en ``test_base.py:335-370``.
"""
import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from addons.base.models.res_groups import ResGroups

User = get_user_model()


@pytest.fixture
def user_types(db):
    internal = ResGroups.objects.create(
        name='Internal', user_type=ResGroups.USER_TYPE_INTERNAL)
    portal = ResGroups.objects.create(
        name='Portal', user_type=ResGroups.USER_TYPE_PORTAL)
    return internal, portal


def _user(login, active=True):
    user = User.objects.create_user(login=login)
    if not active:
        User.objects.filter(pk=user.pk).update(active=False)
        user.refresh_from_db()
    return user


def test_an_implied_user_type_is_seen_by_the_user_check(user_types):
    internal, portal = user_types
    implies_portal = ResGroups.objects.create(name='Implies portal')
    implies_portal.implied_ids.add(portal)
    user = _user('implied@kaupamex.mx')
    internal.user_ids.add(user)
    implies_portal.user_ids.add(user)
    with pytest.raises(ValidationError):
        user._check_disjoint_groups()


def test_one_user_type_through_implication_passes(user_types):
    internal, _portal = user_types
    implies_internal = ResGroups.objects.create(name='Implies internal')
    implies_internal.implied_ids.add(internal)
    user = _user('single@kaupamex.mx')
    internal.user_ids.add(user)
    implies_internal.user_ids.add(user)
    user._check_disjoint_groups()


def test_the_group_check_finds_the_user_of_an_untyped_group(user_types):
    internal, portal = user_types
    implies_portal = ResGroups.objects.create(name='Implies portal')
    implies_portal.implied_ids.add(portal)
    user = _user('member@kaupamex.mx')
    internal.user_ids.add(user)
    implies_portal.user_ids.add(user)
    with pytest.raises(ValidationError):
        implies_portal._check_user_disjoint_groups()


def test_the_group_check_ignores_an_inactive_user(user_types):
    internal, portal = user_types
    implies_portal = ResGroups.objects.create(name='Implies portal')
    implies_portal.implied_ids.add(portal)
    user = _user('archived@kaupamex.mx', active=False)
    internal.user_ids.add(user)
    implies_portal.user_ids.add(user)
    implies_portal._check_user_disjoint_groups()


def test_the_group_check_passes_without_offender(user_types):
    internal, _portal = user_types
    user = _user('clean@kaupamex.mx')
    internal.user_ids.add(user)
    internal._check_user_disjoint_groups()


def test_the_graph_mutators_keep_their_private_names(db):
    a = ResGroups.objects.create(name='A')
    b = ResGroups.objects.create(name='B')
    c = ResGroups.objects.create(name='C')
    c.implied_ids.add(a)
    b._apply_group(a)
    c._apply_group(a)
    assert a in b.implied_ids.all() and a in c.implied_ids.all()
    b._remove_group(a)
    assert a not in b.implied_ids.all()
    publics = ('apply_group', 'remove_group', 'check_user_disjoint_groups')
    for public in publics:
        assert not hasattr(ResGroups, public), public
