"""``base_security._seed`` siembra reglas por grupo y con permisos.

≙ los ``<record model="ir.rule">`` con ``groups`` y ``perm_*`` de
``odoo19c: odoo/addons/base/security/base_security.xml`` (p. ej.
``ir_filters_employee_rule``, ``:86-95``). Ver
``designs/base-security-group-rules-seed.md``.
"""

import pytest
from django.db import DEFAULT_DB_ALIAS

from addons.base.models.ir_model import IrModelData
from addons.base.models.ir_rule import IrRule
from addons.base.security.base_security import DOMAIN_MULTICOMPANY, _seed

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

SPEC = {
    'name': 'seed probe: own exports',
    'model': 'base.IrExports',
    'domain_force': "[('create_uid', '=', user.id)]",
    'groups': ['base.group_user'],
    'perm_read': True, 'perm_write': False,
    'perm_create': True, 'perm_unlink': False,
}


def _group_user_pk():
    return IrModelData._xmlid_to_res_id('base.group_user',
                                        raise_if_not_found=True)


def test_a_group_rule_keeps_its_groups_and_permissions():
    _seed(IrRule, [SPEC], DEFAULT_DB_ALIAS)
    rule = IrRule.objects.get(name=SPEC['name'])
    assert list(rule.groups.values_list('pk', flat=True)) == [_group_user_pk()]
    assert (rule.perm_read, rule.perm_write, rule.perm_create,
            rule.perm_unlink) == (True, False, True, False)
    assert rule.domain_force == SPEC['domain_force']


def test_seeding_twice_changes_nothing():
    _seed(IrRule, [SPEC], DEFAULT_DB_ALIAS)
    _seed(IrRule, [SPEC], DEFAULT_DB_ALIAS)
    rules = IrRule.objects.filter(name=SPEC['name'])
    assert rules.count() == 1
    assert rules.get().groups.count() == 1


def test_a_tuple_entry_still_seeds_the_global_multicompany_rule():
    _seed(IrRule, [('seed probe: multicompany', 'base.CompanySetting')],
          DEFAULT_DB_ALIAS)
    rule = IrRule.objects.get(name='seed probe: multicompany')
    assert rule.domain_force == DOMAIN_MULTICOMPANY
    assert not rule.groups.exists()
