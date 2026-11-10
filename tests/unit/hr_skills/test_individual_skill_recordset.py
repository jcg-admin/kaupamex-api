"""U1 del porte completo de ``hr.individual.skill.mixin``: consumidores
recordset.

Referencia: odoo-tools ``abe4040ec1``,
``odoo19c: addons/hr_skills/models/hr_individual_skill_mixin.py:11``
(``class HrIndividualSkillMixin(models.AbstractModel)``): sus consumidores
son recordsets con ``env``, ``search`` y ``Domain``. Decisión del árbol:
H-API-1083 (los modelos portados derivan de ``BaseModel``).

Diseño: ``designs/hr-individual-skill-mixin-full-port.md``.
"""
import pytest

import fields
from addons.hr.models.hr_job import HrJob
from addons.hr_recruitment_skills.models.hr_applicant_skill import (
    HrApplicantSkill,
)
from addons.hr_skills.models.hr_employee_skill import HrEmployeeSkill
from addons.hr_skills.models.hr_job_skill import HrJobSkill
from addons.hr_skills.models.hr_skill import HrSkill
from addons.hr_skills.models.hr_skill_level import HrSkillLevel
from addons.hr_skills.models.hr_skill_type import HrSkillType
from orm.environments import Environment
from orm.models import BaseModel
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.django_db


@pytest.fixture
def env():
    with Environment(None, SUPERUSER_ID, {}) as environment:
        yield environment


@pytest.fixture
def job_skill():
    skill_type = HrSkillType.objects.create(name='Idiomas-u1')
    skill = HrSkill.objects.create(name='Inglés', skill_type=skill_type)
    level = HrSkillLevel.objects.create(
        name='B1', skill_type=skill_type, level_progress=50)
    job = HrJob.objects.create(name='Desarrollo-u1')
    return HrJobSkill.objects.create(
        job=job, skill=skill, skill_level=level, skill_type=skill_type)


@pytest.mark.parametrize('model', [HrEmployeeSkill, HrJobSkill,
                                   HrApplicantSkill])
def test_the_consumers_are_recordsets(model):
    assert issubclass(model, BaseModel)


def test_search_orders_by_the_django_comodels(env, job_skill):
    """``_order = 'skill_type_id, skill_level_id'``: los dos comodelos son
    filas de Django y el orden se delega en su ``_order``."""
    records = env['hr.job.skill'].search(
        fields.Domain('skill_type_id', '=', job_skill.skill_type_id))
    assert list(records.ids) == [job_skill.pk]


def test_search_follows_a_path_into_a_django_comodel(env, job_skill):
    """``skill_id.name``: el dominio usa el nombre de la fuente, que aquí es
    la columna del ``Many2one`` ``skill``."""
    records = env['hr.job.skill'].search(
        [('skill_id.name', '=', 'Inglés'),
         ('skill_type_id', '=', job_skill.skill_type_id)])
    assert records.ids == [job_skill.pk]
