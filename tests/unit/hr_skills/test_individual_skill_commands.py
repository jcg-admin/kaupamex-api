"""U5 del porte de ``hr.individual.skill.mixin``: transformadores de comandos.

Referencia: odoo-tools ``abe4040ec1``,
``odoo19c: addons/hr_skills/models/hr_individual_skill_mixin.py:257-537``
y sus consumidores ``hr_job.py:55-66``, ``hr_employee.py:45-57``.

Diseño: ``designs/hr-individual-skill-commands.md``.
"""
from datetime import date, timedelta

import pytest

from addons.hr.models.hr_employee import HrEmployee
from addons.hr.models.hr_job import HrJob
from addons.hr_skills.models.hr_employee_skill import HrEmployeeSkill
from addons.hr_skills.models.hr_job_skill import HrJobSkill
from addons.hr_skills.models.hr_skill import HrSkill
from addons.hr_skills.models.hr_skill_level import HrSkillLevel
from addons.hr_skills.models.hr_skill_type import HrSkillType
from orm.environments import Environment
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.django_db

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
LAST_MONTH = TODAY - timedelta(days=30)


@pytest.fixture
def env():
    with Environment(None, SUPERUSER_ID, {}) as environment:
        yield environment


@pytest.fixture
def catalog():
    regular = HrSkillType.objects.create(name='Idiomas-u5', sequence=-20)
    certification = HrSkillType.objects.create(
        name='Certificados-u5', sequence=-10, is_certification=True)
    english = HrSkill.objects.create(name='Inglés', skill_type=regular)
    a2 = HrSkillLevel.objects.create(
        name='A2', skill_type=regular, level_progress=20)
    b1 = HrSkillLevel.objects.create(
        name='B1', skill_type=regular, level_progress=50)
    platform_skill = HrSkill.objects.create(
        name='Odoo', skill_type=certification)
    certified = HrSkillLevel.objects.create(
        name='Certificado', skill_type=certification, level_progress=100)
    job = HrJob.objects.create(name='Desarrollo-u5')
    return {'regular': regular, 'certification': certification,
            'english': english, 'a2': a2, 'b1': b1,
            'platform_skill': platform_skill,
            'certified': certified, 'job': job}


def _english(catalog, level='a2', **values):
    vals = {'job': catalog['job'].pk, 'skill_id': catalog['english'].pk,
            'skill_level_id': catalog[level].pk,
            'skill_type_id': catalog['regular'].pk}
    vals.update(values)
    return vals


def _store(env, catalog, **values):
    return env['hr.job.skill'].create([_english(catalog, **values)])


def test_expire_deletes_what_was_created_since_yesterday(env, catalog):
    record = _store(env, catalog, valid_from=TODAY)
    assert record._expire_individual_skills() == [[2, record.id]]


def test_expire_archives_an_older_active_skill(env, catalog):
    record = _store(env, catalog, valid_from=LAST_MONTH)
    assert record._expire_individual_skills() == [
        [1, record.id, {'valid_to': YESTERDAY}]]


def test_expire_deletes_an_already_expired_skill(env, catalog):
    record = _store(env, catalog, valid_from=LAST_MONTH - timedelta(days=30),
                    valid_to=LAST_MONTH)
    assert record._expire_individual_skills() == [[2, record.id]]


def test_create_archives_the_active_regular_skill(env, catalog):
    old = _store(env, catalog, valid_from=LAST_MONTH)
    new_vals = _english(catalog, level='b1')
    commands = env['hr.job.skill'].browse(())._create_individual_skills(
        [new_vals])
    assert commands == [[1, old.id, {'valid_to': YESTERDAY}],
                        [0, 0, new_vals]]


def test_create_keeps_one_of_two_identical_values(env, catalog):
    new_vals = _english(catalog, level='b1')
    commands = env['hr.job.skill'].browse(())._create_individual_skills(
        [new_vals, dict(new_vals)])
    assert commands == [[0, 0, new_vals]]


def _certification(linked, catalog, pk, **values):
    vals = {linked: pk, 'skill_id': catalog['platform_skill'].pk,
            'skill_level_id': catalog['certified'].pk,
            'skill_type_id': catalog['certification'].pk,
            'valid_from': LAST_MONTH, 'valid_to': TODAY + timedelta(days=300)}
    vals.update(values)
    return vals


def test_an_employee_omits_an_identical_certification(env, catalog):
    """``hr.employee.skill`` libera el periodo de las certificaciones
    (``_can_edit_certification_validity_period`` → ``True``): una idéntica
    ya vigente se omite (``:384-389``)."""
    employee = HrEmployee.objects.create(name='Empleada-u5')
    vals = _certification('employee', catalog, employee.pk)
    env['hr.employee.skill'].create([vals])
    assert env['hr.employee.skill'].browse(())._create_individual_skills(
        [dict(vals)]) == []


def test_a_job_treats_a_certification_as_a_regular_skill(env, catalog):
    """``hr.job.skill`` no libera el periodo (``hr_job_skill.py:23-24``): la
    certificación idéntica no se omite, la vigente se archiva como una
    habilidad regular (``:390-395``)."""
    vals = _certification('job', catalog, catalog['job'].pk)
    old = env['hr.job.skill'].create([vals])
    assert env['hr.job.skill'].browse(())._create_individual_skills(
        [dict(vals)]) == [[1, old.id, {'valid_to': YESTERDAY}],
                          [0, 0, vals]]


