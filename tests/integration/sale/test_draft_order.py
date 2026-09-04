"""Tests — servicios del draft sobre el canónico ``sale`` (V2 orders→sale).

El carrito de Odoo es un ``sale.order`` en ``state='draft'``. S1–S3
construyeron los servicios del draft sobre el strangler ``orders.Order``;
V2 (``analisis-unificar-orders-sale``) los conmuta a ``sale.SaleOrder`` +
``SaleOrderLine`` con el voucher anclado por ``SaleOrderCoupon``
(H-CART-CL-02). Este archivo re-ancla la MISMA cobertura de S1–S2c-2b al
canónico.

**Retiro parcial (H-API, este pase):** ``TestDraftSerializersS2c2b`` probaba
``addons.cart.serializers.DraftCartSerializer``/``DraftItemSerializer`` —
ninguno de los dos existe (``grep -rln "DraftCartSerializer\\|
DraftItemSerializer" src/addons/`` → vacío); el contrato HTTP del carrito se
disolvió con el addon ``cart`` (ver ``test_cart.py``) y no tiene sucesor en
``sale.serializers`` (que sólo serializa la orden ya confirmada). La clase se
retira; el resto del módulo (servicios del draft, sin HTTP) se conserva.
"""
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from addons.base_setup.settings_access import get_setting
from addons.sale.models import SaleOrder, SaleOrderLine
from decimal import Decimal

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
from tests.factories.product_factory import get_stock, make_category, make_product, set_stock

pytestmark = pytest.mark.django_db

User = get_user_model()


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

    def test_authenticated_user_gets_single_draft(self):
        user = User.objects.create_user(
            login='draft-s2@practicayoruba.mx', password='x')
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


class TestUnDraftPorPartnerEnLaBase:
    """H-API-309 — el invariante one-draft-per-partner lo garantiza la BASE.

    Antes se sostenía en ``get_or_create_draft_order`` *"porque MariaDB no
    soporta UNIQUE parcial"*. Con PostgreSQL (ADR-028) el índice único parcial
    existe, así que el invariante deja de depender de que todo el mundo pase
    por esa función: una migración de datos, un script de mantenimiento o dos
    peticiones concurrentes ya no lo pueden violar.

    Los cuatro casos que el índice debe distinguir — su condición es
    ``state='draft' AND partner_id IS NOT NULL``, y cada test fija un borde.
    """

    def test_segundo_draft_del_mismo_partner_es_rechazado(self):
        user = User.objects.create_user(
            login='h309-dup@practicayoruba.mx', password='x')
        SaleOrder.objects.create(partner=user, state=SaleOrder.STATE_DRAFT)
        with pytest.raises(IntegrityError):
            SaleOrder.objects.create(partner=user, state=SaleOrder.STATE_DRAFT)

    def test_orden_confirmada_no_colisiona_con_el_draft(self):
        """El índice sólo cubre ``draft``: confirmar no bloquea el siguiente
        carrito, que es justo el flujo normal del comprador recurrente."""
        user = User.objects.create_user(
            login='h309-sale@practicayoruba.mx', password='x')
        SaleOrder.objects.create(partner=user, state=SaleOrder.STATE_SALE)
        SaleOrder.objects.create(partner=user, state=SaleOrder.STATE_SALE)
        draft = SaleOrder.objects.create(
            partner=user, state=SaleOrder.STATE_DRAFT)
        assert draft.pk is not None

    def test_carritos_anonimos_quedan_fuera_del_indice(self):
        """``partner_id IS NOT NULL`` en la condición: N carritos anónimos en
        draft conviven. Su unicidad es otra — la columna ``cart_token``."""
        a = SaleOrder.objects.create(state=SaleOrder.STATE_DRAFT)
        b = SaleOrder.objects.create(state=SaleOrder.STATE_DRAFT)
        assert a.pk != b.pk

    def test_dos_partners_distintos_tienen_su_propio_draft(self):
        u1 = User.objects.create_user(
            login='h309-u1@practicayoruba.mx', password='x')
        u2 = User.objects.create_user(
            login='h309-u2@practicayoruba.mx', password='x')
        SaleOrder.objects.create(partner=u1, state=SaleOrder.STATE_DRAFT)
        SaleOrder.objects.create(partner=u2, state=SaleOrder.STATE_DRAFT)
        assert SaleOrder.objects.filter(
            state=SaleOrder.STATE_DRAFT, partner__isnull=False).count() == 2


