"""Los lectores de habilidades de ``hr_skills`` como recordsets.

``hr.employee``, ``hr.employee.skill``, ``hr.skill.type``, ``hr.skill.level``,
``hr.resume.line``, ``resource.resource`` y ``hr.employee.public`` son
``BaseModel``: sus One2many y Many2many son recordsets, como en la fuente,
y estos sitios los leían con el gestor de Django. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
basemodel-reverse-queryset.md``.

≙ ``odoo19c: addons/hr_skills/models/hr_employee.py`` (``:25-41``,
``:143-186``), ``hr_skill_level.py`` (``:29-40``), ``hr_skill_type.py``
(``levels_count``), ``resource_resource.py`` (``:9``),
``hr_employee_public.py`` (``:9-11``) y
``odoo19c: addons/project_hr_skills/models/res_users.py`` (``:8``).

*Métrica:* cada lector sobre registros creados por el ORM.
*Ciega a:* las vistas y el chequeo de acceso de ``get_internal_resume_lines``,
que el puerto declara fuera.
"""
from datetime import date

import pytest
from django.contrib.auth import get_user_model

from addons.hr.models.hr_employee import HrEmployee
from addons.hr_skills.models.hr_employee_skill import HrEmployeeSkill
from addons.hr_skills.models.hr_skill import HrSkill
from addons.hr_skills.models.hr_skill_level import HrSkillLevel
from addons.hr_skills.models.hr_skill_type import HrSkillType
from orm.environments import sudo

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff():
    regular = HrSkillType.objects.create(name='SRR Idiomas', sequence=-30)
    certification = HrSkillType.objects.create(
        name='SRR Certificados', sequence=-29, is_certification=True)
    language = HrSkill.objects.create(name='SRR Inglés', skill_type=regular)
    cloud = HrSkill.objects.create(name='SRR Nube', skill_type=certification)
    low = HrSkillLevel.objects.create(
        name='SRR B1', skill_type=regular, level_progress=50)
    HrSkillLevel.objects.create(
        name='SRR C1', skill_type=regular, level_progress=80)
    passed = HrSkillLevel.objects.create(
        name='SRR Aprobado', skill_type=certification, level_progress=100)
    employee = HrEmployee.objects.create(name='SRR Empleada')
    HrEmployeeSkill.objects.create(
        employee=employee, skill=language, skill_level=low,
        skill_type=regular, valid_from=date(2026, 1, 1))
    HrEmployeeSkill.objects.create(
        employee=employee, skill=cloud, skill_level=passed,
        skill_type=certification, valid_from=date(2026, 1, 1))
    return {'employee': employee, 'regular': regular, 'language': language,
            'cloud': cloud, 'low': low}


def _employee(staff):
    return HrEmployee.objects.get(pk=staff['employee'].pk)


def test_the_current_skills_are_the_active_ones(staff):
    with sudo():
        current = _employee(staff).current_employee_skill_ids
    assert {s.skill_id for s in current} == {
        staff['language'].pk, staff['cloud'].pk}


def test_the_skill_ids_compute_keeps_the_distinct_skills(staff):
    with sudo():
        employee = _employee(staff)
        employee._compute_skill_ids()
        assert set(employee.skill_ids.ids) == {
            staff['language'].pk, staff['cloud'].pk}


def test_the_certifications_are_the_certification_skills(staff):
    with sudo():
        certifications = _employee(staff).certification_ids
    assert [s.skill_id for s in certifications] == [staff['cloud'].pk]


def test_the_levels_count_counts_the_type_levels(staff):
    with sudo():
        assert HrSkillType.objects.get(
            pk=staff['regular'].pk)._compute_levels_count() == 2


def test_a_default_level_unmarks_the_other_levels(staff):
    with sudo():
        other = HrSkillLevel.objects.get(name='SRR C1')
        other.default_level = True
        other.save()
        low = HrSkillLevel.objects.get(pk=staff['low'].pk)
        low.default_level = True
        low.save()
    assert not HrSkillLevel.objects.get(name='SRR C1').default_level
    assert HrSkillLevel.objects.get(pk=staff['low'].pk).default_level


def test_the_resource_reaches_the_employee_skills(staff):
    with sudo():
        employee = _employee(staff)
        skills = employee.resource.employee_skill_ids
        assert {s.skill_id for s in skills} == {
            staff['language'].pk, staff['cloud'].pk}


def test_the_user_reaches_the_employee_skills(staff):
    user = get_user_model().objects.create_user(
        login='srr@kaupamex.mx', password='Srr12345!')
    HrEmployee.objects.filter(pk=staff['employee'].pk).update(user_id=user)
    with sudo():
        skills = get_user_model().objects.get(pk=user.pk).employee_skill_ids
        assert {s.skill_id for s in skills} == {
            staff['language'].pk, staff['cloud'].pk}


def test_the_resume_lines_read_the_employee_versions(staff):
    with sudo():
        lines = HrEmployee.get_internal_resume_lines(
            staff['employee'].pk, 'hr.employee')
    assert isinstance(lines, list)
