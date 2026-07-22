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
from addons.orders.services import get_or_create_draft_order

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
