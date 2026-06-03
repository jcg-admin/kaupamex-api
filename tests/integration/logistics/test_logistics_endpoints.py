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
    _p = Product.objects.create(
        name='Pulsera Yoruba', slug='pulsera-yoruba', sku='LOG-PY-001',
        price=Decimal('500.00'), stock=10,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat_log)
    return _p


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
            'status': 'PICKED_UP',
            'description': 'Recolectado',
        }, format='json')
        assert r.status_code == 200
        assert r.json()['status'] == 'PICKED_UP'
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


class TestOrderStatusShippedAfterGuide:
    """UC-LOG-01 POST-01: order.status → SHIPPED when guide created."""

    def test_order_pasa_a_shipped_al_crear_guia(
        self, admin_client, order_log, courier_log, db,
    ):
        assert order_log.status == Order.STATUS_IN_PREPARATION
        r = admin_client.post(GUIDES_URL, {
            'order_id': order_log.id,
            'courier_id': courier_log.id,
            'tracking_number': 'TRK-SHP-001',
        }, format='json')
        assert r.status_code == 201
        order_log.refresh_from_db()
        assert order_log.status == Order.STATUS_SHIPPED


class TestCancelGuide:
    """UC-LOG-01 Alt-C: cancel shipment guide."""

    def test_admin_cancela_guia_creada(
        self, admin_client, order_log, courier_log, db,
    ):
        g = ShipmentGuide.objects.create(
            order=order_log, courier=courier_log, tracking_number='CAN-001',
        )
        r = admin_client.post(f'/api/v1/logistics/guides/{g.id}/cancel/',
                              {'reason': 'Cliente cancelo'}, format='json')
        assert r.status_code == 200
        assert r.json()['cancelled'] is True
        assert ShipmentGuide.all_objects.filter(id=g.id, is_deleted=True).exists()

    def test_no_cancela_guia_entregada(
        self, admin_client, order_log, courier_log, db,
    ):
        g = ShipmentGuide.objects.create(
            order=order_log, courier=courier_log, tracking_number='CAN-002',
            status=ShipmentGuide.STATUS_DELIVERED,
        )
        r = admin_client.post(f'/api/v1/logistics/guides/{g.id}/cancel/', {}, format='json')
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'SHIPMENT_GUIDE_DELIVERED'

    def test_no_cancela_guia_ya_cancelada(
        self, admin_client, order_log, courier_log, db,
    ):
        g = ShipmentGuide.objects.create(
            order=order_log, courier=courier_log, tracking_number='CAN-003',
            status=ShipmentGuide.STATUS_CANCELLED,
        )
        r = admin_client.post(f'/api/v1/logistics/guides/{g.id}/cancel/', {}, format='json')
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'SHIPMENT_GUIDE_ALREADY_CANCELLED'

    def test_cancela_guia_404_loud(self, admin_client, db):
        r = admin_client.post('/api/v1/logistics/guides/999999/cancel/', {}, format='json')
        assert r.status_code == 404
        assert r.json()['codigo_error'] == 'SHIPMENT_GUIDE_NOT_FOUND'


class TestCourierCRUD:
    """UC-LOG-06 CRUD couriers."""

    def test_admin_crea_courier(self, admin_client, db):
        r = admin_client.post('/api/v1/logistics/couriers/', {
            'name': 'FedEx', 'code': 'FDX',
            'tracking_url_template': 'https://fedex.com/track?trk={tracking_number}',
            'is_active': True,
        }, format='json')
        assert r.status_code == 201
        assert r.json()['code'] == 'FDX'

    def test_admin_actualiza_courier(self, admin_client, courier_log, db):
        r = admin_client.patch(
            f'/api/v1/logistics/couriers/{courier_log.id}/',
            {'is_active': False},
            format='json',
        )
        assert r.status_code == 200
        assert r.json()['is_active'] is False

    def test_admin_desactiva_courier(self, admin_client, courier_log, db):
        r = admin_client.delete(f'/api/v1/logistics/couriers/{courier_log.id}/')
        assert r.status_code == 200
        assert r.json()['deactivated'] is True
        courier_log.refresh_from_db()
        assert courier_log.is_active is False

    def test_courier_no_encontrado_loud_404(self, admin_client, db):
        r = admin_client.patch('/api/v1/logistics/couriers/999999/', {'name': 'X'}, format='json')
        assert r.status_code == 404
        assert r.json()['codigo_error'] == 'COURIER_NOT_FOUND'


