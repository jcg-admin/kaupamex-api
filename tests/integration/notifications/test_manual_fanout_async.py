"""
Tests — D-004: manual notification fanout async/sync branching.

Verifica que `AdminManualNotificationCreateView`:

* Para audiencias <= MANUAL_FANOUT_ASYNC_THRESHOLD ejecuta el fanout
  sincronamente inline (preservando el comportamiento previo a D-004).
* Para audiencias > threshold despacha el task
  `dispatch_manual_fanout` a Celery; en tests se usa
  `CELERY_TASK_ALWAYS_EAGER=True` para evitar la dependencia de redis.

JSON keys + identificadores en ingles (DEC-DOC-005).
"""
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings


ADMIN_MANUAL_URL = '/api/v1/admin/notifications/manual/'


def _create_buyers(n):
    """Crea n usuarios y los enlaza a OrderItem(product=<producto creado>).

    Usa importacion diferida para que la fixture solo arme objetos de
    orders/catalogue cuando este test corre — evita romper el modulo
    si esas apps cambian en otros bumps.
    """
    from decimal import Decimal

    from apps.catalogue.models import Category, Product
    from apps.orders.models import Order, OrderItem

    category, _ = Category.objects.get_or_create(
        name='Fanout cat', defaults={'slug': 'fanout-cat'},
    )
    product = Product.objects.create(
        name='Fanout product',
        slug='fanout-product-d004',
        sku='SKU-D004-FANOUT',
        price=Decimal('10.00'),
        stock=100,
        category=category,
    )

    User = get_user_model()
    user_ids = []
    for i in range(n):
        u = User.objects.create_user(
            username=f'fanoutbuyer{i}',
            email=f'fanoutbuyer{i}@practicayoruba.mx',
            password='Pw123456!',
        )
        order = Order.objects.create(user=u)
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            sku=f'sku-{i}',
            unit_price=Decimal('10.00'),
            quantity=1,
            subtotal=Decimal('10.00'),
        )
        user_ids.append(u.id)
    return user_ids, product.id


@pytest.mark.integration
class TestManualFanoutBranching:
    """D-004 — async / sync branching at recipient threshold."""

    @override_settings(
        CELERY_TASK_ALWAYS_EAGER=True,
        MANUAL_FANOUT_ASYNC_THRESHOLD=100,
    )
    def test_below_threshold_runs_synchronously(
        self, admin_client, user, db,
    ):
        """1 destinatario <= 100 -> fanout sincrono (sin .delay)."""
        with mock.patch(
            'apps.notifications.views.dispatch_manual_fanout.delay'
        ) as mocked_delay:
            res = admin_client.post(ADMIN_MANUAL_URL, {
                'recipient_type': 'USER',
                'recipient_identifier': user.username,
                'subject': 'Sync branch',
                'message': 'Mensaje sincronico.',
            }, format='json')

        assert res.status_code == 201
        assert res.json()['recipients_count'] == 1
        # No se despacho al broker porque la audiencia esta bajo el umbral.
        mocked_delay.assert_not_called()

        from apps.notifications.models import Notification
        assert Notification.objects.filter(
            user=user, subject='Sync branch',
        ).count() == 1

    @override_settings(
        CELERY_TASK_ALWAYS_EAGER=True,
        MANUAL_FANOUT_ASYNC_THRESHOLD=2,
    )
    def test_above_threshold_dispatches_to_celery_eager(
        self, admin_client, db,
    ):
        """3 destinatarios > threshold(2) -> .delay() + eager ejecuta task."""
        user_ids, product_id = _create_buyers(3)

        with mock.patch(
            'apps.notifications.views.dispatch_manual_fanout.delay',
            wraps=__import__(
                'apps.notifications.tasks', fromlist=['dispatch_manual_fanout']
            ).dispatch_manual_fanout.delay,
        ) as spy_delay:
            res = admin_client.post(ADMIN_MANUAL_URL, {
                'recipient_type': 'PRODUCT_BUYERS',
                'product_id': product_id,
                'subject': 'Async branch',
                'message': 'Mensaje masivo.',
            }, format='json')

        assert res.status_code == 201
        assert res.json()['recipients_count'] == 3
        # Se despacho exactamente una vez al broker.
        assert spy_delay.call_count == 1

        # Con CELERY_TASK_ALWAYS_EAGER=True el task se ejecuto en proceso
        # y creo las Notification correspondientes.
        from apps.notifications.models import Notification
        created = Notification.objects.filter(subject='Async branch')
        assert created.count() == 3
        assert set(created.values_list('user_id', flat=True)) == set(user_ids)
