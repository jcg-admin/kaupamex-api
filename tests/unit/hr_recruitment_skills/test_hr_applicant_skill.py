"""``hr.applicant.skill`` — ``_get_current_skills_by_applicant`` (tarea #62).

Regresión del bug de forma C (``api@a8949680``): ``applicant_id`` es el
SÍMBOLO del campo (sufijo ``_id`` incluido), así que Django deriva su
attname como ``applicant_id_id`` — ``applicant_skill.applicant_id`` da el
OBJETO relacionado, no la pk. El código bajo prueba agrupaba por el
objeto y el llamador indexaba por pk entera: la clave nunca calzaba y el
``defaultdict(list)`` devolvía siempre ``[]``. Ver el docstring de
``hr_applicant_skill.py``, sección "Corrección H-API-803".

Toca DB → django_db.
"""
import datetime

import pytest

from addons.hr_recruitment.models.hr_applicant import HrApplicant
from addons.hr_recruitment_skills.models.hr_applicant_skill import HrApplicantSkill
from addons.hr_skills.models.hr_skill import HrSkill
from addons.hr_skills.models.hr_skill_level import HrSkillLevel
from addons.hr_skills.models.hr_skill_type import HrSkillType

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def _skill_type(name='General', is_certification=False):
    return HrSkillType.objects.create(name=name, is_certification=is_certification)


def _skill(skill_type, name='Python'):
    return HrSkill.objects.create(name=name, skill_type=skill_type)


def _skill_level(skill_type, name='Nivel', progress=50):
    return HrSkillLevel.objects.create(
        skill_type=skill_type, name=name, level_progress=progress)


class TestGetCurrentSkillsByApplicant:
    """≙ ``_get_current_skills_by_applicant`` (odoo19c: :24-36)."""

    def test_groups_by_applicant_pk_not_by_the_related_object(self):
        """Discriminante de forma C: agrupar por el OBJETO ``applicant_id``
        (en vez de por ``applicant_id_id``, la pk) hace que indexar el
        resultado con la pk entera —como hace el llamador real,
        ``hr_applicant.py::_compute_current_applicant_skill_ids``— devuelva
        ``[]`` por el ``defaultdict``, no las filas reales."""
        skill_type = _skill_type()
        skill = _skill(skill_type)
        level = _skill_level(skill_type)
        applicant = HrApplicant.objects.create()
        applicant_skill = HrApplicantSkill.objects.create(
            applicant_id=applicant, skill=skill, skill_type=skill_type,
            skill_level=level,
        )

        result = HrApplicantSkill._get_current_skills_by_applicant(
            HrApplicantSkill.objects.all())

        assert result[applicant.pk] == [applicant_skill]

    def test_two_applicants_do_not_bleed_into_each_other(self):
        skill_type = _skill_type()
        skill = _skill(skill_type)
        level = _skill_level(skill_type)
        a1 = HrApplicant.objects.create()
        a2 = HrApplicant.objects.create()
        s1 = HrApplicantSkill.objects.create(
            applicant_id=a1, skill=skill, skill_type=skill_type, skill_level=level)
        s2 = HrApplicantSkill.objects.create(
            applicant_id=a2, skill=skill, skill_type=skill_type, skill_level=level)

        result = HrApplicantSkill._get_current_skills_by_applicant(
            HrApplicantSkill.objects.all())

        assert result[a1.pk] == [s1]
        assert result[a2.pk] == [s2]

    def test_expired_non_certification_is_dropped(self):
        skill_type = _skill_type()
        skill = _skill(skill_type)
        level = _skill_level(skill_type)
        applicant = HrApplicant.objects.create()
        HrApplicantSkill.objects.create(
            applicant_id=applicant, skill=skill, skill_type=skill_type,
            skill_level=level, valid_to=datetime.date(2000, 1, 1),
        )

        result = HrApplicantSkill._get_current_skills_by_applicant(
            HrApplicantSkill.objects.all())

        assert result[applicant.pk] == []

    def test_expired_certification_keeps_the_most_recent(self):
        skill_type = _skill_type(is_certification=True)
        skill = _skill(skill_type)
        level = _skill_level(skill_type)
        applicant = HrApplicant.objects.create()
        older = HrApplicantSkill.objects.create(
            applicant_id=applicant, skill=skill, skill_type=skill_type,
            skill_level=level, valid_to=datetime.date(2000, 1, 1),
        )
        newer = HrApplicantSkill.objects.create(
            applicant_id=applicant, skill=skill, skill_type=skill_type,
            skill_level=level, valid_to=datetime.date(2001, 1, 1),
        )

        result = HrApplicantSkill._get_current_skills_by_applicant(
            HrApplicantSkill.objects.all())

        assert result[applicant.pk] == [newer]
        assert older not in result[applicant.pk]

    def test_valid_certification_is_kept_over_an_expired_one(self):
        skill_type = _skill_type(is_certification=True)
        skill = _skill(skill_type)
        level = _skill_level(skill_type)
        applicant = HrApplicant.objects.create()
        HrApplicantSkill.objects.create(
            applicant_id=applicant, skill=skill, skill_type=skill_type,
            skill_level=level, valid_to=datetime.date(2000, 1, 1),
        )
        current = HrApplicantSkill.objects.create(
            applicant_id=applicant, skill=skill, skill_type=skill_type,
            skill_level=level, valid_to=None,
        )

        result = HrApplicantSkill._get_current_skills_by_applicant(
            HrApplicantSkill.objects.all())

        assert result[applicant.pk] == [current]