class TestUpdateTrackingNumber:
    """UC-LOG-02 — registrar/actualizar el número de rastreo tras crear la guía."""

    def test_admin_actualiza_tracking_number(
        self, admin_client, order_log, courier_log, db,
    ):
        g = ShipmentGuide.objects.create(
            order=order_log, courier=courier_log, tracking_number='TRK-OLD',
        )
        r = admin_client.patch(GUIDE_URL(g.id), {
            'tracking_number': 'TRK-NEW',
            'tracking_url': 'https://estafeta.com/track?n=TRK-NEW',
        }, format='json')
        assert r.status_code == 200
        data = r.json()
        assert data['tracking_number'] == 'TRK-NEW'
        assert data['tracking_url'] == 'https://estafeta.com/track?n=TRK-NEW'
        g.refresh_from_db()
        assert g.tracking_number == 'TRK-NEW'
        # Alt C: el historial conserva el numero anterior vía ShipmentEvent.
        assert g.events.filter(description__contains="'TRK-OLD'").exists()

    def test_actualizar_tracking_requiere_admin_403(
        self, auth_client, order_log, courier_log, db,
    ):
        g = ShipmentGuide.objects.create(
            order=order_log, courier=courier_log, tracking_number='TRK-AUTH',
        )
        r = auth_client.patch(GUIDE_URL(g.id), {'tracking_number': 'X'}, format='json')
        assert r.status_code == 403

    def test_tracking_number_vacio_emite_codigo_error(
        self, admin_client, order_log, courier_log, db,
    ):
        g = ShipmentGuide.objects.create(
            order=order_log, courier=courier_log, tracking_number='TRK-VAL',
        )
        r = admin_client.patch(GUIDE_URL(g.id), {'tracking_number': '   '}, format='json')
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'TRACKING_REQUIRED'

    def test_tracking_duplicado_advierte_pero_permite(
        self, admin_client, order_log, courier_log, prod_log, user, db,
    ):
        # EX-02: otra guía activa (de OTRO courier) ya tiene el número → warning
        # pero permite. Nota: la unicidad es per-courier (unique_tracking_per_courier),
        # así que el duplicado reachable es cross-courier.
        c2 = Courier.objects.create(name='DHL-dup', code='DHLD')
        o2 = Order.objects.create(user=user, status=Order.STATUS_IN_PREPARATION)
        ShipmentGuide.objects.create(
            order=o2, courier=c2, tracking_number='DUP-TRK',
        )
        g = ShipmentGuide.objects.create(
            order=order_log, courier=courier_log, tracking_number='TRK-ORIG',
        )
        r = admin_client.patch(GUIDE_URL(g.id), {'tracking_number': 'DUP-TRK'}, format='json')
        assert r.status_code == 200
        assert 'warning' in r.json()
        g.refresh_from_db()
        assert g.tracking_number == 'DUP-TRK'

    def test_actualizar_status_sigue_funcionando(
        self, admin_client, order_log, courier_log, db,
    ):
        # Regresión: el PATCH de status no se rompe con la rama de tracking.
        g = ShipmentGuide.objects.create(
            order=order_log, courier=courier_log, tracking_number='TRK-STS',
        )
        r = admin_client.patch(GUIDE_URL(g.id), {'status': 'PICKED_UP'}, format='json')
        assert r.status_code == 200
        assert r.json()['status'] == 'PICKED_UP'


class TestBuyerGuide:
    """UC-LOG-03: buyer sees shipment guide for own order."""

    def test_comprador_ve_su_guia(
        self, auth_client, order_log, courier_log, db,
    ):
        ShipmentGuide.objects.create(
            order=order_log, courier=courier_log, tracking_number='BYR-001',
        )
        r = auth_client.get(f'/api/v1/logistics/buyer/order/{order_log.id}/guide/')
        assert r.status_code == 200
        data = r.json()
        assert data['tracking_number'] == 'BYR-001'
        assert 'courier_name' in data

    def test_comprador_no_ve_orden_ajena(self, admin_client, order_log, courier_log, db):
        ShipmentGuide.objects.create(
            order=order_log, courier=courier_log, tracking_number='BYR-002',
        )
        # admin_client is authenticated as a different user (admin, not order_log.user)
        r = admin_client.get(f'/api/v1/logistics/buyer/order/{order_log.id}/guide/')
        assert r.status_code == 404
        assert r.json()['codigo_error'] == 'ORDER_NOT_FOUND'

    def test_comprador_sin_guia_recibe_404(self, auth_client, order_log, db):
        r = auth_client.get(f'/api/v1/logistics/buyer/order/{order_log.id}/guide/')
        assert r.status_code == 404
        assert r.json()['codigo_error'] == 'SHIPMENT_GUIDE_NOT_FOUND'
