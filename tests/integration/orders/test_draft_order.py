"""Tests — servicios del draft sobre el canónico ``sale`` (V2 orders→sale).

El carrito de Odoo es un ``sale.order`` en ``state='draft'``. S1–S3
construyeron los servicios del draft sobre el strangler ``orders.Order``;
V2 (``analisis-unificar-orders-sale``) los conmuta a ``sale.SaleOrder`` +
``SaleOrderLine`` con el voucher anclado por ``SaleOrderCoupon``
(H-CART-CL-02). Este archivo re-ancla la MISMA cobertura de S1–S2c-2b al
canónico.
"""
import uuid

import pytest
from django.db import IntegrityError

from addons.base.models import SiteSettings
from addons.sale.models import SaleOrder, SaleOrderLine
from decimal import Decimal

from addons.catalogue.models import Category, Product
from addons.cart.serializers import DraftCartSerializer, DraftItemSerializer
from addons.sale.services import (
    DraftOrderError,
    add_item_to_draft,
    clear_draft_items,
    get_draft_totals,
    merge_draft_orders,
    remove_draft_item,
    update_draft_item_quantity,
    get_or_create_draft_order,
)

pytestmark = pytest.mark.django_db


class TestDraftSaleOrderV2:
    def test_draft_state_is_a_valid_choice(self):
        assert SaleOrder.STATE_DRAFT == 'draft'
        assert SaleOrder.STATE_DRAFT in dict(SaleOrder.STATES)

    def test_sale_order_persists_as_draft_with_cart_token(self):
        token = uuid.uuid4()
        order = SaleOrder.objects.create(
            state=SaleOrder.STATE_DRAFT, cart_token=token)
        order.refresh_from_db()
        assert order.state == SaleOrder.STATE_DRAFT
        assert order.cart_token == token
        assert order.name is None  # el nombre SO se acuña al confirmar

    def test_cart_token_is_unique(self):
        token = uuid.uuid4()
        SaleOrder.objects.create(state=SaleOrder.STATE_DRAFT, cart_token=token)
        with pytest.raises(IntegrityError):
            SaleOrder.objects.create(
                state=SaleOrder.STATE_DRAFT, cart_token=token)

    def test_cart_token_is_optional_multiple_null_allowed(self):
        a = SaleOrder.objects.create(state=SaleOrder.STATE_DRAFT)
        b = SaleOrder.objects.create(state=SaleOrder.STATE_DRAFT)
        assert a.cart_token is None and b.cart_token is None


class TestGetOrCreateDraftOrderS2:
    """Espejo de _get_or_create_cart sobre SaleOrder(draft)."""

    def test_authenticated_user_gets_single_draft(self, django_user_model):
        user = django_user_model.objects.create_user(
            email='draft-s2@test.mx', password='x')
        a, created_a = get_or_create_draft_order(user=user)
        b, created_b = get_or_create_draft_order(user=user)
        assert created_a is True and created_b is False
        assert a.pk == b.pk
        assert a.state == SaleOrder.STATE_DRAFT

    def test_anonymous_token_reuses_draft(self):
        token = uuid.uuid4()
        a, created_a = get_or_create_draft_order(cart_token=token)
        b, created_b = get_or_create_draft_order(cart_token=token)
        assert created_a is True and created_b is False
        assert a.pk == b.pk and a.cart_token == token

    def test_anonymous_without_token_mints_one(self):
        order, created = get_or_create_draft_order()
        assert created is True
        assert order.state == SaleOrder.STATE_DRAFT
        assert order.cart_token is not None


@pytest.fixture
def draft_product(db):
    cat = Category.objects.create(name='Cat Draft', slug='cat-draft-s2b', is_active=True)
    p = Product.objects.create(
        name='Prod Draft S2b', slug='prod-draft-s2b', sku='S2B-001',
        description='', price=Decimal('100.00'), stock=5,
        is_active=True, is_published=True,
    )
    p.categories.add(cat)
    return p


