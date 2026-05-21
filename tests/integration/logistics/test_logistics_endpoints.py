"""
Integration tests — P-13 logistics endpoints (UC-LOG-01..09).

Endpoints under test:
  GET    /api/v1/logistics/
  GET    /api/v1/logistics/couriers/
  POST   /api/v1/logistics/guides/
  PATCH  /api/v1/logistics/guides/<pk>/
  POST   /api/v1/logistics/guides/<pk>/confirm-delivery/

English JSON keys per DEC-DOC-005. Spanish business codes per DEC-DOC-006.
"""
from decimal import Decimal
from apps.catalogue.models import Category, Product
from apps.orders.models import Order, OrderAddress, OrderItem, OrderValue
from apps.logistics.models import Courier, ShipmentGuide
from django.utils import timezone

import pytest

pytestmark = pytest.mark.integration


PANEL_URL    = '/api/v1/logistics/'
COURIER_URL  = '/api/v1/logistics/couriers/'
GUIDES_URL   = '/api/v1/logistics/guides/'
CONFIRM_URL  = lambda pk: f'/api/v1/logistics/guides/{pk}/confirm-delivery/'
GUIDE_URL    = lambda pk: f'/api/v1/logistics/guides/{pk}/'


@pytest.fixture
def cat_log(db):
    return Category.objects.create(name='Logistics', slug='log-cat', is_active=True)


@pytest.fixture
def prod_log(db, cat_log):
    return Product.objects.create(
        name='Pulsera Yoruba', slug='pulsera-yoruba', sku='LOG-PY-001',
        category=cat_log, price=Decimal('500.00'), stock=10,
        is_active=True, is_published=True,
    )


@pytest.fixture
def order_log(db, user, prod_log):
    o = Order.objects.create(user=user, status=Order.STATUS_IN_PREPARATION)
    OrderItem.objects.create(
        order=o, product=prod_log, product_name=prod_log.name,
        sku=prod_log.sku, unit_price=prod_log.price,
        quantity=1, subtotal=prod_log.price,
    )
    OrderValue.objects.create(
        order=o, subtotal=Decimal('500'), tax=Decimal('0'),
        shipping_cost=Decimal('80'), total=Decimal('580'),
    )
    OrderAddress.objects.create(
        order=o, recipient_name='Test', street='Av', city='CDMX',
        state='CDMX', zip_code='06600',
    )
    return o


@pytest.fixture
def courier_log(db):
    return Courier.objects.create(name='Estafeta', code='ESF')


class TestCouriersList:

    def test_admin_lista_couriers(self, admin_client, courier_log, db):
        r = admin_client.get(COURIER_URL)
        assert r.status_code == 200
        codes = {c['code'] for c in r.json()}
        assert 'ESF' in codes

    def test_anonimo_recibe_401(self, api_client, db):
        r = api_client.get(COURIER_URL)
        assert r.status_code == 401

    def test_comprador_recibe_403(self, auth_client, db):
        r = auth_client.get(COURIER_URL)
        assert r.status_code == 403


class TestLogisticsPanel:

    def test_panel_separa_groups_a_y_b(
        self, admin_client, order_log, courier_log, prod_log, user, db
    ):
        # group A: order_log has no guide.
        # group B: create another order + guide.
        o2 = Order.objects.create(user=user, status='SHIPPED')
        OrderItem.objects.create(
            order=o2, product=prod_log, product_name=prod_log.name,
            sku='X', unit_price=Decimal('100'), quantity=1,
            subtotal=Decimal('100'),
        )
        OrderValue.objects.create(order=o2, subtotal=Decimal('100'),
            tax=Decimal('0'), shipping_cost=Decimal('0'),
            total=Decimal('100'))
        OrderAddress.objects.create(order=o2, recipient_name='X',
            street='Y', city='Z', state='Z', zip_code='00000')
        ShipmentGuide.objects.create(
            order=o2, courier=courier_log, tracking_number='TRK-001',
        )
        r = admin_client.get(PANEL_URL)
        assert r.status_code == 200
        data = r.json()
        assert data['group_a_count'] >= 1
        assert data['group_b_count'] >= 1
        nums = {row['order_number'] for row in data['pending_pickup']}
        assert order_log.order_number in nums
        guides = {g['tracking_number'] for g in data['in_transit']}
        assert 'TRK-001' in guides

    def test_panel_courier_id_filter(
        self, admin_client, order_log, courier_log, prod_log, user, db
    ):
        c2 = Courier.objects.create(name='DHL', code='DHL')
        ShipmentGuide.objects.create(
            order=order_log, courier=c2, tracking_number='OTHER-001',
        )
        r = admin_client.get(PANEL_URL + f'?courier_id={courier_log.id}')
        assert r.status_code == 200
        tracking_nums = {g['tracking_number'] for g in r.json()['in_transit']}
        assert 'OTHER-001' not in tracking_nums

    def test_panel_invalid_courier_id_loud_error(self, admin_client, db):
        r = admin_client.get(PANEL_URL + '?courier_id=abc')
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'COURIER_ID_INVALID'


