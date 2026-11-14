"""Comodelos de ``hr_recruitment`` sobre ``BaseModel`` y su seguridad.

≙ ``odoo19c: addons/hr_recruitment/models/*.py`` (los comodelos de
``hr.applicant`` son ``BaseModel``) y ``odoo19c: addons/hr_recruitment/
security/``. Los dos archivos son copia fiel, salvo las omisiones medidas que
declaran su cabecera y el manifiesto, y los carga el ciclo de instalación.
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
basemodel-adoption-hr-recruitment.md``.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrModelAccess, IrModelData
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope
from orm.models import BaseModel
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db

MODELS = ('hr.applicant.category', 'hr.applicant.refuse.reason',
          'hr.job.platform', 'hr.recruitment.degree',
          'hr.recruitment.source', 'hr.recruitment.stage', 'hr.talent.pool')


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


@pytest.mark.parametrize('name', MODELS)
def test_every_comodel_is_a_base_model(name):
    assert issubclass(MODELS_BY_NAME[name], BaseModel)


def test_the_groups_imply_one_another_as_in_the_source():
    interviewer = _group('hr_recruitment', 'group_hr_recruitment_interviewer')
    officer = _group('hr_recruitment', 'group_hr_recruitment_user')
    manager = _group('hr_recruitment', 'group_hr_recruitment_manager')
    assert _group('base', 'group_user') in interviewer.implied_ids.all()
    assert interviewer in officer.implied_ids.all()
    assert officer in manager.implied_ids.all()


def test_the_acl_and_rules_carry_their_external_ids():
    data = IrModelData.objects.filter(module='hr_recruitment')
    # 19 filas en el CSV: 18 propias y ``hr.access_hr_job_user``, que
    # sobrescribe la fila homónima de ``hr``
    assert data.filter(model='base.IrModelAccess').count() == 18
    assert set(data.filter(model='base.IrRule').values_list(
        'name', flat=True)) == {'hr_applicant_comp_rule',
                                'hr_applicant_user_rule',
                                'hr_job_user_rule',
                                'hr_talent_pool_user_rule'}


def test_an_interviewer_reads_stages_but_does_not_write_them():
    user = _user('recruitment-interviewer', _group('base', 'group_user'),
                 _group('hr_recruitment', 'group_hr_recruitment_interviewer'))
    with user_scope(user.pk):
        stages = Environment(uid=user.pk)['hr.recruitment.stage']
        stages.check_access('read')
        with pytest.raises(AccessError):
            stages.check_access('write')


def test_a_recruitment_manager_creates_stages():
    user = _user('recruitment-manager', _group('base', 'group_user'),
                 _group('hr_recruitment', 'group_hr_recruitment_manager'))
    with user_scope(user.pk):
        stages = Environment(uid=user.pk)['hr.recruitment.stage']
        stage = stages.create({'name': 'Entrevista técnica'})
        assert stage.name == 'Entrevista técnica'


def test_the_hr_job_row_of_hr_is_overridden_to_read_only():
    """``hr.access_hr_job_user`` en el CSV de ``hr_recruitment`` actualiza la
    fila que define ``hr``: el oficial de RR. HH. pasa a sólo leer puestos."""
    row = IrModelAccess.objects.get(pk=IrModelData.objects.get(
        module='hr', name='access_hr_job_user').res_id)
    perms = (row.perm_read, row.perm_write, row.perm_create, row.perm_unlink)
    assert perms == (True, False, False, False)
