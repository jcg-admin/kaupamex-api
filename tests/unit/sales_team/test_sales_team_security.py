"""``sales_team`` sobre ``BaseModel`` y con la seguridad de la referencia.

≙ ``odoo19c: addons/sales_team/models/*.py`` (``crm.tag``, ``crm.team`` y
``crm.team.member`` son ``BaseModel``) y ``odoo19c: addons/sales_team/
security/`` (``sales_team_security.xml``: un privilegio, tres grupos y dos
reglas; ``ir.model.access.csv``: nueve filas). Los dos archivos son copia
fiel y los carga el ciclo de instalación desde el manifiesto. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
security-data-by-manifest.md``.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrModelData
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope
from orm.models import BaseModel
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db

MODELS = ('crm.tag', 'crm.team', 'crm.team.member')


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
def test_every_sales_team_model_is_a_base_model(name):
    assert issubclass(MODELS_BY_NAME[name], BaseModel)


def test_the_groups_imply_one_another_as_in_the_source():
    salesman = _group('sales_team', 'group_sale_salesman')
    all_leads = _group('sales_team', 'group_sale_salesman_all_leads')
    manager = _group('sales_team', 'group_sale_manager')
    assert _group('base', 'group_user') in salesman.implied_ids.all()
    assert salesman in all_leads.implied_ids.all()
    assert all_leads in manager.implied_ids.all()


def test_the_acl_and_rules_carry_their_external_ids():
    data = IrModelData.objects.filter(module='sales_team')
    assert data.filter(model='base.IrModelAccess').count() == 9
    assert set(data.filter(model='base.IrRule').values_list(
        'name', flat=True)) == {'crm_rule_all_salesteam',
                                'sale_team_comp_rule'}


def test_an_internal_user_reads_teams_but_not_tags():
    user = _user('sales-team-internal', _group('base', 'group_user'))
    with user_scope(user.pk):
        environment = Environment(uid=user.pk)
        environment['crm.team'].check_access('read')
        with pytest.raises(AccessError):
            environment['crm.team'].check_access('write')
        with pytest.raises(AccessError):
            environment['crm.tag'].check_access('read')


def test_a_salesman_creates_tags_but_cannot_delete_them():
    user = _user('sales-team-salesman', _group('base', 'group_user'),
                 _group('sales_team', 'group_sale_salesman'))
    with user_scope(user.pk):
        tags = Environment(uid=user.pk)['crm.tag']
        tag = tags.create({'name': 'Prioritario'})
        assert tag.name == 'Prioritario'
        with pytest.raises(AccessError):
            tag.unlink()
