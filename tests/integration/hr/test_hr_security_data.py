"""Los datos de seguridad de ``hr`` y ``hr_skills`` entran por su manifiesto.

≙ ``odoo19c: addons/hr/__manifest__.py:21-22`` y
``addons/hr_skills/__manifest__.py:17-19``: ``security/*.xml`` e
``ir.model.access.csv`` en la clave ``data``, que ``load_data`` lee al
instalar. Aquí los lee el mismo ciclo (``modules.loading.load_modules``,
L3). Diseño: ``designs/module-install-cycle.md``, L4c.
"""
import pytest

from addons.base.models import IrModelData
from addons.base.models.ir_model import IrModelAccess
from addons.base.models.ir_rule import IrRule
import modules.loading as loading

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _installed(db):
    """La base de pruebas ya pasó por el ciclo; se vuelve a ejecutar para
    medirlo dentro de la transacción de la prueba."""
    loading.load_modules('default')


def _ref(xmlid):
    return IrModelData.ref(xmlid)


def test_the_hr_groups_hang_from_their_privilege():
    officer = _ref('hr.group_hr_user')
    manager = _ref('hr.group_hr_manager')
    assert officer.privilege == _ref('hr.res_groups_privilege_employees')
    assert _ref('base.group_user') in officer.implied_ids.all()
    assert officer in manager.implied_ids.all()
    assert _ref('hr.res_groups_privilege_employees').category == _ref(
        'base.module_category_human_resources')


def test_the_access_rows_of_the_source_are_loaded():
    hr_rows = IrModelData.objects.filter(
        module='hr', model='base.IrModelAccess')
    skills_rows = IrModelData.objects.filter(
        module='hr_skills', model='base.IrModelAccess')
    assert hr_rows.count() == 20
    assert skills_rows.count() == 14
    employee_user = _ref('hr.access_hr_employee_user')
    assert isinstance(employee_user, IrModelAccess)
    assert employee_user.group_id == _ref('hr.group_hr_user')
    assert (employee_user.perm_read, employee_user.perm_write,
            employee_user.perm_create, employee_user.perm_unlink) == (
        True, True, True, True)


def test_the_rules_of_the_source_are_loaded():
    employee_rule = _ref('hr.hr_employee_comp_rule')
    bank_rule = _ref('hr.ir_rule_res_partner_bank_internal_users')
    assert isinstance(employee_rule, IrRule)
    assert "('user_id', '=', user.id)" in employee_rule.domain_force
    assert bank_rule.domain_force == (
        "[('partner_id.employee_ids', '=', False)]")
    assert list(bank_rule.groups.all()) == [_ref('base.group_user')]
    assert _ref('hr_skills.hr_skill_rule_employee_update').domain_force == (
        "[('employee_id.user_id','=',user.id)]")
