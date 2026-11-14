"""``hr.job`` sobre ``BaseModel``, con la escritura de ``hr_recruitment``.

≙ ``odoo19c: addons/hr/models/hr_job.py:80-92`` y
``addons/hr_recruitment/models/hr_job.py:287-336``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
hr-job-basemodel.md``.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrModelData
from orm.commands import Command
from orm.environments import sudo
from orm.models import BaseModel
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _as_superuser():
    """Los datos de prueba de la referencia se escriben como superusuario."""
    with sudo():
        yield


def _interviewer_group():
    return MODELS_BY_NAME['res.groups'].objects.get(pk=IrModelData.objects.get(
        module='hr_recruitment',
        name='group_hr_recruitment_interviewer').res_id)


def _user(login):
    return get_user_model().objects.create_user(
        login=login, password=None, name=login)


def _job(name='Puesto'):
    [job] = MODELS_BY_NAME['hr.job'].create([{'name': name}])
    return job


def test_the_job_is_a_base_model():
    assert issubclass(MODELS_BY_NAME['hr.job'], BaseModel)


def test_writing_interviewers_adds_and_removes_them_from_the_group():
    user = _user('job-iv')
    job = _job()
    job.write({'interviewer_ids': [Command.set([user.pk])]})
    assert user in _interviewer_group().user_ids.all()
    job.write({'interviewer_ids': [Command.clear()]})
    assert user not in _interviewer_group().user_ids.all()


def test_archiving_the_job_archives_its_applications():
    job = _job()
    [applicant] = MODELS_BY_NAME['hr.applicant'].create(
        [{'partner_name': 'Ada', 'job_id': job.id}])
    job.write({'active': False})
    applicant.invalidate_recordset()
    assert applicant.active is False


def test_a_new_recruiter_takes_the_ongoing_applications_of_the_old_one():
    old, new, other = _user('rec-old'), _user('rec-new'), _user('rec-other')
    [job] = MODELS_BY_NAME['hr.job'].create(
        [{'name': 'Con reclutador', 'user_id': old.pk}])
    Applicant = MODELS_BY_NAME['hr.applicant']
    [mine] = Applicant.create(
        [{'partner_name': 'Del anterior', 'job_id': job.id,
          'user_id': old.pk}])
    [theirs] = Applicant.create(
        [{'partner_name': 'De otro', 'job_id': job.id,
          'user_id': other.pk}])
    job.write({'user_id': new.pk})
    (mine | theirs).invalidate_recordset()
    assert mine.user_id == new.pk
    assert theirs.user_id == other.pk
