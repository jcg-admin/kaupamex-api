"""``res.users.share`` como campo calculado y almacenado.

≙ ``odoo19c: odoo/addons/base/models/res_users.py:234-235,459-464``: interno
es quien tiene ``base.group_user`` en ``all_group_ids`` (la clausura), y el
valor vive en una columna buscable
(``designs/base-res-users-share-field-0356.md``).
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models.ir_model import IrModelData
from addons.base.models.res_groups import ResGroups
from orm.commands import related_manager
from orm.environments import env as current_env

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def group_user():
    return ResGroups.objects.get(pk=IrModelData._xmlid_to_res_id(
        'base.group_user', raise_if_not_found=True))


def account(login):
    """Una cuenta sin los grupos por defecto (``_default_groups``)."""
    return User.objects.create_user(login=login, group_ids=[])


def stored_share(user):
    """El valor de la columna tras volcar los recómputos pendientes."""
    current_env().flush_all()
    return User._base_manager.filter(pk=user.pk).values_list(
        'share', flat=True).get()


def test_share_is_a_stored_compute():
    field = User._meta.get_field('share')
    assert field.concrete
    assert (field.compute, field.store) == ('_compute_share', True)


def test_a_group_implying_group_user_makes_the_user_internal(group_user):
    staff = ResGroups.objects.create(name='Staff 0356')
    related_manager(staff, 'implied_ids').add(group_user)
    user = account('share.closure@kaupamex.mx')
    related_manager(staff, 'user_ids').add(user)
    assert stored_share(user) is False


def test_adding_and_removing_group_user_recomputes(group_user):
    user = account('share.toggle@kaupamex.mx')
    assert stored_share(user) is True
    related_manager(group_user, 'user_ids').add(user)
    assert stored_share(user) is False
    related_manager(group_user, 'user_ids').remove(user)
    assert stored_share(user) is True


def test_share_is_searchable(group_user):
    internal = account('share.search.internal@kaupamex.mx')
    external = account('share.search.external@kaupamex.mx')
    related_manager(group_user, 'user_ids').add(internal)
    current_env().flush_all()
    # ``res.users`` es un modelo de Django: buscable es filtrable por la
    # columna, el ``('share', '=', False)`` de la fuente.
    found = User._base_manager.filter(
        share=False, pk__in=[internal.pk, external.pk])
    assert list(found.values_list('pk', flat=True)) == [internal.pk]


def test_changing_an_implication_recomputes(group_user):
    staff = ResGroups.objects.create(name='Staff 0356 later')
    user = account('share.implication@kaupamex.mx')
    related_manager(staff, 'user_ids').add(user)
    assert stored_share(user) is True
    related_manager(staff, 'implied_ids').add(group_user)
    assert stored_share(user) is False


def test_an_internal_user_type_alone_is_not_group_user():
    """La regla es literal: ``base.group_user``, no un tipo de grupo."""
    own = ResGroups.objects.create(
        name='Internos propios 0356', user_type=ResGroups.USER_TYPE_INTERNAL)
    user = account('share.own.internal@kaupamex.mx')
    related_manager(own, 'user_ids').add(user)
    assert stored_share(user) is True
