"""``res.users`` nace con sus grupos por defecto.

≙ ``_default_groups`` (``odoo19c: odoo/addons/base/models/res_users.py:
203-212``) y el ``default`` de ``group_ids`` (``:257``): sin ``group_ids``
en ``vals``, ``base.group_user`` más los implicados de
``base.default_user_group``. Diseño: ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/res-users-default-groups.md``.

*Métrica:* los grupos de un usuario recién creado.
*Ciega a:* la creación por ``signup`` desde una plantilla, que trae sus
propios grupos.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrModelData

pytestmark = pytest.mark.django_db


def test_a_user_created_without_groups_is_an_employee():
    user = get_user_model().objects.create_user(login='default-groups@x.mx')
    expected = {IrModelData.ref('base.group_user').pk}
    default_group = IrModelData.ref('base.default_user_group',
                                    raise_if_not_found=False)
    if default_group:
        expected |= set(default_group.implied_ids.values_list('pk', flat=True))
    assert set(user.group_ids.values_list('pk', flat=True)) == expected


def test_explicit_groups_replace_the_default():
    portal = IrModelData.ref('base.group_portal')
    user = get_user_model().objects.create_user(
        login='portal-groups@x.mx', group_ids=[portal])
    assert list(user.group_ids.values_list('pk', flat=True)) == [portal.pk]
    nobody = get_user_model().objects.create_user(
        login='no-groups@x.mx', group_ids=[])
    assert not nobody.group_ids.exists()
