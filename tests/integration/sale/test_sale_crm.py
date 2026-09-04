"""Tests — addons ``crm`` + ``sale_crm`` (oportunidad ↔ orden)."""
from decimal import Decimal

import pytest

from addons.crm.models import CrmLead, CrmStage
from addons.sale.models import SaleOrder
from addons.sale_crm.models import SaleOrderOpportunity
from addons.sales_team.models import CrmTeam

pytestmark = pytest.mark.integration


def test_crm_stage_ordering(db):
    b = CrmStage.objects.create(name='Propuesta', sequence=2)
    a = CrmStage.objects.create(name='Nuevo', sequence=1)
    assert list(CrmStage.objects.all()) == [a, b]


def test_crm_lead_defaults(db):
    lead = CrmLead.objects.create(name='Oportunidad X')
    assert lead.type == CrmLead.TYPE_LEAD
    assert lead.priority == '0'
    assert lead.active is True
    assert lead.expected_revenue == Decimal('0.00')


def test_crm_lead_with_stage_and_team(db):
    stage = CrmStage.objects.create(name='Ganada', sequence=5, is_won=True)
    team = CrmTeam.objects.create(name='Ventas')
    lead = CrmLead.objects.create(
        name='Oportunidad Y', type=CrmLead.TYPE_OPPORTUNITY, stage_id=stage, team_id=team,
        expected_revenue=Decimal('5000.00'), probability=Decimal('40.00'),
    )
    assert lead.stage_id.is_won is True
    assert lead.team_id.name == 'Ventas'
    assert lead in stage.leads.all()


def test_sale_order_opportunity_link_and_count(db):
    lead = CrmLead.objects.create(name='Op con órdenes', type=CrmLead.TYPE_OPPORTUNITY)
    o1 = SaleOrder.objects.create()
    o2 = SaleOrder.objects.create()
    SaleOrderOpportunity.objects.create(order=o1, opportunity=lead)
    SaleOrderOpportunity.objects.create(order=o2, opportunity=lead)
    assert SaleOrderOpportunity.order_count_for(lead) == 2
    assert o1.opportunity_link.opportunity == lead


def test_sale_order_opportunity_nullable(db):
    o = SaleOrder.objects.create()
    link = SaleOrderOpportunity.objects.create(order=o, opportunity=None)
    assert link.opportunity is None
    assert 'sin oportunidad' in str(link)