def test_write_of_a_core_field_archives_and_creates(env, catalog):
    record = _store(env, catalog, valid_from=LAST_MONTH)
    commands = record._write_individual_skills(
        [[1, record.id, {'skill_level_id': catalog['b1'].pk}]])
    # El registro escrito sigue vigente cuando ``_create_individual_skills``
    # busca los existentes, así que la fuente lo archiva DOS veces: una por
    # ``(self - remove_from_expire)._expire_individual_skills()`` y otra al
    # crear (``:479``). Las dos escriben el mismo ``valid_to``.
    assert commands == [
        [1, record.id, {'valid_to': YESTERDAY}],
        [1, record.id, {'valid_to': YESTERDAY}],
        [0, 0, {'job': catalog['job'].pk,
                'skill_id': catalog['english'].pk,
                'skill_level_id': catalog['b1'].pk,
                'skill_type_id': catalog['regular'].pk,
                'valid_from': TODAY, 'valid_to': False}],
    ]


def test_write_of_another_field_is_a_plain_write(env, catalog):
    record = _store(env, catalog, valid_from=LAST_MONTH)
    commands = record._write_individual_skills(
        [[1, record.id, {'valid_to': TODAY + timedelta(days=5)}]])
    assert commands == [
        [1, record.id, {'valid_to': TODAY + timedelta(days=5)}]]


def test_transformed_commands_drop_the_update_of_a_deleted_record(
        env, catalog):
    """Un id en ``1`` y en ``2``: el ``1`` se descarta (``:518-526``). La
    fuente escribe ``updated_ids.append`` sobre un ``set`` —``AttributeError``
    si se alcanza—; se porta la intención, ver el diseño."""
    keep = _store(env, catalog, valid_from=LAST_MONTH)
    gone = env['hr.job.skill'].create([{
        'job': catalog['job'].pk, 'skill_id': catalog['platform_skill'].pk,
        'skill_level_id': catalog['certified'].pk,
        'skill_type_id': catalog['certification'].pk,
        'valid_from': TODAY}])
    commands = env['hr.job.skill'].browse(())._get_transformed_commands([
        [1, gone.id, {'valid_to': TODAY}],
        [2, gone.id],
        [1, keep.id, {'valid_to': TODAY + timedelta(days=5)}],
    ], catalog['job'])
    assert commands == [
        [2, gone.id],
        [1, keep.id, {'valid_to': TODAY + timedelta(days=5)}],
    ]


def test_writing_a_job_archives_its_previous_skill(env, catalog):
    """La ruta real: ``hr.job.write`` transforma los comandos de
    ``job_skill_ids`` antes de aplicarlos (``hr_job.py:62-66``)."""
    old = _store(env, catalog, valid_from=LAST_MONTH)
    catalog['job'].write({'job_skill_ids': [
        [0, 0, {'skill_id': catalog['english'].pk,
                'skill_level_id': catalog['b1'].pk,
                'skill_type_id': catalog['regular'].pk}]]})
    rows = HrJobSkill.objects.filter(job=catalog['job']).order_by('id')
    assert [(row.pk == old.id, row.skill_level_id, row.valid_to)
            for row in rows] == [
        (True, catalog['a2'].pk, YESTERDAY),
        (False, catalog['b1'].pk, None),
    ]


def test_writing_an_employee_archives_its_previous_skill(env, catalog):
    """``hr.employee.write`` (``hr_employee.py:53-58``), con la suma de
    ``certification_ids`` que la fuente hace antes de transformar."""
    employee = HrEmployee.objects.create(name='Empleado-u5')
    vals = _english(catalog, employee=employee.pk, valid_from=LAST_MONTH)
    del vals['job']
    old = env['hr.employee.skill'].create([vals])
    employee.write({'certification_ids': [], 'employee_skill_ids': [
        [0, 0, {'skill_id': catalog['english'].pk,
                'skill_level_id': catalog['b1'].pk,
                'skill_type_id': catalog['regular'].pk}]]})
    rows = HrEmployeeSkill.objects.filter(employee=employee).order_by('id')
    assert [(row.pk == old.id, row.skill_level_id, row.valid_to)
            for row in rows] == [
        (True, catalog['a2'].pk, YESTERDAY),
        (False, catalog['b1'].pk, None),
    ]


def test_creating_an_employee_transforms_its_skill_commands(env, catalog):
    """``hr.employee.create`` (``:45-51``): un valor repetido en el lote se
    crea una vez (``:369-373``)."""
    line = {'skill_id': catalog['english'].pk,
            'skill_level_id': catalog['b1'].pk,
            'skill_type_id': catalog['regular'].pk}
    employee = env['hr.employee'].create([{
        'name': 'Nuevo-u5',
        'employee_skill_ids': [[0, 0, dict(line)], [0, 0, dict(line)]]}])
    assert HrEmployeeSkill.objects.filter(employee__in=employee).count() == 1
