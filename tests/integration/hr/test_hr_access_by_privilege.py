"""L5 — el acceso a ``hr`` según el privilegio, con los datos de la fuente.

≙ ``odoo19c: addons/hr/security/ir.model.access.csv``: ``hr.employee`` lo
leen y escriben los oficiales de HR (``hr.group_hr_user``); el usuario
interno lee ``hr.employee.public`` y no ``hr.employee``; el administrador
(``group_hr_manager``) hereda el oficial por ``implied_ids``; el
superusuario no consulta la tabla (``ir_model.py:2153``). Los datos los carga
el ciclo de instalación (L3/L4c), no esta prueba. Diseño:
``designs/module-install-cycle.md``, L5.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrModelData
from addons.base.models.ir_model import IrModelAccess
from orm.environments import sudo

pytestmark = pytest.mark.django_db

MODES = ('read', 'write', 'create', 'unlink')


def _user(login, *xmlids):
    user = get_user_model().objects.create_user(
        login=login, password=None, name=login)
    for xmlid in xmlids:
        user.group_ids.add(IrModelData.ref(xmlid))
    return user


def _modes(model, user):
    return tuple(IrModelAccess.check(model, mode, raise_exception=False,
                                     user=user) for mode in MODES)


def test_an_internal_user_reads_only_the_public_employee():
    user = _user('hr-acl-internal', 'base.group_user')
    assert _modes('hr.employee', user) == (False, False, False, False)
    assert _modes('hr.employee.public', user) == (True, False, False, False)


def test_the_hr_officer_has_the_four_modes_on_the_employee():
    user = _user('hr-acl-officer', 'base.group_user', 'hr.group_hr_user')
    assert _modes('hr.employee', user) == (True, True, True, True)


def test_the_hr_manager_inherits_the_officer():
    user = _user('hr-acl-manager', 'hr.group_hr_manager')
    assert IrModelData.ref('hr.group_hr_user').pk in user._get_group_ids()
    assert _modes('hr.employee', user) == (True, True, True, True)


def test_a_user_without_groups_has_no_access():
    user = _user('hr-acl-nobody')
    assert _modes('hr.employee', user) == (False, False, False, False)
    assert _modes('hr.employee.public', user) == (False, False, False, False)


def test_the_superuser_does_not_consult_the_table():
    user = _user('hr-acl-elevated')
    with sudo():
        assert _modes('hr.employee', user) == (True, True, True, True)


def test_without_its_row_the_internal_user_loses_the_public_read():
    """CONTROL — la lectura del público la da la fila de la fuente, no otra."""
    user = _user('hr-acl-control', 'base.group_user')
    IrModelData.ref('hr.access_hr_employee_public_user').delete()
    assert _modes('hr.employee.public', user) == (False, False, False, False)