@pytest.fixture
def draft_product(db):
    cat = make_category(name='Cat Draft')
    return make_product(name='Prod Draft S2b', price=Decimal('100.00'),
                        stock=5, categ=cat)


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
        rate = get_setting('iva_rate')
        total = Decimal('200.00')
        expected_tax = (total * rate / (Decimal('1') + rate)).quantize(
            Decimal('0.01'))
        assert line.price_total == total
        assert line.price_tax == expected_tax
        assert line.price_subtotal == total - expected_tax

    def test_current_price_and_availability(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        line, _ = add_item_to_draft(order, draft_product, quantity=1)
        assert line.current_price() == Decimal('100.00')
        assert line.is_available() is True
        assert line.available_stock() == get_stock(draft_product)

    def test_is_available_false_when_product_inactive(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        line, _ = add_item_to_draft(order, draft_product, quantity=1)
        draft_product.active = False
        draft_product.save(update_fields=['active'])
        line.refresh_from_db()
        assert line.is_available() is False

    def test_is_available_false_when_out_of_stock(self, draft_product):
        order, _ = get_or_create_draft_order(cart_token=uuid.uuid4())
        line, _ = add_item_to_draft(order, draft_product, quantity=1)
        set_stock(draft_product, 0)
        line.refresh_from_db()
        assert line.is_available() is False
        assert line.available_stock() == 0


class TestMergeDraftOrdersS2c2b:
    """Fusión del draft anónimo al autenticado (UC-CART-06)."""

    def test_merge_moves_items_and_deletes_anon_draft(self, draft_product):
        user = User.objects.create_user(
            login='merge-s2c@practicayoruba.mx', password='x')
        token = uuid.uuid4()
        anon, _ = get_or_create_draft_order(cart_token=token)
        add_item_to_draft(anon, draft_product, quantity=2)

        order, skipped = merge_draft_orders(user, token)
        assert skipped == []
        assert order.partner_id == user.pk
        assert order.order_line.count() == 1
        assert order.order_line.first().product_uom_qty == 2
        assert not SaleOrder.objects.filter(pk=anon.pk).exists()

    def test_merge_caps_quantity_to_stock(self, draft_product):
        user = User.objects.create_user(
            login='merge-cap@practicayoruba.mx', password='x')
        auth, _ = get_or_create_draft_order(user=user)
        add_item_to_draft(auth, draft_product, quantity=4)
        token = uuid.uuid4()
        anon, _ = get_or_create_draft_order(cart_token=token)
        add_item_to_draft(anon, draft_product, quantity=3)

        order, skipped = merge_draft_orders(user, token)
        line = order.order_line.get()
        assert line.product_uom_qty == 5  # 4+3 recortado al stock=5
        assert skipped == []

    def test_merge_skips_out_of_stock(self, draft_product):
        user = User.objects.create_user(
            login='merge-skip@practicayoruba.mx', password='x')
        token = uuid.uuid4()
        anon, _ = get_or_create_draft_order(cart_token=token)
        add_item_to_draft(anon, draft_product, quantity=1)
        set_stock(draft_product, 0)

        order, skipped = merge_draft_orders(user, token)
        assert order.order_line.count() == 0
        assert skipped == [{'product_id': draft_product.pk,
                            'product_name': draft_product.name,
                            'reason': 'OUT_OF_STOCK'}]

    def test_merge_without_anon_draft_returns_auth_draft(self):
        user = User.objects.create_user(
            login='merge-noop@practicayoruba.mx', password='x')
        order, skipped = merge_draft_orders(user, uuid.uuid4())
        assert order.partner_id == user.pk
        assert skipped == []
