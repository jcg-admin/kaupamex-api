"""U2–U4 del porte completo de ``hr.individual.skill.mixin``.

Referencia: odoo-tools ``abe4040ec1``,
``odoo19c: addons/hr_skills/models/hr_individual_skill_mixin.py``:

- ``_default_skill_type_id`` (``:42-45``): la clave de contexto
  ``certificate_skill`` elige el primer tipo de certificación;
- los ``related`` y el ``compute`` sin almacenar (``:54-62``);
- ``_check_not_overlapping_regular_skill`` (``:64-110``) valida el lote
  con ``_get_overlapping_individual_skill`` (``:111-195``);
- ``_check_date``, ``_check_skill_type``, ``_check_skill_level``
  (``:196-219``) son ``@api.constrains``;
- ``_compute_display_name`` (``:249-253``).

Diseño: ``designs/hr-individual-skill-mixin-full-port.md``.
"""
from datetime import date

import pytest

from addons.hr.models.hr_job import HrJob
from addons.hr_skills.models.hr_job_skill import HrJobSkill
from addons.hr_skills.models.hr_skill import HrSkill
from addons.hr_skills.models.hr_skill_level import HrSkillLevel
from addons.hr_skills.models.hr_skill_type import HrSkillType
from exceptions import ValidationError
from orm.environments import Environment
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.django_db


@pytest.fixture
def env():
    with Environment(None, SUPERUSER_ID, {}) as environment:
        yield environment


@pytest.fixture
def catalog():
    regular = HrSkillType.objects.create(
        name='Idiomas-u2', sequence=-20, color=4)
    certification = HrSkillType.objects.create(
        name='Certificados-u2', sequence=-10, is_certification=True)
    skill = HrSkill.objects.create(name='Inglés', skill_type=regular)
    level = HrSkillLevel.objects.create(
        name='B1', skill_type=regular, level_progress=50)
    HrSkillLevel.objects.create(
        name='C1', skill_type=regular, level_progress=80)
    job = HrJob.objects.create(name='Desarrollo-u2')
    return {'regular': regular, 'certification': certification,
            'skill': skill, 'level': level, 'job': job}


def _vals(catalog, **overrides):
    vals = {'job': catalog['job'].pk, 'skill': catalog['skill'].pk,
            'skill_level': catalog['level'].pk,
            'skill_type': catalog['regular'].pk,
            'valid_from': date(2026, 1, 1)}
    vals.update(overrides)
    return vals


def test_default_skill_type_follows_the_certificate_context(env, catalog):
    model = env['hr.job.skill'].browse([])
    assert model._default_skill_type_id() == catalog['regular']
    assert (model.with_context(certificate_skill=True)
            ._default_skill_type_id() == catalog['certification'])


def test_the_field_default_reads_the_context(env, catalog):
    model = env['hr.job.skill'].browse([])
    assert model.default_get(['skill_type']) == {
        'skill_type': catalog['regular'].pk}
    assert model.with_context(certificate_skill=True).default_get(
        ['skill_type']) == {'skill_type': catalog['certification'].pk}


def test_related_and_computed_fields_are_fields(env, catalog):
    record = env['hr.job.skill'].create([_vals(catalog)])
    assert record.level_progress == 50
    assert record.color == 4
    assert record.levels_count == catalog['regular'].levels_count
    assert record.is_certification is False
    assert record.certification_skill_type_count == (
        HrSkillType.objects.filter(is_certification=True).count())
    declared = {name: field.type for name, field in record._fields.items()}
    assert declared['level_progress'] == 'integer'
    assert declared['is_certification'] == 'boolean'


def test_display_name_is_skill_colon_level(env, catalog):
    record = env['hr.job.skill'].create([_vals(catalog)])
    assert record.display_name == 'Inglés: B1'


def test_a_batch_with_two_overlapping_skills_is_rejected(
        env, catalog, assert_raises):
    """``create`` no abre savepoint en la fuente: lo hace quien lo envuelve,
    y en sus pruebas es ``BaseCase._assertRaises``
    (``odoo19c: odoo/tests/common.py:502-524``), aquí ``assert_raises``."""
    with assert_raises(ValidationError) as info:
        env['hr.job.skill'].create([
            _vals(catalog),
            _vals(catalog, valid_from=date(2026, 3, 1)),
        ])
    assert 'overlap' in str(info.value)
    assert not HrJobSkill.objects.filter(job=catalog['job']).exists()


