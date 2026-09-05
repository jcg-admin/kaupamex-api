"""``hr_recruitment/models/digest.py`` — el KPI de nuevos empleados
(tarea #159).

Adaptación de ``odoo19c: addons/hr_recruitment/models/digest.py:12-17``
(LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Hasta este pase el archivo declaraba el compute BLOQUEADO por
``_calculate_company_based_kpi``, que ``crm`` había portado días antes: la
causa ya no existía. Se ejerce por la puerta que el árbol usa —
``digest.compute_kpi_value(...)``, que despacha al método instalado por
``extend_model``— para que un ``metodos=`` mal cableado caiga aquí.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from addons.base.models import ResCompany
from addons.base.models.ir_model import IrModelData
from addons.base.models.res_groups import ResGroups
from addons.digest.models import DigestDigest
from addons.hr.models import HrEmployee
from addons.hr_recruitment.models.digest import GROUP_HR_RECRUITMENT_USER
from exceptions import AccessError
from orm.environments import user_scope
from tests.factories.user_factory import UserFactory

pytestmark = pytest.mark.django_db

TODAY = timezone.now()
START = TODAY - timedelta(days=7)
END = TODAY + timedelta(days=1)


@pytest.fixture
def company():
    return ResCompany.objects.create(
        code='digest-colleagues-co', name='Digest Colleagues Co')


@pytest.fixture
def digest(company):
    return DigestDigest.objects.create(
        name='Digest de empleados', company_id=company)


@pytest.fixture
def recruiter():
    """Un usuario dentro de ``hr_recruitment.group_hr_recruitment_user``."""
    user = UserFactory(login='reclutamiento@kaupamex.mx')
    group = ResGroups.objects.create(name='Reclutamiento (fixture)')
    IrModelData.set_xmlid(group, GROUP_HR_RECRUITMENT_USER)
    user.group_ids.add(group)
    return user


@pytest.fixture
def outsider():
    return UserFactory(login='ajeno-hr@kaupamex.mx')


class TestNewColleaguesCountsEmployeesOfTheCompany:
    """≙ ``self._calculate_company_based_kpi('hr.employee', …)``."""

    def test_counts_the_employees_created_in_the_window(
        self, digest, company, recruiter,
    ):
        HrEmployee.objects.create(name='Primera contratación',
                                  company=company)
        HrEmployee.objects.create(name='Segunda contratación',
                                  company=company)
        with user_scope(recruiter.pk):
            value = digest.compute_kpi_value(
                'kpi_hr_recruitment_new_colleagues', START, END)
        assert value == 2

    def test_no_hires_gives_zero(self, digest, company, recruiter):
        with user_scope(recruiter.pk):
            value = digest.compute_kpi_value(
                'kpi_hr_recruitment_new_colleagues', START, END)
        assert value == 0

    def test_another_company_is_not_counted(self, digest, company, recruiter):
        other = ResCompany.objects.create(
            code='digest-colleagues-other', name='Otra Co')
        HrEmployee.objects.create(name='De la otra empresa', company=other)
        with user_scope(recruiter.pk):
            value = digest.compute_kpi_value(
                'kpi_hr_recruitment_new_colleagues', START, END)
        assert value == 0

    def test_a_hire_outside_the_window_is_not_counted(
        self, digest, company, recruiter,
    ):
        employee = HrEmployee.objects.create(name='Contratación vieja',
                                             company=company)
        HrEmployee.objects.filter(pk=employee.pk).update(
            created_at=TODAY - timedelta(days=30))
        with user_scope(recruiter.pk):
            value = digest.compute_kpi_value(
                'kpi_hr_recruitment_new_colleagues', START, END)
        assert value == 0


class TestAccessGuard:
    """≙ ``if not self.env.user.has_group('hr_recruitment.
    group_hr_recruitment_user'): raise AccessError(...)``."""

    def test_user_outside_the_group_is_refused(
        self, digest, company, outsider,
    ):
        with user_scope(outsider.pk), pytest.raises(AccessError):
            digest.compute_kpi_value(
                'kpi_hr_recruitment_new_colleagues', START, END)

    def test_no_current_user_is_refused_not_a_crash(self, digest, company):
        with user_scope(None), pytest.raises(AccessError):
            digest.compute_kpi_value(
                'kpi_hr_recruitment_new_colleagues', START, END)


class TestTheValueFieldHasNoColumn:
    """≙ ``fields.Integer(compute=…)`` sin ``store``: la fuente no le da
    columna, y aquí tampoco — lo sirve el descriptor ``NonStored``."""

    def test_it_is_an_attribute_and_not_a_model_field(self):
        names = {f.name for f in DigestDigest._meta.get_fields()}
        assert 'kpi_hr_recruitment_new_colleagues_value' not in names
        assert hasattr(DigestDigest, 'kpi_hr_recruitment_new_colleagues_value')
