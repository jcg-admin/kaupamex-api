"""``hr.employee.user_id`` — Many2one almacenado sobre el usuario del recurso.

≙ ``odoo19c: addons/hr/models/hr_employee.py:86-94``::

    user_id = fields.Many2one(
        'res.users', 'User',
        related='resource_id.user_id',
        store=True,
        readonly=False,
        check_company=True,
        precompute=True,
        index='btree_not_null',
        ondelete='restrict')

Es la ruta que filtran las reglas de ``hr`` y ``hr_skills``
(``hr_employee_comp_rule``, ``hr_skill_rule_employee_update``…), así que
tiene que ser un campo y no una ``property``. Diseño:
``designs/module-install-cycle.md``, L4a.
"""
import importlib
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection, models

from addons.hr.models import HrEmployee
from orm.environments import sudo
from orm.utils import model_field_registry

#: El módulo de migración empieza por un número: se carga por su nombre.
copy_the_resource_user = importlib.import_module(
    'addons.hr.migrations.0014_hremployee_user').copy_the_resource_user

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _as_superuser(db):
    """Estas pruebas miden la conducta del campo, no el acceso: guardar el
    recurso lee su usuario delegado, que un contexto sin usuario no puede
    leer. El acceso por privilegio lo mide la unidad L5."""
    with sudo():
        yield


def _user(login):
    return get_user_model().objects.create_user(
        login=login, password=None, name=login)


def test_it_is_a_stored_many2one_to_the_users():
    field = HrEmployee._meta.get_field('user_id')
    assert field.related_model is get_user_model()
    assert field.attname == 'user_id_id'
    assert field.remote_field.on_delete is models.PROTECT
    assert field.null


def test_the_rules_can_filter_by_it():
    assert model_field_registry(HrEmployee)['user_id'] is (
        HrEmployee._meta.get_field('user_id'))


def test_it_follows_the_user_of_its_resource():
    user = _user('employee-user-follow')
    employee = HrEmployee.objects.create(name='Sigue al recurso')
    employee.resource.user = user
    employee.resource.save()
    employee.save()
    employee.refresh_from_db()
    assert employee.user_id_id == user.pk


def test_writing_it_writes_the_resource():
    """``readonly=False`` en la fuente: escribir el relacionado escribe su
    origen, el usuario del recurso."""
    user = _user('employee-user-write')
    employee = HrEmployee.objects.create(name='Escribe el recurso')
    employee.user_id = user
    employee.save()
    employee.resource.refresh_from_db()
    assert employee.resource.user_id == user.pk


def test_it_is_queryable():
    user = _user('employee-user-query')
    employee = HrEmployee.objects.create(name='Consultable', user_id=user)
    assert list(HrEmployee.objects.filter(user_id=user)) == [employee]


def test_the_migration_fills_the_existing_rows():
    """``0014_hremployee_user`` copia el usuario del recurso en las filas que
    ya existían, como ``_auto_init`` calcula una columna almacenada nueva."""
    user = _user('employee-user-migration')
    employee = HrEmployee.objects.create(name='Fila previa')
    type(employee.resource).objects.filter(pk=employee.resource_id).update(
        user=user)
    HrEmployee.objects.filter(pk=employee.pk).update(user_id=None)
    copy_the_resource_user(apps, SimpleNamespace(connection=connection))
    employee.refresh_from_db()
    assert employee.user_id_id == user.pk
