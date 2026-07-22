"""Tests — S1 de la unificación cart→order→sale (analisis-unificar-cart-order-sale).

El carrito de Odoo es un ``sale.order`` en ``state='draft'`` — no una tabla
aparte. S1 hace la migración additiva: ``Order.status`` gana ``DRAFT`` y
``Order`` gana ``cart_token`` (paridad con ``cart.Cart.cart_token`` para el
carrito anónimo). Nada se borra ni se copia todavía (S2+).
"""
import uuid

import pytest
from django.db import IntegrityError

from addons.orders.models import Order
from decimal import Decimal

from addons.catalogue.models import Category, Product
from addons.orders.services import (
    DraftOrderError,
    add_item_to_draft,
    clear_draft_items,
    get_draft_totals,
    remove_draft_item,
    update_draft_item_quantity,
    get_or_create_draft_order,
)

pytestmark = pytest.mark.django_db


class TestDraftOrderS1:
    def test_draft_status_is_a_valid_choice(self):
        assert Order.STATUS_DRAFT == 'DRAFT'
        assert Order.STATUS_DRAFT in dict(Order.STATUSES)

    def test_order_persists_as_draft_with_cart_token(self):
        token = uuid.uuid4()
        order = Order.objects.create(
            order_number=f'D-{str(uuid.uuid4())[:8]}',
            status=Order.STATUS_DRAFT,
            cart_token=token,
        )
        order.refresh_from_db()
        assert order.status == Order.STATUS_DRAFT
        assert order.cart_token == token

    def test_cart_token_is_unique(self):
        token = uuid.uuid4()
        Order.objects.create(
            order_number=f'D-{str(uuid.uuid4())[:8]}',
            status=Order.STATUS_DRAFT,
            cart_token=token,
        )
        with pytest.raises(IntegrityError):
            Order.objects.create(
                order_number=f'D-{str(uuid.uuid4())[:8]}',
                status=Order.STATUS_DRAFT,
                cart_token=token,
            )

    def test_cart_token_is_optional_multiple_null_allowed(self):
        a = Order.objects.create(
            order_number=f'D-{str(uuid.uuid4())[:8]}', status=Order.STATUS_DRAFT)
        b = Order.objects.create(
            order_number=f'D-{str(uuid.uuid4())[:8]}', status=Order.STATUS_DRAFT)
        assert a.cart_token is None and b.cart_token is None


class TestGetOrCreateDraftOrderS2:
    """S2a: espejo de _get_or_create_cart sobre Order(DRAFT)."""

    def test_authenticated_user_gets_single_draft(self, django_user_model):
        user = django_user_model.objects.create_user(
            email='draft-s2@test.mx', password='x')
        a, created_a = get_or_create_draft_order(user=user)
        b, created_b = get_or_create_draft_order(user=user)
        assert created_a is True and created_b is False
        assert a.pk == b.pk
        assert a.status == Order.STATUS_DRAFT

    def test_anonymous_token_reuses_draft(self):
        token = uuid.uuid4()
        a, created_a = get_or_create_draft_order(cart_token=token)
        b, created_b = get_or_create_draft_order(cart_token=token)
        assert created_a is True and created_b is False
        assert a.pk == b.pk and a.cart_token == token

    def test_anonymous_without_token_mints_one(self):
        order, created = get_or_create_draft_order()
        assert created is True
        assert order.status == Order.STATUS_DRAFT
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
    """S2b: paridad de operaciones de items sobre Order(DRAFT)."""

    def test_add_item_snapshots_and_merges(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        item, created = add_item_to_draft(order, draft_product, quantity=2)
        assert created is True
        assert item.product_name == draft_product.name
        assert item.sku == draft_product.sku
        assert item.unit_price == Decimal('100.00')
        assert item.subtotal == Decimal('200.00')

        item2, created2 = add_item_to_draft(order, draft_product, quantity=1)
        assert created2 is False and item2.pk == item.pk
        item2.refresh_from_db()
        assert item2.quantity == 3
        assert item2.subtotal == Decimal('300.00')

    def test_add_item_respects_stock(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        with pytest.raises(DraftOrderError) as exc:
            add_item_to_draft(order, draft_product, quantity=6)
        assert exc.value.codigo_error == 'INSUFFICIENT_STOCK'

    def test_add_item_rejects_non_draft(self, draft_product):
        order = Order.objects.create(
            order_number=f'D-{str(uuid.uuid4())[:8]}', status=Order.STATUS_PENDING)
        with pytest.raises(DraftOrderError) as exc:
            add_item_to_draft(order, draft_product, quantity=1)
        assert exc.value.codigo_error == 'ORDEN_NO_DRAFT'

    def test_clear_draft_items(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        add_item_to_draft(order, draft_product, quantity=1)
        assert order.items.count() == 1
        clear_draft_items(order)
        assert order.items.count() == 0


class TestDraftTotalsS2c:
    """S2c-1: paridad del contrato de totales con Cart.get_totals."""

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
    """S2c-2a: paridad de patch/delete de item sobre el draft."""

    def test_update_quantity_and_subtotal(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        item, _ = add_item_to_draft(order, draft_product, quantity=1)
        updated = update_draft_item_quantity(order, item.pk, 4)
        assert updated.quantity == 4
        assert updated.subtotal == Decimal('400.00')

    def test_update_quantity_respects_stock(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        item, _ = add_item_to_draft(order, draft_product, quantity=1)
        with pytest.raises(DraftOrderError) as exc:
            update_draft_item_quantity(order, item.pk, 6)
        assert exc.value.codigo_error == 'INSUFFICIENT_STOCK'

    def test_update_missing_item_raises(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        with pytest.raises(DraftOrderError) as exc:
            update_draft_item_quantity(order, 999999, 1)
        assert exc.value.codigo_error == 'ITEM_NOT_FOUND'

    def test_remove_item(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        item, _ = add_item_to_draft(order, draft_product, quantity=1)
        remove_draft_item(order, item.pk)
        assert order.items.count() == 0