def test_a_new_skill_overlapping_a_stored_one_is_rejected(
        env, catalog, assert_raises):
    env['hr.job.skill'].create([_vals(catalog, valid_to=date(2026, 6, 30))])
    with assert_raises(ValidationError) as info:
        env['hr.job.skill'].create([
            _vals(catalog, valid_from=date(2026, 6, 1))])
    assert 'overlap' in str(info.value)
    env['hr.job.skill'].create([_vals(catalog, valid_from=date(2026, 7, 1))])


def test_identical_certifications_are_rejected(env, catalog, assert_raises):
    cert_skill = HrSkill.objects.create(
        name='Odoo', skill_type=catalog['certification'])
    cert_level = HrSkillLevel.objects.create(
        name='Certificado', skill_type=catalog['certification'],
        level_progress=100)
    vals = _vals(catalog, skill=cert_skill.pk, skill_level=cert_level.pk,
                 skill_type=catalog['certification'].pk,
                 valid_to=date(2026, 12, 31))
    env['hr.job.skill'].create([vals])
    with assert_raises(ValidationError) as info:
        env['hr.job.skill'].create([vals])
    assert 'overlap' in str(info.value)
    env['hr.job.skill'].create([dict(vals, valid_from=date(2027, 1, 1),
                                     valid_to=date(2027, 12, 31))])


def test_the_date_and_type_checks_are_constraints(env, catalog, assert_raises):
    """Las restricciones corren en el orden de ``getmembers``, alfabético:
    ``_check_skill_level`` antes que ``_check_skill_type``."""
    cert_level = HrSkillLevel.objects.create(
        name='Certificado', skill_type=catalog['certification'],
        level_progress=100)
    with assert_raises(ValidationError) as info:
        env['hr.job.skill'].create([
            _vals(catalog, valid_to=date(2025, 1, 1))])
    assert 'prior to' in str(info.value)
    with assert_raises(ValidationError) as info:
        env['hr.job.skill'].create([
            _vals(catalog, skill_type=catalog['certification'].pk)])
    assert 'is not valid' in str(info.value)
    with assert_raises(ValidationError) as info:
        env['hr.job.skill'].create([
            _vals(catalog, skill_type=catalog['certification'].pk,
                  skill_level=cert_level.pk)])
    assert "don't match" in str(info.value)


def test_write_runs_the_stored_field_constraints(env, catalog):
    record = env['hr.job.skill'].create([_vals(catalog)])
    with pytest.raises(ValidationError, match='prior to'):
        record.write({'valid_to': date(2025, 1, 1)})


def test_the_constraint_matches_the_source_name_of_a_many2one(env, catalog):
    """``@api.constrains('skill_id', …)`` corre cuando los ``vals`` traen el
    nombre de Django ``skill``: los dos nombran el mismo campo."""
    record = env['hr.job.skill'].create([_vals(catalog)])
    other_type = HrSkillType.objects.create(name='Otro-u3')
    other = HrSkill.objects.create(name='Francés', skill_type=other_type)
    with pytest.raises(ValidationError, match="don't match"):
        record.write({'skill': other.pk})


def test_skill_and_level_are_computed_from_the_type(env, catalog):
    """``skill_id`` y ``skill_level_id`` son ``compute`` almacenados y
    editables (``:47-50``, ``:232-248``): en un registro de ``new()`` —el del
    formulario— salen del tipo.

    Corrección de la expectativa anterior, que creaba la fila sin los dos
    campos: en la fuente son ``required`` (NOT NULL, ``odoo/orm/fields.py:
    298``) y no ``precompute`` (``:287``), así que ``create`` sin ellos viola
    el NOT NULL también allá. Ver ``FLOW.md`` §6.
    """
    HrSkillLevel.objects.filter(pk=catalog['level'].pk).update(
        default_level=True)
    record = env['hr.job.skill'].new({'skill_type': catalog['regular'].pk})
    assert record.skill == catalog['skill']
    assert record.skill_level == catalog['level']


def test_changing_the_type_recomputes_the_skill(env, catalog):
    """La lectura previa deja el objeto relacionado en la copia por instancia
    de Django (``_state.fields_cache``); tras el recómputo la lectura tiene
    que responder la caché del ORM, que es la única copia en la fuente."""
    record = env['hr.job.skill'].create([_vals(catalog)])
    assert record.skill == catalog['skill']
    assert record.skill_level == catalog['level']
    other_type = HrSkillType.objects.create(name='Otro-u4b', sequence=-30)
    other_skill = HrSkill.objects.create(name='Python', skill_type=other_type)
    other_level = HrSkillLevel.objects.create(
        name='Senior', skill_type=other_type, level_progress=90)
    record.write({'skill_type': other_type.pk})
    assert record.skill == other_skill
    assert record.skill_level == other_level