class TestDraftItemOperationsS2b:
    """Paridad de operaciones de líneas sobre SaleOrder(draft)."""

    def test_add_item_snapshots_and_merges(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        line, created = add_item_to_draft(order, draft_product, quantity=2)
        assert created is True
        assert line.name == draft_product.name
        assert line.price_unit == Decimal('100.00')
        assert line.price_unit * line.product_uom_qty == Decimal('200.00')

        line2, created2 = add_item_to_draft(order, draft_product, quantity=1)
        assert created2 is False and line2.pk == line.pk
        line2.refresh_from_db()
        assert line2.product_uom_qty == 3

    def test_add_item_respects_stock(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        with pytest.raises(DraftOrderError) as exc:
            add_item_to_draft(order, draft_product, quantity=6)
        assert exc.value.codigo_error == 'INSUFFICIENT_STOCK'

    def test_add_item_rejects_non_draft(self, draft_product):
        order = SaleOrder.objects.create(state=SaleOrder.STATE_SALE)
        with pytest.raises(DraftOrderError) as exc:
            add_item_to_draft(order, draft_product, quantity=1)
        assert exc.value.codigo_error == 'ORDER_NOT_DRAFT'

    def test_clear_draft_items(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        add_item_to_draft(order, draft_product, quantity=1)
        assert order.order_line.count() == 1
        clear_draft_items(order)
        assert order.order_line.count() == 0


class TestDraftTotalsS2c:
    """Paridad del contrato de totales (13 claves) con el histórico."""

    CART_TOTALS_KEYS = {
        'subtotal', 'discount', 'subtotal_net', 'tax_included',
        'shipping_cost', 'total', 'free_shipping_threshold',
        'free_shipping_remaining', 'free_shipping_applied',
        'amount_untaxed', 'amount_tax', 'amount_total', 'item_count',
    }

    def test_totals_contract_keys_match_cart(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        add_item_to_draft(order, draft_product, quantity=2)
        totals = get_draft_totals(order)
        assert set(totals.keys()) == self.CART_TOTALS_KEYS

    def test_totals_math_simple(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        add_item_to_draft(order, draft_product, quantity=2)
        totals = get_draft_totals(order)
        assert totals['subtotal'] == '200.00'
        assert totals['discount'] == '0.00'
        assert totals['total'] == '200.00'
        assert totals['item_count'] == 1


class TestDraftItemUpdateRemoveS2c2:
    """Paridad de patch/delete de línea sobre el draft."""

    def test_update_quantity(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        line, _ = add_item_to_draft(order, draft_product, quantity=1)
        updated = update_draft_item_quantity(order, line.pk, 4)
        assert updated.product_uom_qty == 4
        assert updated.price_unit * updated.product_uom_qty == Decimal('400.00')

    def test_update_quantity_respects_stock(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        line, _ = add_item_to_draft(order, draft_product, quantity=1)
        with pytest.raises(DraftOrderError) as exc:
            update_draft_item_quantity(order, line.pk, 6)
        assert exc.value.codigo_error == 'INSUFFICIENT_STOCK'

    def test_update_missing_item_raises(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        with pytest.raises(DraftOrderError) as exc:
            update_draft_item_quantity(order, 999999, 1)
        assert exc.value.codigo_error == 'ITEM_NOT_FOUND'

    def test_remove_item(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        line, _ = add_item_to_draft(order, draft_product, quantity=1)
        remove_draft_item(order, line.pk)
        assert order.order_line.count() == 0


class TestSaleOrderLineMethodsV2:
    """La matemática y disponibilidad de línea viven en SaleOrderLine
    (Odoo ``sale.order.line._compute_amount`` + estado vivo del catálogo).
    """

    def test_price_total_and_breakdown(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        line, _ = add_item_to_draft(order, draft_product, quantity=2)
        rate = SiteSettings.get_current().iva_rate
        total = Decimal('200.00')
        expected_tax = (total * rate / (Decimal('1') + rate)).quantize(
            Decimal('0.01'))
        assert line.price_total() == total
        assert line.price_tax() == expected_tax
        assert line.price_subtotal() == total - expected_tax

    def test_current_price_and_availability(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        line, _ = add_item_to_draft(order, draft_product, quantity=1)
        assert line.current_price() == Decimal('100.00')
        assert line.is_available() is True
        assert line.available_stock() == draft_product.stock

    def test_is_available_false_when_product_inactive(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        line, _ = add_item_to_draft(order, draft_product, quantity=1)
        draft_product.is_active = False
        draft_product.save(update_fields=['is_active'])
        line.refresh_from_db()
        assert line.is_available() is False

    def test_is_available_false_when_out_of_stock(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        line, _ = add_item_to_draft(order, draft_product, quantity=1)
        draft_product.stock = 0
        draft_product.save(update_fields=['stock'])
        line.refresh_from_db()
        assert line.is_available() is False
        assert line.available_stock() == 0


class TestDraftSerializersS2c2b:
    """El draft serializado con el contrato EXACTO del carrito."""

    CART_ITEM_KEYS = [
        'id', 'product_name', 'product_slug', 'variant_label', 'sku',
        'quantity', 'unit_price', 'subtotal',
        'price_subtotal', 'price_tax', 'price_total',
        'available_stock', 'is_available', 'price_changed', 'image_url',
    ]

    def test_item_contract_matches_cart_item_serializer(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        add_item_to_draft(order, draft_product, quantity=2)
        data = DraftItemSerializer(order.order_line.first()).data
        assert list(data.keys()) == self.CART_ITEM_KEYS
        assert data['product_name'] == draft_product.name
        assert data['product_slug'] == draft_product.slug
        assert data['variant_label'] is None
        assert data['sku'] == draft_product.sku
        assert data['subtotal'] == '200.00'
        assert data['is_available'] is True
        assert data['price_changed'] is False

    def test_cart_contract_matches_cart_serializer(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        add_item_to_draft(order, draft_product, quantity=1)
        data = DraftCartSerializer(order).data
        assert list(data.keys()) == ['id', 'cart_token', 'items', 'totals']
        assert len(data['items']) == 1
        assert data['totals']['item_count'] == 1
        assert data['totals']['total'] == '100.00'


class TestMergeDraftOrdersS2c2b:
    """Fusión del draft anónimo al autenticado (UC-CART-06)."""

    def test_merge_moves_items_and_deletes_anon_draft(
            self, draft_product, django_user_model):
        user = django_user_model.objects.create_user(
            email='merge-s2c@test.mx', password='x')
        token = uuid.uuid4()
        anon, _ = get_or_create_draft_order(cart_token=token)
        add_item_to_draft(anon, draft_product, quantity=2)

        order, skipped = merge_draft_orders(user, token)
        assert skipped == []
        assert order.partner_id == user.pk
        assert order.order_line.count() == 1
        assert order.order_line.first().product_uom_qty == 2
        assert not SaleOrder.objects.filter(pk=anon.pk).exists()

    def test_merge_caps_quantity_to_stock(self, draft_product, django_user_model):
        user = django_user_model.objects.create_user(
            email='merge-cap@test.mx', password='x')
        auth, _ = get_or_create_draft_order(user=user)
        add_item_to_draft(auth, draft_product, quantity=4)
        token = uuid.uuid4()
        anon, _ = get_or_create_draft_order(cart_token=token)
        add_item_to_draft(anon, draft_product, quantity=3)

        order, skipped = merge_draft_orders(user, token)
        line = order.order_line.get()
        assert line.product_uom_qty == 5  # 4+3 recortado al stock=5
        assert skipped == []

    def test_merge_skips_out_of_stock(self, draft_product, django_user_model):
        user = django_user_model.objects.create_user(
            email='merge-skip@test.mx', password='x')
        token = uuid.uuid4()
        anon, _ = get_or_create_draft_order(cart_token=token)
        add_item_to_draft(anon, draft_product, quantity=1)
        draft_product.stock = 0
        draft_product.save(update_fields=['stock'])

        order, skipped = merge_draft_orders(user, token)
        assert order.order_line.count() == 0
        assert skipped == [{'product_id': draft_product.pk,
                            'product_name': draft_product.name,
                            'reason': 'OUT_OF_STOCK'}]

    def test_merge_without_anon_draft_returns_auth_draft(self, django_user_model):
        user = django_user_model.objects.create_user(
            email='merge-noop@test.mx', password='x')
        order, skipped = merge_draft_orders(user, uuid.uuid4())
        assert order.partner_id == user.pk
        assert skipped == []
