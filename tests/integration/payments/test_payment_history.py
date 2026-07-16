"""
Tests — Historial y estado de pagos (UC-PAY-05, UC-PAY-06)

Nombre descriptivo: describe el dominio (historial de pagos),
no el número de sprint.
"""
import pytest
from decimal import Decimal
from apps.addons.catalogue.models import Category, Product
from apps.addons.orders.models import Order, OrderItem, OrderValue, OrderAddress
from apps.addons.payments.models import Payment
from datetime import timedelta
from django.contrib.auth import get_user_model
from apps.addons.settings_app.models import PaymentGateway
import django.utils.timezone as tz

pytestmark = pytest.mark.integration

STATUS_URL   = lambda o: f'/api/v2/payments/{o}/status/'
HISTORY_URL  = lambda o: f'/api/v2/payments/{o}/history/'
RETRY_URL    = lambda o: f'/api/v2/payments/{o}/retry-eligibility/'


@pytest.fixture
def cat_hist(db):
    return Category.objects.create(name='Cat Hist', slug='cat-hist', is_active=True)


@pytest.fixture
def orden_con_pago(db, user, cat_hist):
    """Orden con un Payment APPROVED."""

    prod = Product.objects.create(
        name='Ide Orula', slug='ide-orula', sku='HIST-001',
        description='',
        price=Decimal('2400.00'), stock=3,
        is_active=True, is_published=True,
    )
    prod.categories.add(cat_hist)
    order = Order.objects.create(user=user, status='PROCESSING')
    OrderItem.objects.create(
        order=order, product_name=prod.name, sku=prod.sku,
        unit_price=prod.price, quantity=1, subtotal=prod.price,
    )
    OrderValue.objects.create(
        order=order, subtotal=Decimal('2400.00'), tax=Decimal('331.03'),
        shipping_cost=Decimal('0.00'), discount=Decimal('0.00'),
        total=Decimal('2400.00'),
    )
    OrderAddress.objects.create(
        order=order, recipient_name='Test',
        street='Calle 1', city='CDMX', state='CMX', zip_code='06600',
    )
    approved = Payment.objects.create(
        order=order, gateway='MERCADOPAGO',
        preference_id='PREF-HIST-001',
        gateway_payment_id='MP-HIST-001',
        status='APPROVED', amount=Decimal('2400.00'),
    )
    return order, approved


@pytest.fixture
def orden_con_historial(db, user, cat_hist):
    """Orden con un Payment FAILED seguido de uno APPROVED."""

    prod = Product.objects.create(
        name='Elekes Orula', slug='elekes-hist', sku='HIST-002',
        description='',
        price=Decimal('1200.00'), stock=5,
        is_active=True, is_published=True,
    )
    prod.categories.add(cat_hist)
    order = Order.objects.create(user=user, status='PROCESSING')
    OrderItem.objects.create(
        order=order, product_name=prod.name, sku=prod.sku,
        unit_price=prod.price, quantity=1, subtotal=prod.price,
    )
    OrderValue.objects.create(
        order=order, subtotal=Decimal('1200.00'), tax=Decimal('165.52'),
        shipping_cost=Decimal('0.00'), discount=Decimal('0.00'),
        total=Decimal('1200.00'),
    )
    OrderAddress.objects.create(
        order=order, recipient_name='Test',
        street='Av 1', city='CDMX', state='CMX', zip_code='06600',
    )
    failed = Payment.objects.create(
        order=order, gateway='MERCADOPAGO',
        preference_id='PREF-HIST-FAIL',
        status='FAILED', amount=Decimal('1200.00'),
    )
    approved = Payment.objects.create(
        order=order, gateway='PAYPAL',
        preference_id='PP-HIST-001',
        gateway_payment_id='PP-CAP-HIST-001',
        status='APPROVED', amount=Decimal('1200.00'),
    )
    return order, failed, approved


# =============================================================================
# UC-PAY-05 — Estado del pago
# =============================================================================

