"""``hr.applicant`` — matching de habilidades y sincronía con el talento
(tarea #62).

Cubre ``_compute_current_applicant_skill_ids`` (regresión del bug de forma
C — ver ``test_hr_applicant_skill.py``), ``_compute_matching_skill_ids``,
``_map_applicant_skill_ids_to_talent_skill_ids`` (DIVERGENCIA 6),
``create`` (DIVERGENCIA 7) y ``write`` (DIVERGENCIA 8) — los tres símbolos
que cerraban el porte del addon.

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


class TestComputeCurrentApplicantSkillIds:
    """Regresión H-API-803: ``current_applicant_skill_ids`` estaba
    silenciosamente vacía desde ``api@a8949680`` (bug de forma C, ver
    ``test_hr_applicant_skill.py``)."""

    def test_returns_the_applicant_own_skills(self):
        skill_type = _skill_type()
        skill = _skill(skill_type)
        level = _skill_level(skill_type)
        applicant = HrApplicant.objects.create()
        a_s = HrApplicantSkill.objects.create(
            applicant_id=applicant, skill=skill, skill_type=skill_type,
            skill_level=level,
        )

        assert list(applicant.current_applicant_skill_ids) == [a_s]

    def test_empty_when_no_skills(self):
        applicant = HrApplicant.objects.create()
        assert list(applicant.current_applicant_skill_ids) == []


class TestComputeMatchingSkillIds:
    """≙ ``_compute_matching_skill_ids`` (odoo19c: :46-76)."""

    def test_no_job_returns_empty_and_zero(self):
        applicant = HrApplicant.objects.create()
        matching, missing, score = applicant._compute_matching_skill_ids()
        assert list(matching) == []
        assert list(missing) == []
        assert score == 0

    def test_full_match_scores_100(self):
        skill_type = _skill_type()
        skill = _skill(skill_type)
        level = _skill_level(skill_type, progress=80)
        job = HrJob.objects.create(name='Dev')
        HrJobSkill.objects.create(
            job=job, skill=skill, skill_type=skill_type, skill_level=level)
        applicant = HrApplicant.objects.create(job=job)
        HrApplicantSkill.objects.create(
            applicant_id=applicant, skill=skill, skill_type=skill_type,
            skill_level=level,
        )

        matching, missing, score = applicant._compute_matching_skill_ids()

        assert list(matching) == [skill]
        assert list(missing) == []
        assert score == 100

    def test_missing_skill_is_reported_with_zero_score(self):
        skill_type = _skill_type()
        needed = _skill(skill_type, name='Django')
        level = _skill_level(skill_type, progress=80)
        job = HrJob.objects.create(name='Dev')
        HrJobSkill.objects.create(
            job=job, skill=needed, skill_type=skill_type, skill_level=level)
        applicant = HrApplicant.objects.create(job=job)

        matching, missing, score = applicant._compute_matching_skill_ids()

        assert list(matching) == []
        assert list(missing) == [needed]
        assert score == 0

    def test_matching_job_argument_overrides_self_job(self):
        """DIVERGENCIA 1: el puesto llega como argumento, no por contexto."""
        skill_type = _skill_type()
        skill = _skill(skill_type)
        level = _skill_level(skill_type, progress=50)
        other_job = HrJob.objects.create(name='Other')
        HrJobSkill.objects.create(
            job=other_job, skill=skill, skill_type=skill_type, skill_level=level)
        applicant = HrApplicant.objects.create(job=None)
        HrApplicantSkill.objects.create(
            applicant_id=applicant, skill=skill, skill_type=skill_type,
            skill_level=level,
        )

        matching, _missing, score = applicant._compute_matching_skill_ids(
            matching_job=other_job)

        assert list(matching) == [skill]
        assert score == 100


class TestMapApplicantSkillIdsToTalentSkillIds:
    """≙ ``_map_applicant_skill_ids_to_talent_skill_ids`` (odoo19c:
    :94-133) — DIVERGENCIA 6."""

    def test_no_pool_applicant_is_a_no_op(self):
        applicant = HrApplicant.objects.create()
        result = applicant._map_applicant_skill_ids_to_talent_skill_ids()
        assert list(result) == []

    def test_creates_a_skill_on_the_talent(self):
        skill_type = _skill_type()
        skill = _skill(skill_type)
        level = _skill_level(skill_type)
        talent = HrApplicant.objects.create()
        applicant = HrApplicant.objects.create(pool_applicant=talent)
        HrApplicantSkill.objects.create(
            applicant_id=applicant, skill=skill, skill_type=skill_type,
            skill_level=level,
        )

        applicant._map_applicant_skill_ids_to_talent_skill_ids()

        talent_skills = set(
            talent.applicant_skill_ids.values_list('skill_id', flat=True))
        assert talent_skills == {skill.pk}

    def test_updates_the_level_on_an_existing_talent_skill(self):
        skill_type = _skill_type()
        skill = _skill(skill_type)
        low = _skill_level(skill_type, name='Bajo', progress=10)
        high = _skill_level(skill_type, name='Alto', progress=90)
        talent = HrApplicant.objects.create()
        HrApplicantSkill.objects.create(
            applicant_id=talent, skill=skill, skill_type=skill_type,
            skill_level=low,
        )
        applicant = HrApplicant.objects.create(pool_applicant=talent)
        HrApplicantSkill.objects.create(
            applicant_id=applicant, skill=skill, skill_type=skill_type,
            skill_level=high,
        )

        applicant._map_applicant_skill_ids_to_talent_skill_ids()

        talent_skill = talent.applicant_skill_ids.get()
        assert talent_skill.skill_level_id == high.pk

    def test_deletes_a_talent_skill_the_applicant_no_longer_has(self):
        skill_type = _skill_type()
        stale = _skill(skill_type, name='COBOL')
        level = _skill_level(skill_type)
        talent = HrApplicant.objects.create()
        HrApplicantSkill.objects.create(
            applicant_id=talent, skill=stale, skill_type=skill_type,
            skill_level=level,
        )
        applicant = HrApplicant.objects.create(pool_applicant=talent)

        applicant._map_applicant_skill_ids_to_talent_skill_ids()

        assert talent.applicant_skill_ids.count() == 0

    def test_does_nothing_when_self_is_its_own_pool_applicant(self):
        """Caso real del guard: ``check_talent_pool_required`` modela "es
        un talento" como ``pool_applicant_id == self.pk`` (``hr_recruitment/
        models/hr_applicant.py:218``) — un talento no se propaga a sí
        mismo."""
        talent = HrApplicant.objects.create()
        talent.pool_applicant = talent
        talent.save(update_fields=['pool_applicant'])
        skill_type = _skill_type()
        skill = _skill(skill_type)
        level = _skill_level(skill_type)
        HrApplicantSkill.objects.create(
            applicant_id=talent, skill=skill, skill_type=skill_type,
            skill_level=level,
        )

        result = talent._map_applicant_skill_ids_to_talent_skill_ids()

        assert list(result) == []


class TestCreate:
    """≙ ``create`` (odoo19c: :147-153) — DIVERGENCIA 7."""

    def test_creates_the_applicant_with_its_skills(self):
        skill_type = _skill_type()
        skill = _skill(skill_type)
        level = _skill_level(skill_type)

        [applicant] = HrApplicant.create([
            {'applicant_skill_ids': [
                {'skill': skill, 'skill_level': level, 'skill_type': skill_type},
            ]},
        ])

        assert applicant.pk is not None
        assert list(
            applicant.applicant_skill_ids.values_list('skill_id', flat=True),
        ) == [skill.pk]

    def test_merges_current_and_applicant_skill_ids(self):
        """≙ el comentario de la fuente (``:149-150``): sin la fusión, la
        duplicación de un candidato pierde sus habilidades."""
        skill_type = _skill_type()
        s1 = _skill(skill_type, name='A')
        s2 = _skill(skill_type, name='B')
        level = _skill_level(skill_type)

        [applicant] = HrApplicant.create([{
            'current_applicant_skill_ids': [
                {'skill': s1, 'skill_level': level, 'skill_type': skill_type},
            ],
            'applicant_skill_ids': [
                {'skill': s2, 'skill_level': level, 'skill_type': skill_type},
            ],
        }])

        skill_pks = set(
            applicant.applicant_skill_ids.values_list('skill_id', flat=True))
        assert skill_pks == {s1.pk, s2.pk}

    def test_scalar_fields_are_applied(self):
        [applicant] = HrApplicant.create([{'partner_name': 'Ada Lovelace'}])
        assert applicant.partner_name == 'Ada Lovelace'

    def test_creates_several_applicants_from_one_call(self):
        created = HrApplicant.create([
            {'partner_name': 'Ada'}, {'partner_name': 'Grace'},
        ])
        assert [a.partner_name for a in created] == ['Ada', 'Grace']

    def test_skill_type_defaults_when_omitted(self):
        """El ``default=`` del mixin resuelve ``skill_type`` cuando se
        omite — nunca se manda ``None`` explícito, que violaría el NOT
        NULL de la columna."""
        skill_type = _skill_type()
        skill = _skill(skill_type)
        level = _skill_level(skill_type)

        [applicant] = HrApplicant.create([
            {'applicant_skill_ids': [{'skill': skill, 'skill_level': level}]},
        ])

        created = applicant.applicant_skill_ids.get()
        assert created.skill_type_id is not None


class TestWrite:
    """≙ ``write`` (odoo19c: :155-166) — DIVERGENCIA 8."""

    def test_reconciles_skills_when_present_in_vals(self):
        skill_type = _skill_type()
        skill = _skill(skill_type)
        level = _skill_level(skill_type)
        applicant = HrApplicant.objects.create()

        applicant.write({'applicant_skill_ids': [
            {'skill': skill, 'skill_level': level, 'skill_type': skill_type},
        ]})

        assert list(
            applicant.applicant_skill_ids.values_list('skill_id', flat=True),
        ) == [skill.pk]

    def test_does_not_touch_skills_when_vals_does_not_mention_them(self):
        """Guard de la fuente (``:156``): un ``write`` sobre otras columnas
        no debe borrar las habilidades existentes."""
        skill_type = _skill_type()
        skill = _skill(skill_type)
        level = _skill_level(skill_type)
        applicant = HrApplicant.objects.create()
        HrApplicantSkill.objects.create(
            applicant_id=applicant, skill=skill, skill_type=skill_type,
            skill_level=level,
        )

        applicant.write({'partner_name': 'Grace Hopper'})

        applicant.refresh_from_db()
        assert applicant.partner_name == 'Grace Hopper'
        assert applicant.applicant_skill_ids.count() == 1

    def test_propagates_to_pool_applicant_when_skills_change(self):
        skill_type = _skill_type()
        skill = _skill(skill_type)
        level = _skill_level(skill_type)
        talent = HrApplicant.objects.create()
        applicant = HrApplicant.objects.create(pool_applicant=talent)

        applicant.write({'applicant_skill_ids': [
            {'skill': skill, 'skill_level': level, 'skill_type': skill_type},
        ]})

        assert list(
            talent.applicant_skill_ids.values_list('skill_id', flat=True),
        ) == [skill.pk]

    def test_does_not_propagate_when_skills_are_untouched(self):
        talent = HrApplicant.objects.create()
        applicant = HrApplicant.objects.create(pool_applicant=talent)

        applicant.write({'partner_name': 'Ada'})

        assert talent.applicant_skill_ids.count() == 0

    def test_returns_self(self):
        applicant = HrApplicant.objects.create()
        assert applicant.write({}) is applicant
