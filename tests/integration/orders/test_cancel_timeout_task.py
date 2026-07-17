"""
Tests — UC-SYS-01: cancel_timeout_orders task.

Verifica que ordenes PENDING con mas de ORDER_PAYMENT_TIMEOUT_MINUTES
de antiguedad son canceladas con STATUS_CANCELLED_BY_TIMEOUT.
"""
import pytest
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from addons.catalogue.models import Category, Product
from addons.inventory.models import StockMovement
from addons.orders.models import Order, OrderItem, OrderStatusLog
from addons.orders.tasks import cancel_timeout_orders, ORDER_PAYMENT_TIMEOUT_MINUTES

pytestmark = pytest.mark.django_db


def _make_pending_order(age_minutes=ORDER_PAYMENT_TIMEOUT_MINUTES + 10):
    order = Order.objects.create(status=Order.STATUS_PENDING)
    Order.objects.filter(pk=order.pk).update(
        created_at=timezone.now() - timedelta(minutes=age_minutes)
    )
    order.refresh_from_db()
    return order


def _make_product(stock=7):
    cat = Category.objects.create(name='Cat Timeout', slug='cat-timeout',
                                  is_active=True)
    p = Product.objects.create(
        name='Prod Timeout', slug='prod-timeout', sku='SKU-TO',
        price=Decimal('900.00'), stock=stock,
        is_active=True, is_published=True,
    )
    p.categories.add(cat)
    return p


class TestCancelTimeoutOrders:

    def test_cancela_ordenes_pendientes_antiguas(self):
        order = _make_pending_order(age_minutes=ORDER_PAYMENT_TIMEOUT_MINUTES + 10)
        count = cancel_timeout_orders()
        order.refresh_from_db()
        assert order.status == Order.STATUS_CANCELLED_BY_TIMEOUT
        assert order.cancellation_reason == 'TIMEOUT'
        assert order.cancelled_at is not None
        assert count >= 1

    def test_respeta_ordenes_dentro_de_ventana(self):
        order = _make_pending_order(age_minutes=5)
        cancel_timeout_orders()
        order.refresh_from_db()
        assert order.status == Order.STATUS_PENDING

    def test_ignora_ordenes_no_pending(self):
        order = _make_pending_order(age_minutes=ORDER_PAYMENT_TIMEOUT_MINUTES + 10)
        Order.objects.filter(pk=order.pk).update(status=Order.STATUS_PROCESSING)
        order.refresh_from_db()
        cancel_timeout_orders()
        order.refresh_from_db()
        assert order.status == Order.STATUS_PROCESSING

    def test_crea_status_log(self):
        order = _make_pending_order(age_minutes=ORDER_PAYMENT_TIMEOUT_MINUTES + 10)
        cancel_timeout_orders()
        log = OrderStatusLog.objects.filter(order=order).first()
        assert log is not None
        assert log.previous_status == Order.STATUS_PENDING
        assert log.new_status == Order.STATUS_CANCELLED_BY_TIMEOUT
        assert log.changed_by is None

    def test_restaura_stock_al_cancelar_por_timeout(self):
        # UC-SYS-01 POST-02 / BR-016: el stock decrementado en checkout se
        # restaura al cancelar por timeout (simetrico con la cancelacion
        # manual). Sin esto el stock queda "perdido" en ordenes impagas.
        product = _make_product(stock=7)  # 7 = 10 inicial - 3 del checkout
        order = _make_pending_order(age_minutes=ORDER_PAYMENT_TIMEOUT_MINUTES + 10)
        OrderItem.objects.create(
            order=order, product=product, product_name=product.name,
            sku=product.sku, unit_price=product.price, quantity=3,
            subtotal=product.price * 3,
        )
        cancel_timeout_orders()
        product.refresh_from_db()
        assert product.stock == 10  # 7 + 3 restaurados
        mov = StockMovement.objects.filter(
            product=product,
            movement_type=StockMovement.TYPE_CANCELLATION,
            reference=order.order_number,
        ).first()
        assert mov is not None
        assert mov.delta == 3

    def test_restaura_stock_es_idempotente(self):
        # Correr la tarea dos veces no restaura el stock dos veces
        # (idempotencia por reference=order_number en InventoryService).
        product = _make_product(stock=7)
        order = _make_pending_order(age_minutes=ORDER_PAYMENT_TIMEOUT_MINUTES + 10)
        OrderItem.objects.create(
            order=order, product=product, product_name=product.name,
            sku=product.sku, unit_price=product.price, quantity=3,
            subtotal=product.price * 3,
        )
        cancel_timeout_orders()
        cancel_timeout_orders()  # la orden ya no es PENDING; no re-restaura
        product.refresh_from_db()
        assert product.stock == 10
        assert StockMovement.objects.filter(
            product=product, reference=order.order_number,
            movement_type=StockMovement.TYPE_CANCELLATION,
        ).count() == 1
