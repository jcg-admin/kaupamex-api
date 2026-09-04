"""``hr.job`` — puntuación de matching y candidatos que coinciden (tarea
#62).

Cubre ``_compute_applicant_matching_score`` (regresión: dependía de
``_compute_current_applicant_skill_ids``, silenciosamente vacía antes del
fix de forma C — ver ``test_hr_applicant_skill.py``) y
``_search_matching_applicants`` — la porción de datos que
``action_search_matching_applicants`` (DIVERGENCIA 4,
``scripts/divergencias_declaradas.txt``) exponía envuelta en una acción de
cliente sin mecanismo en este backend.

Toca DB → django_db.
"""
import pytest

from addons.hr.models.hr_job import HrJob
from addons.hr_recruitment.models.hr_applicant import HrApplicant
from addons.hr_recruitment_skills.models.hr_applicant_skill import HrApplicantSkill
from addons.hr_skills.models.hr_job_skill import HrJobSkill
from addons.hr_skills.models.hr_skill import HrSkill
from addons.hr_skills.models.hr_skill_level import HrSkillLevel
from addons.hr_skills.models.hr_skill_type import HrSkillType

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def _skill_type(name='General'):
    return HrSkillType.objects.create(name=name)


def _skill(skill_type, name='Python'):
    return HrSkill.objects.create(name=name, skill_type=skill_type)


def _skill_level(skill_type, name='Nivel', progress=50):
    return HrSkillLevel.objects.create(
        skill_type=skill_type, name=name, level_progress=progress)


class TestComputeApplicantMatchingScore:
    """≙ ``_compute_applicant_matching_score`` (odoo19c: :15-44)."""

    def test_full_match_scores_100(self):
        skill_type = _skill_type()
        skill = _skill(skill_type)
        level = _skill_level(skill_type, progress=70)
        job = HrJob.objects.create(name='Dev')
        HrJobSkill.objects.create(
            job=job, skill=skill, skill_type=skill_type, skill_level=level)
        applicant = HrApplicant.objects.create()
        HrApplicantSkill.objects.create(
            applicant_id=applicant, skill=skill, skill_type=skill_type,
            skill_level=level,
        )

        score = job._compute_applicant_matching_score(applicant)

        assert score == 100

    def test_zero_when_job_has_no_skills(self):
        job = HrJob.objects.create(name='Dev')
        applicant = HrApplicant.objects.create()
        assert job._compute_applicant_matching_score(applicant) == 0

    def test_zero_when_applicant_has_no_matching_skills(self):
        skill_type = _skill_type()
        needed = _skill(skill_type, name='Django')
        level = _skill_level(skill_type, progress=70)
        job = HrJob.objects.create(name='Dev')
        HrJobSkill.objects.create(
            job=job, skill=needed, skill_type=skill_type, skill_level=level)
        applicant = HrApplicant.objects.create()

        assert job._compute_applicant_matching_score(applicant) == 0


class TestSearchMatchingApplicants:
    """La porción de datos de ``action_search_matching_applicants``
    (DIVERGENCIA 4) — el envoltorio de acción de cliente no tiene
    mecanismo en este backend; esto es lo que quedó."""

    def test_empty_when_job_has_no_skills(self):
        job = HrJob.objects.create(name='Dev')
        assert list(job._search_matching_applicants()) == []

    def test_finds_applicants_sharing_a_skill(self):
        skill_type = _skill_type()
        skill = _skill(skill_type)
        level = _skill_level(skill_type)
        job = HrJob.objects.create(name='Dev')
        HrJobSkill.objects.create(
            job=job, skill=skill, skill_type=skill_type, skill_level=level)
        other_job = HrJob.objects.create(name='Other')
        candidate = HrApplicant.objects.create(job=other_job)
        HrApplicantSkill.objects.create(
            applicant_id=candidate, skill=skill, skill_type=skill_type,
            skill_level=level,
        )
        candidate._compute_skill_ids()

        matches = job._search_matching_applicants()

        assert list(matches) == [candidate]

    def test_excludes_applicants_already_in_this_job(self):
        skill_type = _skill_type()
        skill = _skill(skill_type)
        level = _skill_level(skill_type)
        job = HrJob.objects.create(name='Dev')
        HrJobSkill.objects.create(
            job=job, skill=skill, skill_type=skill_type, skill_level=level)
        already_here = HrApplicant.objects.create(job=job)
        HrApplicantSkill.objects.create(
            applicant_id=already_here, skill=skill, skill_type=skill_type,
            skill_level=level,
        )
        already_here._compute_skill_ids()

        assert list(job._search_matching_applicants()) == []

    def test_excludes_applicants_without_a_shared_skill(self):
        skill_type = _skill_type()
        needed = _skill(skill_type, name='Django')
        other = _skill(skill_type, name='COBOL')
        level = _skill_level(skill_type)
        job = HrJob.objects.create(name='Dev')
        HrJobSkill.objects.create(
            job=job, skill=needed, skill_type=skill_type, skill_level=level)
        unrelated = HrApplicant.objects.create()
        HrApplicantSkill.objects.create(
            applicant_id=unrelated, skill=other, skill_type=skill_type,
            skill_level=level,
        )
        unrelated._compute_skill_ids()

        assert list(job._search_matching_applicants()) == []