class TestCreateShipmentGuide:

    def test_admin_crea_guia(self, admin_client, order_log, courier_log, db):
        payload = {
            'order_id': order_log.id,
            'courier_id': courier_log.id,
            'tracking_number': 'TRK-NEW-001',
        }
        r = admin_client.post(GUIDES_URL, payload, format='json')
        assert r.status_code == 201
        data = r.json()
        assert data['tracking_number'] == 'TRK-NEW-001'
        assert data['status'] == 'CREATED'

    def test_tracking_duplicado_emite_codigo_error_loud(
        self, admin_client, order_log, courier_log, db
    ):
        ShipmentGuide.objects.create(
            order=order_log, courier=courier_log, tracking_number='DUPE',
        )
        r = admin_client.post(GUIDES_URL, {
            'order_id': order_log.id,
            'courier_id': courier_log.id,
            'tracking_number': 'DUPE',
        }, format='json')
        assert r.status_code == 400
        assert 'TRACKING_DUPLICATE' in str(r.json())


class TestUpdateGuideStatus:

    def test_admin_actualiza_status(
        self, admin_client, order_log, courier_log, db,
    ):
        g = ShipmentGuide.objects.create(
            order=order_log, courier=courier_log, tracking_number='UPD-1',
        )
        r = admin_client.patch(GUIDE_URL(g.id), {
            'status': 'IN_TRANSIT',
            'description': 'En camino',
        }, format='json')
        assert r.status_code == 200
        assert r.json()['status'] == 'IN_TRANSIT'
        g.refresh_from_db()
        assert g.events.count() == 1

    def test_status_invalido_emite_codigo_error_loud(
        self, admin_client, order_log, courier_log, db,
    ):
        g = ShipmentGuide.objects.create(
            order=order_log, courier=courier_log, tracking_number='UPD-2',
        )
        r = admin_client.patch(GUIDE_URL(g.id), {'status': 'X'}, format='json')
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'STATUS_INVALID'


class TestConfirmDelivery:
    """UC-LOG-05 — idempotent."""

    def test_confirmacion_primera_vez_marca_delivered(
        self, admin_client, order_log, courier_log, db,
    ):
        g = ShipmentGuide.objects.create(
            order=order_log, courier=courier_log, tracking_number='DEL-1',
            status=ShipmentGuide.STATUS_IN_TRANSIT,
        )
        r = admin_client.post(CONFIRM_URL(g.id), {}, format='json')
        assert r.status_code == 200
        data = r.json()
        assert data['status'] == 'DELIVERED'
        assert data['already_delivered'] is False
        order_log.refresh_from_db()
        assert order_log.status == 'DELIVERED'

    def test_confirmacion_idempotente(
        self, admin_client, order_log, courier_log, db,
    ):
        g = ShipmentGuide.objects.create(
            order=order_log, courier=courier_log, tracking_number='DEL-2',
            status=ShipmentGuide.STATUS_DELIVERED,
            delivered_at=timezone.now(),
        )
        r = admin_client.post(CONFIRM_URL(g.id), {}, format='json')
        assert r.status_code == 200
        assert r.json()['already_delivered'] is True

    def test_guia_cancelada_no_se_puede_confirmar(
        self, admin_client, order_log, courier_log, db,
    ):
        g = ShipmentGuide.objects.create(
            order=order_log, courier=courier_log, tracking_number='DEL-3',
            status=ShipmentGuide.STATUS_CANCELLED,
        )
        r = admin_client.post(CONFIRM_URL(g.id), {}, format='json')
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'SHIPMENT_GUIDE_CANCELLED'

    def test_guia_no_encontrada_loud_404(self, admin_client, db):
        r = admin_client.post(CONFIRM_URL(999999), {}, format='json')
        assert r.status_code == 404
        assert r.json()['codigo_error'] == 'SHIPMENT_GUIDE_NOT_FOUND'
