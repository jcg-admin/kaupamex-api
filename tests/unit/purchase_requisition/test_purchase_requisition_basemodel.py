"""``purchase_requisition`` sobre ``BaseModel``, con la seguridad de la
referencia.

≙ ``odoo19c: addons/purchase_requisition/models/purchase_requisition.py``
(``purchase.requisition`` con ``_inherit = ['mail.thread',
'mail.activity.mixin']`` y ``purchase.requisition.line``),
``odoo19c: addons/purchase_requisition/models/purchase.py``
(``purchase.order.group``) y los dos archivos de
``odoo19c: addons/purchase_requisition/security/``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
basemodel-adoption-purchase-requisition.md``.

*Métrica:* el tipo de cada modelo, las filas cargadas con el identificador
externo del módulo, y la conducta de ``action_cancel``/``action_done`` sobre
órdenes reales.
*Ciega a:* las vistas e informes del manifiesto de la fuente, que este árbol
no carga.
"""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrModelAccess, IrModelData, IrRule, ResCompany
from addons.mail.models import MailThread
from addons.purchase.models import PurchaseOrder
from addons.purchase_requisition.models import PurchaseRequisition
from exceptions import AccessError, UserError
from orm.environments import Environment, sudo, user_scope
from orm.models import BaseModel
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db

MODELS = {
    'purchase.requisition': 'Purchase Requisition',
    'purchase.requisition.line': 'Purchase Requisition Line',
    'purchase.order.group': 'Technical model to group PO for call to tenders',
}


@pytest.fixture
def company(db):
    with sudo():
        return ResCompany.objects.create(code='pr-adopt', name='PR adopt')


@pytest.fixture
def requisition(company):
    with sudo():
        return PurchaseRequisition.objects.create(company=company)


def _order(requisition, state):
    with sudo():
        order = PurchaseOrder.objects.create(
            company_id=requisition.company, requisition=requisition)
        order.state = state
        order.save()
    return order


@pytest.mark.parametrize('name', sorted(MODELS))
def test_each_model_is_a_base_model_with_its_description(name):
    model = MODELS_BY_NAME[name]
    assert issubclass(model, BaseModel)
    assert model.__dict__['_description'] == MODELS[name]


def test_the_agreement_is_a_mail_thread():
    """D-1 cerrada: el ``_inherit`` de la fuente es herencia real."""
    assert issubclass(PurchaseRequisition, MailThread)


def test_the_acl_is_the_reference_csv():
    """Sin las dos filas de los asistentes abstractos (manifiesto)."""
    xmlids = set(IrModelData.objects.filter(
        module='purchase_requisition', model='base.IrModelAccess',
    ).values_list('name', flat=True))
    assert xmlids == {
        'access_purchase_requisition',
        'access_purchase_requisition_line_purchase_user',
        'access_purchase_requisition_manager',
        'access_purchase_requisition_line_manager',
        'access_purchase_requisition_purchase_order_group',
    }
    manager = IrModelAccess.objects.get(pk=IrModelData.objects.get(
        module='purchase_requisition',
        name='access_purchase_requisition_manager').res_id)
    perms = (manager.perm_read, manager.perm_write, manager.perm_create,
             manager.perm_unlink)
    assert perms == (True, False, False, False)


def test_the_security_xml_loads_its_rules_and_group():
    names = set(IrModelData.objects.filter(
        module='purchase_requisition').values_list('name', flat=True))
    assert {'purchase_requisition_comp_rule',
            'purchase_requisition_line_comp_rule',
            'group_purchase_alternatives'} <= names
    rule = IrRule.objects.get(pk=IrModelData.objects.get(
        module='purchase_requisition',
        name='purchase_requisition_comp_rule').res_id)
    assert rule.domain_force == "[('company_id', 'in', company_ids)]"


def test_an_internal_user_without_purchase_rights_cannot_read():
    group = MODELS_BY_NAME['res.groups'].objects.get(
        pk=IrModelData.objects.get(module='base', name='group_user').res_id)
    with sudo():
        user = get_user_model().objects.create_user(
            login='requisition-acl-internal', password=None, name='interno')
    user.group_ids.add(group)
    with user_scope(user.pk):
        agreements = Environment(uid=user.pk)['purchase.requisition']
        with pytest.raises(AccessError):
            agreements.check_access('read')


def test_order_count_counts_the_orders(requisition):
    _order(requisition, 'draft')
    _order(requisition, 'sent')
    with sudo():
        assert requisition.order_count == 2


def test_done_is_refused_with_an_order_to_approve(requisition):
    """≙ ``action_done`` (``:146-156``): ``to approve`` también bloquea."""
    _order(requisition, 'to approve')
    with sudo(), pytest.raises(UserError):
        requisition.action_done()


def test_cancel_posts_a_note_on_each_cancelled_order(requisition):
    """≙ ``action_cancel`` (``:118-127``): nota en cada orden cancelada."""
    order = _order(requisition, 'draft')
    with sudo():
        before = order.message_ids.count()
        requisition.action_cancel()
        order.refresh_from_db()
        assert order.state == 'cancel'
        assert order.message_ids.count() == before + 1
        assert requisition.state == 'cancel'
