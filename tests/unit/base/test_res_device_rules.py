"""Las reglas de ``res.device`` y ``res.device.log``, y la inversa del usuario.

≙ ``odoo19c: odoo/addons/base/security/base_security.xml:229-252`` y
``res.users.device_ids``
(``odoo19c: odoo/addons/base/models/res_users.py:232``).
Diseño: ``designs/basemodel-adoption-res-device.md`` (primer paso).
"""

import pytest

from addons.base.models import IrModelData
from addons.base.models.ir_rule import IrRule
from addons.base.models.res_users import ResUsers

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

RULES = {
    'Users can read only their own devices':
        ('base.group_user', "[('user_id', '=', user.id)]"),
    'Administrators can read all devices':
        ('base.group_system', "[(1, '=', 1)]"),
    'Users can read only their own device logs':
        ('base.group_user', "[('user_id', '=', user.id)]"),
    'Administrators can read all device logs':
        ('base.group_system', "[(1, '=', 1)]"),
}


@pytest.mark.parametrize('name', sorted(RULES))
def test_each_source_rule_is_seeded(name):
    xmlid, domain = RULES[name]
    rule = IrRule.objects.get(name=name)
    group = IrModelData._xmlid_to_res_id(xmlid, raise_if_not_found=True)
    assert rule.domain_force == domain
    assert list(rule.groups.values_list('pk', flat=True)) == [group]


def test_the_user_inverse_is_device_ids():
    assert ResUsers._meta.get_field('device_ids').related_model._name == (
        'res.device')
