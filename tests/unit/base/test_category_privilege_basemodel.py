"""``ir.module.category`` y ``res.groups.privilege`` son ``BaseModel``.

``class IrModuleCategory(models.Model)``
(``odoo19c: odoo/addons/base/models/ir_module.py:76``) y
``class ResGroupsPrivilege(models.Model)``
(``odoo19c: odoo/addons/base/models/res_groups_privilege.py:4``): con
``BaseModel`` la ACL sembrada les aplica, y quien no puede leer un privilegio
recibe ``PermissionDenied``. Por eso ``_compute_full_name`` lo lee con
privilegio, como el ``zip(self, self.sudo())`` de la fuente
(``odoo19c: res_groups.py:123-129``).
"""

import models
import pytest
from django.contrib.auth import get_user_model

from addons.base.models.ir_module import IrModuleCategory
from addons.base.models.res_groups import ResGroups
from addons.base.models.res_groups_privilege import ResGroupsPrivilege
from orm.environments import user_scope

pytestmark = [pytest.mark.unit]


@pytest.mark.parametrize('model', [IrModuleCategory, ResGroupsPrivilege])
def test_category_and_privilege_are_basemodel(model):
    """Cada uno hereda ``BaseModel``, no sólo las columnas de auditoría."""
    assert issubclass(model, models.BaseModel)


@pytest.mark.django_db
def test_full_name_reads_the_privilege_for_a_user_who_cannot():
    """Un usuario sin grupo no puede leer ``res.groups.privilege``, y aun así
    el nombre completo del grupo lleva el nombre del privilegio."""
    privilege = ResGroupsPrivilege.objects.create(name='Panel 397')
    group = ResGroups.objects.create(name='Lector 397', privilege=privilege)
    user = get_user_model().objects.create_user(
        login='privilege.reader@kaupamex.mx', group_ids=[])
    with user_scope(user.pk):
        group = ResGroups.objects.get(pk=group.pk)
        assert group.full_name == 'Panel 397 / Lector 397'
