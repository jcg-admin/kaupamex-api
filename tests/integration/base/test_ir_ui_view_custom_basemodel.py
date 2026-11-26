"""``ir.ui.view.custom`` es ``BaseModel`` y lleva su regla personal.

``class IrUiViewCustom(models.Model)``
(``odoo19c: odoo/addons/base/models/ir_ui_view.py``) y la regla global
``ir_ui_view_custom_personal`` con ``[('user_id','=',user.id)]``
(``odoo19c: odoo/addons/base/security/base_security.xml:50-54``). La ACL es
sólo de ``group_system`` (``ir.model.access.csv:38``), así que la regla se
mide entre dos administradores: cada uno ve sólo su personalización.
"""

import models
import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrModelData
from addons.base.models.ir_rule import IrRule
from addons.base.models.ir_ui_view import IrUiView, IrUiViewCustom
from orm.environments import Environment, sudo, user_scope
from orm.registry import MODELS_BY_NAME

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def _admin(login):
    with sudo():
        user = get_user_model().objects.create_user(
            login=login, password=None, name=login)
    for xmlid in ('base.group_user', 'base.group_system'):
        user.group_ids.add(MODELS_BY_NAME['res.groups'].objects.get(
            pk=IrModelData._xmlid_to_res_id(xmlid, raise_if_not_found=True)))
    return user


def test_view_custom_is_basemodel():
    assert issubclass(IrUiViewCustom, models.BaseModel)


def test_the_personal_rule_is_seeded_global():
    rule = IrRule.objects.get(name='ir.ui.view_custom rule')
    assert rule.domain_force == "[('user_id','=',user.id)]"
    assert not rule.groups.exists()
    assert (rule.perm_read, rule.perm_write, rule.perm_create,
            rule.perm_unlink) == (True, True, True, True)


def test_each_user_sees_only_their_customization():
    first, second = _admin('view-custom-a'), _admin('view-custom-b')
    with sudo():
        view = IrUiView.objects.create(
            name='view custom probe', model='res.partner', type='form',
            arch_db='<form/>')
        mine = IrUiViewCustom.objects.create(
            ref_id=view, user=first, arch='<form string="a"/>')
        IrUiViewCustom.objects.create(
            ref_id=view, user=second, arch='<form string="b"/>')
    with user_scope(first.pk):
        found = Environment(uid=first.pk)['ir.ui.view.custom'].search([])
    assert found.ids == [mine.pk]
