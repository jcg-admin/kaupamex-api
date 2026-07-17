"""
Tests — UC-NOT-07: manual notification fanout (sincrono, sin broker).

El fanout es sincrono: AdminManualNotificationCreateView llama
dispatch_manual_fanout() directamente (cnst-arquitectura T6:
Celery prohibido, alternativa Cron + Management Commands).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model

from addons.catalogue.models import Category, Product
from addons.notifications.models import ManualNotification, Notification
from addons.orders.models import Order, OrderItem

import pytest


ADMIN_MANUAL_URL = '/api/v2/admin/notifications/'


def _create_buyers(n):
    """Crea n usuarios enlazados a OrderItem sobre un producto comun."""
    category, _ = Category.objects.get_or_create(
        name='Fanout cat', defaults={'slug': 'fanout-cat'},
    )
    product = Product.objects.create(
        name='Fanout product',
        slug='fanout-product-sync',
        sku='SKU-SYNC-FANOUT',
        price=Decimal('10.00'),
        stock=100,
    )
    product.categories.add(category)
    User = get_user_model()
    user_ids = []
    for i in range(n):
        u = User.objects.create_user(
            email=f'syncbuyer{i}@practicayoruba.mx',
            password='Pw123456!',
        )
        order = Order.objects.create(user=u)
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            sku=f'sku-sync-{i}',
            unit_price=Decimal('10.00'),
            quantity=1,
            subtotal=Decimal('10.00'),
        )
        user_ids.append(u.id)
    return user_ids, product.id


@pytest.mark.integration
class TestManualFanoutSync:
    """UC-NOT-07 — fanout sincrono sin broker (cnst-arquitectura T6)."""

    def test_fanout_usuario_individual(self, admin_client, user, db):
        """POST manual para USER crea ManualNotification y Notification."""
        res = admin_client.post(ADMIN_MANUAL_URL, {
            'recipient_type': 'USER',
            'recipient_identifier': user.email,
            'subject': 'Test individual',
            'message': 'Mensaje de prueba.',
        }, format='json')

        assert res.status_code == 201
        data = res.json()
        assert data['recipients_count'] == 1
        assert Notification.objects.filter(
            user=user, subject='Test individual',
        ).count() == 1
        assert ManualNotification.objects.filter(subject='Test individual').exists()

    def test_fanout_product_buyers(self, admin_client, db):
        """POST manual para PRODUCT_BUYERS crea Notification por comprador."""
        user_ids, product_id = _create_buyers(3)

        res = admin_client.post(ADMIN_MANUAL_URL, {
            'recipient_type': 'PRODUCT_BUYERS',
            'product_id': product_id,
            'subject': 'Notif compradores',
            'message': 'Para todos los compradores.',
        }, format='json')

        assert res.status_code == 201
        assert res.json()['recipients_count'] == 3
        created = Notification.objects.filter(subject='Notif compradores')
        assert created.count() == 3
        assert set(created.values_list('user_id', flat=True)) == set(user_ids)

    def test_fanout_sin_destinatarios_status_failed(
        self, admin_client, db,
    ):
        """POST manual con recipient inexistente: recipients_count=0, status=FAILED."""
        res = admin_client.post(ADMIN_MANUAL_URL, {
            'recipient_type': 'USER',
            'recipient_identifier': 'inexistente-usuario-xyz',
            'subject': 'Sin destinatarios',
            'message': 'Mensaje sin destino.',
        }, format='json')

        assert res.status_code == 201
        data = res.json()
        assert data['recipients_count'] == 0
        manual = ManualNotification.objects.filter(subject='Sin destinatarios').first()
        assert manual is not None
        assert manual.status == ManualNotification.Status.FAILED
        assert Notification.objects.filter(subject='Sin destinatarios').count() == 0
