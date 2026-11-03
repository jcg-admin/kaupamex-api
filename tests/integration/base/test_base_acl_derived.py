"""La ACL de ``base`` derivada del CSV de la referencia (:ref:`h-api-1143`).

``_ACCESS`` se genera con ``derive_base_acl.py`` desde
``odoo19c: odoo/addons/base/security/ir.model.access.csv``; la migración
``0096`` lleva el resultado a las bases ya creadas.
"""

import pytest

from addons.base.models.ir_model import IrModelAccess
from addons.base.security.ir_model_access import _ACCESS, seed

pytestmark = pytest.mark.django_db

RENAMED = ('ir_module_category', 'ir_module_module',
           'ir_module_module_dependency', 'res_users group_portal',
           'res_users group_public', 'res_users group_user',
           'res_users_apikeys group_portal', 'res_users_apikeys group_user')


def test_each_row_is_unique_by_name_model_and_group():
    keys = [(name, label, group) for name, label, group, _ in _ACCESS]
    assert len(keys) == len(set(keys))


def test_a_name_the_csv_repeats_is_seeded_once_per_group():
    """``res_company group_user`` sale tres veces en el CSV, para público,
    portal e interno. Con el nombre como única clave sólo se sembraba una."""
    declared = [group for name, label, group, _ in _ACCESS
                if name == 'res_company group_user']
    assert sorted(declared) == ['group_portal', 'group_public', 'group_user']
    IrModelAccess.objects.filter(name='res_company group_user').delete()
    seed()
    seeded = IrModelAccess.objects.filter(name='res_company group_user')
    assert seeded.count() == 3


def test_no_row_keeps_an_invented_name():
    assert not IrModelAccess.objects.filter(name__in=RENAMED).exists()
    assert IrModelAccess.objects.filter(name='res_users all').count() == 3
