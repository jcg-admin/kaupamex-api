"""Tests — clúster ``sale.order`` (addons sale / sales_team / sale_stock / sale_loyalty).

Cobertura TDD de los modelos Odoo-fieles del grafo de venta:

- ``sale``          — SaleOrder / SaleOrderLine: desglose por línea + amounts de
                      orden + máquina de estados (action_confirm/cancel/draft/lock).
- ``sales_team``    — CrmTeam / CrmTeamMember / CrmTag + sale.order.team_id.
- ``sale_stock``    — SaleOrderDelivery / SaleOrderLineDelivery: delivery_status +
                      qty_to_deliver (extensión Odoo _inherit como modelo relacionado).
- ``sale_loyalty``  — SaleOrderCoupon: descuento del voucher sobre la orden.
"""
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from addons.sale.models import SaleOrder, SaleOrderLine
from addons.sale_loyalty.models import SaleOrderCoupon
from addons.sale_stock.models import SaleOrderDelivery, SaleOrderLineDelivery
from addons.sales_team.models import CrmTag, CrmTeam, CrmTeamMember
from addons.loyalty.models import Voucher
from tests.factories.product_factory import make_category, make_product

pytestmark = pytest.mark.integration


@pytest.fixture
def cat(db):
    return make_category(name='Cat Sale')


@pytest.fixture
def producto(db, cat):
    return make_product(name='Prod Sale', price=Decimal('100.00'), stock=10, categ=cat)


# ---------------------------------------------------------------- sale (base)

def test_line_amount_breakdown_iva_incluido(producto):
    """price_total/tax/subtotal por línea (Odoo _compute_amount)."""
    so = SaleOrder.objects.create()
    line = SaleOrderLine.objects.create(
        order=so, product=producto, product_uom_qty=2, price_unit=Decimal('100.00'),
    )
    assert line.price_total() == Decimal('200.00')
    # IVA MX 16% incluido: tax = total*rate/(1+rate) = 200*0.16/1.16 = 27.59
    assert line.price_tax() == Decimal('27.59')
    assert line.price_subtotal() == Decimal('172.41')


def test_line_discount_percentage(producto):
    """discount % de la línea (Odoo sale.order.line.discount)."""
    so = SaleOrder.objects.create()
    line = SaleOrderLine.objects.create(
        order=so, product=producto, product_uom_qty=1, price_unit=Decimal('100.00'),
        discount=Decimal('10.00'),
    )
    assert line.price_total() == Decimal('90.00')


def test_order_amounts_sum_lines(producto):
    """amount_untaxed/tax/total = suma del desglose por línea (Odoo _compute_amounts)."""
    so = SaleOrder.objects.create()
    SaleOrderLine.objects.create(order=so, product=producto, product_uom_qty=2, price_unit=Decimal('100.00'))
    assert so.amount_total == Decimal('200.00')
    assert so.amount_untaxed == Decimal('172.41')
    assert so.amount_tax == Decimal('27.59')


def test_state_machine_confirm(producto):
    """action_confirm: draft → sale, asigna name + date_order."""
    so = SaleOrder.objects.create()
    SaleOrderLine.objects.create(order=so, product=producto, product_uom_qty=1, price_unit=Decimal('100.00'))
    assert so.state == SaleOrder.STATE_DRAFT
    so.action_confirm()
    so.refresh_from_db()
    assert so.state == SaleOrder.STATE_SALE
    assert so.name and so.name.startswith('S')
    assert so.date_order is not None


def test_confirm_empty_blocked(db):
    so = SaleOrder.objects.create()
    with pytest.raises(ValidationError):
        so.action_confirm()


def test_cancel_locked_blocked(producto):
    so = SaleOrder.objects.create()
    SaleOrderLine.objects.create(order=so, product=producto, product_uom_qty=1, price_unit=Decimal('100.00'))
    so.action_lock()
    with pytest.raises(ValidationError):
        so.action_cancel()
    so.action_unlock()
    so.action_cancel()
    so.refresh_from_db()
    assert so.state == SaleOrder.STATE_CANCEL


def test_draft_reopens_from_cancel(db):
    so = SaleOrder.objects.create(state=SaleOrder.STATE_CANCEL)
    so.action_draft()
    so.refresh_from_db()
    assert so.state == SaleOrder.STATE_DRAFT


# ---------------------------------------------------------------- sales_team

def test_crm_team_and_membership(db, django_user_model):
    team = CrmTeam.objects.create(name='Ventas MX', sequence=5, color=3)
    u = django_user_model.objects.create_user(login='v1@practicayoruba.mx', password='x')
    CrmTeamMember.objects.create(crm_team=team, user=u)
    assert team.members.count() == 1
    assert list(CrmTeam.objects.all()) == [team]  # _order sequence
    # unique(crm_team, user)
    with pytest.raises(Exception):
        CrmTeamMember.objects.create(crm_team=team, user=u)


def test_crm_tag_unique(db):
    CrmTag.objects.create(name='VIP')
    with pytest.raises(Exception):
        CrmTag.objects.create(name='VIP')


def test_sale_order_team_id(db):
    team = CrmTeam.objects.create(name='Equipo A')
    so = SaleOrder.objects.create(team=team)
    assert so.team.name == 'Equipo A'
    assert so in team.sale_orders.all()


# ---------------------------------------------------------------- sale_stock

def test_delivery_status_branches(producto):
    so = SaleOrder.objects.create()
    d = SaleOrderDelivery.objects.create(order=so)
    line = SaleOrderLine.objects.create(order=so, product=producto, product_uom_qty=4, price_unit=Decimal('10.00'))
    ld = SaleOrderLineDelivery.objects.create(line=line, qty_delivered=0)
    assert d.refresh_status() == SaleOrderDelivery.STATUS_PENDING
    assert ld.qty_to_deliver() == 4
    ld.qty_delivered = 2; ld.save()
    assert d.refresh_status() == SaleOrderDelivery.STATUS_PARTIAL
    assert ld.qty_to_deliver() == 2
    ld.qty_delivered = 4; ld.save()
    assert d.refresh_status() == SaleOrderDelivery.STATUS_FULL
    assert ld.qty_to_deliver() == 0


def test_order_reverse_accessor(producto):
    so = SaleOrder.objects.create()
    SaleOrderDelivery.objects.create(order=so, delivery_status='full')
    assert so.delivery.delivery_status == 'full'


# ---------------------------------------------------------------- sale_loyalty

def test_coupon_discount(producto):
    v = Voucher.objects.create(
        code='LOY10', voucher_type='PERCENTAGE', discount_pct=Decimal('10.00'),
        valid_from=timezone.now(), is_active=True,
    )
    so = SaleOrder.objects.create()
    SaleOrderLine.objects.create(order=so, product=producto, product_uom_qty=2, price_unit=Decimal('100.00'))
    coupon = SaleOrderCoupon.objects.create(order=so, voucher=v)
    # 10% de amount_untaxed 172.41 = 17.24
    assert coupon.discount_amount() == Decimal('17.24')
    assert coupon.amount_total_after_discount() == Decimal('182.76')


def test_coupon_no_voucher(producto):
    so = SaleOrder.objects.create()
    SaleOrderLine.objects.create(order=so, product=producto, product_uom_qty=1, price_unit=Decimal('100.00'))
    coupon = SaleOrderCoupon.objects.create(order=so, voucher=None)
    assert coupon.discount_amount() == Decimal('0.00')
