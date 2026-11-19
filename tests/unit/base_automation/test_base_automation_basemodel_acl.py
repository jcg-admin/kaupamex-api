"""``base_automation`` sobre ``BaseModel`` y con la ACL de la referencia.

≙ ``odoo19c: addons/base_automation/models/base_automation.py:125-127``
y ``odoo19c: addons/base_automation/security/ir.model.access.csv`` (una
fila: los cuatro permisos para ``base.group_system``). Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
basemodel-adoption-base-automation.md``.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrModelAccess, IrModelData
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope
from orm.models import BaseModel
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db


@pytest.fixture
def superuser_env():
    """Sin el entorno de superusuario del ``conftest``: estas pruebas miden
    la ACL, y la última abre su propio usuario interno."""
    yield None


def test_the_automation_rule_is_a_base_model():
    model = MODELS_BY_NAME['base.automation']
    assert issubclass(model, BaseModel)
    assert model.__dict__['_description'] == 'Automation Rule'


def test_the_acl_is_the_reference_csv_with_its_external_id():
    xmlids = IrModelData.objects.filter(module='base_automation',
                                        model='base.IrModelAccess')
    assert xmlids.count() == 1
    row = IrModelAccess.objects.get(
        pk=xmlids.get(name='access_base_automation_config').res_id)
    perms = (row.perm_read, row.perm_write, row.perm_create, row.perm_unlink)
    assert perms == (True, True, True, True)


def test_an_internal_user_cannot_read_a_rule():
    group = MODELS_BY_NAME['res.groups'].objects.get(
        pk=IrModelData.objects.get(module='base', name='group_user').res_id)
    with sudo():
        user = get_user_model().objects.create_user(
            login='automation-acl-internal', password=None, name='interno')
    user.group_ids.add(group)
    with user_scope(user.pk):
        rules = Environment(uid=user.pk)['base.automation']
        with pytest.raises(AccessError):
            rules.check_access('read')
