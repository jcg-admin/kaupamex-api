"""Tests — S1 de la unificación cart→order→sale (analisis-unificar-cart-order-sale).

El carrito de Odoo es un ``sale.order`` en ``state='draft'`` — no una tabla
aparte. S1 hace la migración additiva: ``Order.status`` gana ``DRAFT`` y
``Order`` gana ``cart_token`` (paridad con ``cart.Cart.cart_token`` para el
carrito anónimo). Nada se borra ni se copia todavía (S2+).
"""
import uuid

import pytest
from django.db import IntegrityError

from addons.base.models import SiteSettings
from addons.orders.models import Order
from decimal import Decimal

from addons.catalogue.models import Category, Product
from addons.cart.serializers import DraftCartSerializer, DraftItemSerializer
from addons.orders.services import (
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


class TestOrderItemLineMethodsS2c2b:
    """S2c-2b: paridad de la matemática de línea con CartItem.

    En Odoo estos cálculos viven en ``sale.order.line``
    (price_subtotal/price_tax/price_total); ``OrderItem`` es su línea
    strangler, así que gana los mismos métodos que ``CartItem`` expone
    al serializer del carrito.
    """

    def test_price_total_and_breakdown(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        item, _ = add_item_to_draft(order, draft_product, quantity=2)
        rate = SiteSettings.get_current().iva_rate
        total = Decimal('200.00')
        expected_tax = (total * rate / (Decimal('1') + rate)).quantize(
            Decimal('0.01'))
        assert item.price_total() == total
        assert item.price_tax() == expected_tax
        assert item.price_subtotal() == total - expected_tax

    def test_current_price_and_availability(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        item, _ = add_item_to_draft(order, draft_product, quantity=1)
        assert item.current_price() == Decimal('100.00')
        assert item.is_available() is True
        assert item.available_stock() == draft_product.stock

    def test_is_available_false_when_product_inactive(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        item, _ = add_item_to_draft(order, draft_product, quantity=1)
        draft_product.is_active = False
        draft_product.save(update_fields=['is_active'])
        item.refresh_from_db()
        assert item.is_available() is False

    def test_is_available_false_when_out_of_stock(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        item, _ = add_item_to_draft(order, draft_product, quantity=1)
        draft_product.stock = 0
        draft_product.save(update_fields=['stock'])
        item.refresh_from_db()
        assert item.is_available() is False
        assert item.available_stock() == 0


class TestDraftSerializersS2c2b:
    """S2c-2b: el draft serializado con el contrato EXACTO del carrito."""

    CART_ITEM_KEYS = [
        'id', 'product_name', 'product_slug', 'variant_label', 'sku',
        'quantity', 'unit_price', 'subtotal',
        'price_subtotal', 'price_tax', 'price_total',
        'available_stock', 'is_available', 'price_changed', 'image_url',
    ]

    def test_item_contract_matches_cart_item_serializer(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        add_item_to_draft(order, draft_product, quantity=2)
        data = DraftItemSerializer(order.items.first()).data
        assert list(data.keys()) == self.CART_ITEM_KEYS
        assert data['product_name'] == draft_product.name
        assert data['product_slug'] == draft_product.slug
        assert data['variant_label'] is None
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
    """S2c-2b: fusión del draft anónimo al autenticado (UC-CART-06)."""

    def test_merge_moves_items_and_deletes_anon_draft(
            self, draft_product, django_user_model):
        user = django_user_model.objects.create_user(
            email='merge-s2c@test.mx', password='x')
        token = uuid.uuid4()
        anon, _ = get_or_create_draft_order(cart_token=token)
        add_item_to_draft(anon, draft_product, quantity=2)

        order, skipped = merge_draft_orders(user, token)
        assert skipped == []
        assert order.user_id == user.pk
        assert order.items.count() == 1
        assert order.items.first().quantity == 2
        assert not Order.objects.filter(pk=anon.pk).exists()

    def test_merge_caps_quantity_to_stock(self, draft_product, django_user_model):
        user = django_user_model.objects.create_user(
            email='merge-cap@test.mx', password='x')
        auth, _ = get_or_create_draft_order(user=user)
        add_item_to_draft(auth, draft_product, quantity=4)
        token = uuid.uuid4()
        anon, _ = get_or_create_draft_order(cart_token=token)
        add_item_to_draft(anon, draft_product, quantity=3)

        order, skipped = merge_draft_orders(user, token)
        item = order.items.get()
        assert item.quantity == 5  # 4+3 recortado al stock=5
        assert item.subtotal == Decimal('500.00')
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
        assert order.items.count() == 0
        assert skipped == [{'product_id': draft_product.pk,
                            'product_name': draft_product.name,
                            'reason': 'OUT_OF_STOCK'}]

    def test_merge_without_anon_draft_returns_auth_draft(self, django_user_model):
        user = django_user_model.objects.create_user(
            email='merge-noop@test.mx', password='x')
        order, skipped = merge_draft_orders(user, uuid.uuid4())
        assert order.user_id == user.pk
        assert skipped == []
