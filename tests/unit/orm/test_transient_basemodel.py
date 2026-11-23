"""Un transitorio es un ``BaseModel``, con la ACL de su app.

≙ ``odoo19c: odoo/orm/models_transient.py:10`` (``TransientModel(Model)``)
y ``odoo19c: odoo/orm/models.py:7049`` (``Model`` deriva de
``BaseModel``). Las filas son copia fiel de
``odoo19c: addons/base_import_module/security/ir.model.access.csv:2`` y
``odoo19c: addons/base_install_request/security/ir.model.access.csv:2-7``.
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
basemodel-adoption-transient.md``.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrModelAccess, IrModelData
from addons.base_import_module.models import BaseImportModule
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope
from orm.models import BaseModel
from orm.models_transient import TransientModel
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db


def _user(login, *groups):
    with sudo():
        user = get_user_model().objects.create_user(
            login=login, password=None, name=login)
    for name in groups:
        user.group_ids.add(MODELS_BY_NAME['res.groups'].objects.get(
            pk=IrModelData.objects.get(module='base', name=name).res_id))
    return user


def test_a_transient_model_is_a_base_model():
    assert issubclass(TransientModel, BaseModel)


@pytest.mark.parametrize('module, xmlids', [
    ('base_import_module', ['access_base_import_module']),
    ('base_install_request', [
        'access_base_module_install_request',
        'access_base_module_install_review',
        'access_ir_module_category_group_user',
        'access_ir_module_module_dependency_group_user',
        'access_ir_module_module_exclusion_group_user',
        'access_ir_module_module_group_user',
    ]),
])
def test_the_wizard_acl_is_the_reference_csv(module, xmlids):
    loaded = IrModelData.objects.filter(module=module,
                                        model='ir.model.access')
    assert sorted(loaded.values_list('name', flat=True)) == xmlids


def test_the_import_wizard_is_for_system_users_only():
    row = IrModelAccess.objects.get(pk=IrModelData.objects.get(
        module='base_import_module', name='access_base_import_module').res_id)
    perms = (row.perm_read, row.perm_write, row.perm_create, row.perm_unlink)
    assert perms == (True, True, True, False)
    internal = _user('import-wizard-internal', 'group_user')
    with user_scope(internal.pk), pytest.raises(AccessError):
        Environment(uid=internal.pk)['base.import.module'].create({})
    admin = _user('import-wizard-system', 'group_user', 'group_system')
    with user_scope(admin.pk):
        wizard = Environment(uid=admin.pk)['base.import.module'].create({})
    assert wizard.state == 'init'
    assert isinstance(BaseImportModule.objects.get(pk=wizard.id),
                      BaseImportModule)
