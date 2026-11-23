"""``crm`` sobre ``BaseModel``, con su seguridad.

≙ los seis modelos de ``odoo19c: addons/crm/models/`` que tienen puerto y los
dos archivos de ``odoo19c: addons/crm/security/``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
basemodel-adoption-crm.md``.

*Métrica:* el tipo de cada modelo, las filas cargadas con el identificador
externo del módulo, la ACL de un usuario interno y el reactivado.
*Ciega a:* los registros de los modelos sin puerto (informes, planes de
actividad, calendario y asistentes), que el manifiesto declara.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrModelData
from addons.crm.models import CrmLead
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope
from orm.models import BaseModel
from orm.registry import MODELS_BY_NAME
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.django_db

NAMES = ('crm.lead', 'crm.lead.scoring.frequency',
         'crm.lead.scoring.frequency.field', 'crm.lost.reason',
         'crm.recurring.plan', 'crm.stage')


@pytest.mark.parametrize('name', NAMES)
def test_each_model_is_a_base_model(name):
    assert issubclass(MODELS_BY_NAME[name], BaseModel)


def test_the_groups_and_rules_load():
    names = set(IrModelData.objects.filter(
        module='crm').values_list('name', flat=True))
    assert {'group_use_lead', 'group_use_recurring_revenues',
            'crm_rule_personal_lead', 'crm_lead_company_rule',
            'crm_rule_all_lead'} <= names


def test_the_acl_rows_that_resolve_load():
    """Las 32 de la fuente menos las 14 de modelos sin puerto."""
    assert IrModelData.objects.filter(
        module='crm', model='ir.model.access').count() == 18


def test_an_internal_user_without_sales_rights_cannot_read():
    group = MODELS_BY_NAME['res.groups'].objects.get(
        pk=IrModelData.objects.get(module='base', name='group_user').res_id)
    with sudo():
        user = get_user_model().objects.create_user(
            login='crm-acl-internal', password=None, name='interno')
    user.group_ids.add(group)
    with user_scope(user.pk):
        leads = Environment(uid=user.pk)['crm.lead']
        with pytest.raises(AccessError):
            leads.check_access('read')


def test_unarchiving_reaches_only_the_archived_records():
    """≙ ``action_unarchive`` (``odoo19c: addons/crm/models/
    crm_lead.py:1101-1110``): ``activated`` es ``self.filtered(not
    active)``. Sobre un recordset vacío no hay nada que reactivar; leer
    ``not self.active`` daba verdadero y guardaba una fila inexistente."""
    with Environment(None, SUPERUSER_ID, {}):
        lead = CrmLead.objects.create(name='Activa')
        lead.browse().action_unarchive()
        lead.refresh_from_db()
        assert lead.active is True


def test_a_browsed_record_saves_as_an_update():
    """Un recordset de ids reales nombra filas que existen: su ``save`` es
    un UPDATE, no un alta (``_from_ids``)."""
    with Environment(None, SUPERUSER_ID, {}):
        lead = CrmLead.objects.create(name='Leída')
        browsed = lead.browse(lead.pk)
        assert browsed._state.adding is False
        assert lead.browse()._state.adding is True