class TestEstadoPago:

    def test_sin_auth_retorna_401(self, api_client, db):
        res = api_client.get(STATUS_URL('PY-FAKE'))
        assert res.status_code == 401

    def test_estado_pago_aprobado(
        self, auth_client, orden_con_pago, db
    ):
        order, payment = orden_con_pago
        res = auth_client.get(STATUS_URL(order.order_number))
        assert res.status_code == 200
        data = res.json()
        assert data['payment_status'] == 'APPROVED'
        assert data['gateway'] == 'MERCADOPAGO'
        assert data['order_number'] == order.order_number

    def test_orden_sin_pagos_retorna_no_payment(
        self, auth_client, user, cat_hist, db
    ):
        prod = Product.objects.create(
            name='PNoP', slug='pnop', sku='HIST-NP',
            description='',
            price=Decimal('100'), stock=1, is_active=True, is_published=True,
        )
        prod.categories.add(cat_hist)
        order = Order.objects.create(user=user, status='PENDING')
        OrderValue.objects.create(
            order=order, subtotal=Decimal('100'), tax=Decimal('13.79'),
            shipping_cost=Decimal('0'), discount=Decimal('0'), total=Decimal('100'),
        )
        OrderAddress.objects.create(
            order=order, recipient_name='X', street='Y',
            city='Z', state='W', zip_code='00000',
        )
        res = auth_client.get(STATUS_URL(order.order_number))
        assert res.status_code == 200
        assert res.json()['payment_status'] == 'NO_PAYMENT'

    def test_rnf_sec_003_orden_de_otro_usuario_retorna_404(
        self, auth_client, db
    ):
        """RNF-SEC-003: nunca 403, siempre 404 aunque la orden exista."""
        User = get_user_model()
        other = User.objects.create_user(
            email='other_h@test.com', password='pass'
        )
        order = Order.objects.create(user=other, status='PENDING')
        res = auth_client.get(STATUS_URL(order.order_number))
        assert res.status_code == 404
        assert res.json()['codigo_error'] == 'ORDER_NOT_FOUND'

    def test_orden_inexistente_retorna_404(self, auth_client, db):
        res = auth_client.get(STATUS_URL('PY-NO-EXISTE'))
        assert res.status_code == 404


# =============================================================================
# UC-PAY-06 — Historial de pagos
# =============================================================================

class TestHistorialPagos:

    def test_historial_incluye_todos_los_intentos(
        self, auth_client, orden_con_historial, db
    ):
        order, failed, approved = orden_con_historial
        res = auth_client.get(HISTORY_URL(order.order_number))
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 2
        statuses = {p['status'] for p in data}
        assert 'FAILED' in statuses
        assert 'APPROVED' in statuses

    def test_historial_ordenado_por_created_at_desc(
        self, auth_client, orden_con_historial, db
    ):
        order, failed, approved = orden_con_historial
        res = auth_client.get(HISTORY_URL(order.order_number))
        pagos = res.json()
        assert pagos[0]['status'] == 'APPROVED'
        assert pagos[1]['status'] == 'FAILED'

    def test_historial_rnf_sec_003(self, user, auth_client, db):
        """RNF-SEC-003: orden de otro usuario → 404."""
        User = get_user_model()
        other = User.objects.create_user(
            email='o2@test.com', password='pass'
        )
        order = Order.objects.create(user=other, status='PENDING')
        res = auth_client.get(HISTORY_URL(order.order_number))
        assert res.status_code == 404

    def test_historial_orden_sin_pagos_retorna_lista_vacia(
        self, auth_client, user, cat_hist, db
    ):
        order = Order.objects.create(user=user, status='PENDING')
        res = auth_client.get(HISTORY_URL(order.order_number))
        assert res.status_code == 200
        assert res.json() == []


# =============================================================================
# UC-PAY-08 — Elegibilidad de reintento
# =============================================================================

class TestElegibilidadReintento:

    def test_orden_con_pago_fallido_es_reintentable(
        self, auth_client, user, cat_hist, db
    ):

        gw = PaymentGateway(name='MP', gateway='MERCADOPAGO', is_active=True)
        gw.set_credentials({'access_token': 'T', 'client_secret': 'S'})
        gw.save()

        order = Order.objects.create(user=user, status='PENDING')
        Payment.objects.create(
            order=order, gateway='MERCADOPAGO',
            status='FAILED', amount=Decimal('500'),
        )
        res = auth_client.get(RETRY_URL(order.order_number))
        assert res.status_code == 200
        data = res.json()
        assert data['eligible'] is True
        assert 'MERCADOPAGO' in data['available_gateways']

    def test_orden_delivered_no_es_reintentable(
        self, auth_client, orden_con_pago, db
    ):
        order, _ = orden_con_pago
        res = auth_client.get(RETRY_URL(order.order_number))
        assert res.status_code == 200
        data = res.json()
        assert data['eligible'] is False

    def test_orden_inexistente_retorna_404(self, auth_client, db):
        res = auth_client.get(RETRY_URL('PY-GHOST'))
        assert res.status_code == 404
