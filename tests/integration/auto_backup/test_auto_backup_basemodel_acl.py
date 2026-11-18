"""``auto_backup`` sobre ``BaseModel`` y con la seguridad de la fuente.

≙ ``odoo-tools: 18.x/app-odoo-18.0/app_auto_backup`` (LGPL-3):
``models/db_backup.py:27-29`` y ``models/db_backup_details.py:9-12`` (los
dos son ``BaseModel``), ``security/user_groups.xml`` (el grupo
``group_manager``, implicado por ``base.group_system``) y
``security/ir.model.access.csv`` (tres filas). Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
basemodel-adoption-auto-backup.md``.
"""
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.db import DEFAULT_DB_ALIAS

from addons.auto_backup.models.db_backup import DbBackup
from addons.auto_backup.models.db_backup_details import DbBackupDetails
from addons.base.models import IrModelAccess, IrModelData
from exceptions import AccessError
from modules.loading import load_data
from modules.module import get_manifest
from orm.environments import Environment, sudo, user_scope
from orm.models import BaseModel
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db


def _ref(module, name):
    return IrModelData.objects.get(module=module, name=name).res_id


def _user(login, *xmlids):
    with sudo():
        user = get_user_model().objects.create_user(
            login=login, password=None, name=login)
    for xmlid in xmlids:
        user.group_ids.add(MODELS_BY_NAME['res.groups'].objects.get(
            pk=_ref(*xmlid.split('.'))))
    return user


@pytest.mark.parametrize('model', [DbBackup, DbBackupDetails])
def test_both_models_are_base_models(model):
    assert issubclass(model, BaseModel)


@pytest.fixture
def installed_data():
    """Los datos del manifiesto como los deja una instalación nueva.

    Se cargan por ``load_data`` en ``mode='init'``, el mismo paso del ciclo
    de instalación, así que la prueba mide la lista ``data`` del manifiesto y
    no una copia. ``base.group_system`` es ``noupdate`` y en modo de
    actualización no se reescribiría (``AND NOT ir_model_data.noupdate``,
    igual que la fuente). La base reutilizada ya trae las filas del ACL; se
    retiran antes, para que sólo las cree el manifiesto.
    """
    loaded = IrModelData.objects.filter(module='auto_backup',
                                        model='base.IrModelAccess')
    with sudo():
        IrModelAccess.objects.filter(
            pk__in=list(loaded.values_list('res_id', flat=True))).delete()
    loaded.delete()
    package = SimpleNamespace(name='auto_backup',
                              manifest=get_manifest('auto_backup'))
    load_data({}, 'init', 'data', package, using=DEFAULT_DB_ALIAS)


def test_the_system_group_implies_the_backup_manager(installed_data):
    """Al instalar, ``base.group_system`` implica a ``group_manager``."""
    groups = MODELS_BY_NAME['res.groups'].objects
    manager = groups.get(pk=_ref('auto_backup', 'group_manager'))
    system = groups.get(pk=_ref('base', 'group_system'))
    assert manager.name == 'Manager'
    assert manager in system.implied_ids.all()


def test_the_acl_is_the_reference_csv_with_its_external_ids(installed_data):
    loaded = IrModelData.objects.filter(module='auto_backup',
                                        model='base.IrModelAccess')
    rows = {name: IrModelAccess.objects.get(pk=loaded.get(name=name).res_id)
            for name in loaded.values_list('name', flat=True)}
    assert {name: (row.perm_read, row.perm_write, row.perm_create,
                   row.perm_unlink) for name, row in rows.items()} == {
        'admin_access': (True, True, True, True),
        'admin_security_rule': (True, True, True, True),
        'admin_db_backup_details': (True, True, True, True),
    }


def test_only_a_backup_manager_reads_the_backups(installed_data):
    internal = _user('backup-acl-internal', 'base.group_user')
    with user_scope(internal.pk), pytest.raises(AccessError):
        Environment(uid=internal.pk)['db.backup.details'].search([])
    admin = _user('backup-acl-system', 'base.group_user', 'base.group_system')
    with user_scope(admin.pk):
        found = Environment(uid=admin.pk)['db.backup.details'].search([])
    assert not found
