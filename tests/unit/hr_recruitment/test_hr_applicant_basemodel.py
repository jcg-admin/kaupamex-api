"""``hr.applicant`` sobre ``BaseModel``: ``create``/``write`` de la fuente y
la regla del entrevistador.

≙ ``odoo19c: addons/hr_recruitment/models/hr_applicant.py:617-700`` y
``security/hr_recruitment_security.xml:49-60``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
hr-applicant-basemodel.md``.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrModelData
from orm.commands import Command
from orm.environments import Environment, sudo, user_scope
from orm.models import BaseModel
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db


def _group(module, name):
    return MODELS_BY_NAME['res.groups'].objects.get(
        pk=IrModelData.objects.get(module=module, name=name).res_id)


def _user(login, *groups):
    with sudo():
        user = get_user_model().objects.create_user(
            login=login, password=None, name=login)
    for group in groups:
        user.group_ids.add(group)
    return user


def _interviewer_group():
    return _group('hr_recruitment', 'group_hr_recruitment_interviewer')


def test_the_applicant_is_a_base_model():
    assert issubclass(MODELS_BY_NAME['hr.applicant'], BaseModel)


def test_writing_interviewers_adds_and_removes_them_from_the_group():
    user = _user('iv-sync', _group('base', 'group_user'))
    with sudo():
        [applicant] = MODELS_BY_NAME['hr.applicant'].create(
            [{'partner_name': 'Ada'}])
        applicant.write({'interviewer_ids': [Command.set([user.pk])]})
        assert user in _interviewer_group().user_ids.all()
        applicant.write({'interviewer_ids': [Command.clear()]})
        assert user not in _interviewer_group().user_ids.all()


def test_creating_with_interviewers_adds_them_to_the_group():
    user = _user('iv-create', _group('base', 'group_user'))
    with sudo():
        MODELS_BY_NAME['hr.applicant'].create([{
            'partner_name': 'Grace',
            'interviewer_ids': [Command.set([user.pk])]}])
    assert user in _interviewer_group().user_ids.all()


def test_only_a_stage_or_kanban_change_stamps_the_last_stage_update():
    Stage = MODELS_BY_NAME['hr.recruitment.stage']
    with sudo():
        [applicant] = MODELS_BY_NAME['hr.applicant'].create(
            [{'partner_name': 'Edsger'}])
        before = applicant.date_last_stage_update
        applicant.write({'partner_phone': '555'})
        assert applicant.date_last_stage_update == before
        [stage] = Stage.create([{'name': 'Entrevista'}])
        applicant.write({'stage_id': stage.pk})
        assert applicant.date_last_stage_update != before


def _applicants(interviewer):
    Applicant = MODELS_BY_NAME['hr.applicant']
    Job = MODELS_BY_NAME['hr.job']
    with sudo():
        job = Job.objects.create(name='Puesto entrevistado')
        job.interviewer_ids.add(interviewer)
        other_job = Job.objects.create(name='Puesto ajeno')
        made = {
            'by_job': Applicant.create([{
                'partner_name': 'Por puesto', 'job_id': job.pk}]),
            'direct': Applicant.create([{
                'partner_name': 'Directo',
                'job_id': other_job.pk,
                'interviewer_ids': [Command.set([interviewer.pk])]}]),
            'foreign': Applicant.create([{
                'partner_name': 'Ajeno', 'job_id': other_job.pk}]),
        }
    return {key: records.id for key, records in made.items()}


def test_an_interviewer_reads_only_the_applicants_they_interview():
    user = _user('iv-rule', _group('base', 'group_user'), _interviewer_group())
    ids = _applicants(user)
    with user_scope(user.pk):
        applicants = Environment(uid=user.pk)['hr.applicant']
        seen = set(applicants.search(
            [('id', 'in', list(ids.values()))]).ids)
    assert seen == {ids['by_job'], ids['direct']}

