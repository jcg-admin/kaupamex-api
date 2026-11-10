"""Las rutas de ``user`` que evalúan las reglas de ``hr``.

≙ ``odoo19c: addons/hr/security/hr_security.xml`` (``hr_employee_comp_rule``)::

    ('parent_id.user_id', '=', user.id),
    ('id', '=', user.employee_id.parent_id.id),

En la fuente ``hr.employee`` es un modelo del ORM: ``user.employee_id`` es un
recordset (vacío si no hay empleado, ``hr/models/res_users.py:64-65`` y
``:266-272``) y ``parent_id`` es su ``Many2one`` (``hr_employee.py:193-195``),
así que ``.parent_id.id`` es ``False`` sobre lo vacío. Diseño:
``designs/module-install-cycle.md``, L4e (e1-e3).
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models.ir_rule import IrRule
from addons.hr.models import HrEmployee
from orm.environments import sudo, user_scope
from orm.models import BaseModel
from orm.utils import model_field_registry

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _as_superuser(db):
    with sudo():
        yield


def _user(login):
    return get_user_model().objects.create_user(
        login=login, password=None, name=login)


def test_the_employee_is_an_orm_model():
    assert issubclass(HrEmployee, BaseModel)


def test_parent_id_is_the_manager_field():
    field = model_field_registry(HrEmployee)['parent_id']
    assert field.related_model is HrEmployee
    assert field.column == 'parent_id'
    assert field.remote_field.related_name == 'child_ids'


def test_a_user_without_employee_reads_an_empty_manager():
    user = _user('rule-path-no-employee')
    assert not user.employee_id
    assert user.employee_id.parent_id.id is False


def test_a_user_with_employee_reads_its_manager():
    manager = HrEmployee.objects.create(name='Gerente')
    user = _user('rule-path-employee')
    employee = HrEmployee.objects.create(
        name='Subordinado', user_id=user, parent_id=manager)
    assert user.employee_id.id == employee.pk
    assert user.employee_id.parent_id.id == manager.pk
    assert manager.child_ids.ids == [employee.pk]


def test_the_rule_context_takes_the_acting_user():
    """≙ ``_eval_context`` (``ir_rule.py:38-51``): ``user`` es
    ``self.env.user``. Sin usuario explícito, el del entorno — al instalar,
    ``base.user_root`` — y no ``None``."""
    user = get_user_model().objects.create_user(
        login='rule-context-user', password=None, name='Contexto')
    with user_scope(user.pk):
        assert IrRule._eval_context()['user'] == user
