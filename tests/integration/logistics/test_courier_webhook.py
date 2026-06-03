"""
Integration tests — LOG-04 courier webhook (US-1.2 / DEC-LOOP-05).

Endpoint under test:
  POST /api/v1/logistics/webhook/courier/

Contract:
  - AllowAny: no JWT. Authenticated by HMAC-SHA256 signature with a
    shared per-courier secret (same philosophy as the payments webhook).
  - Effect: verify signature -> find guide by (courier_code, tracking_number)
    -> map courier status to internal ShipmentGuide.STATUS_* -> update
    guide.status + create an append-only ShipmentEvent (recorded_by=None).
  - Idempotent: replaying the same event (same status + occurred_at for the
    same guide) does not duplicate the ShipmentEvent and returns 200.

English JSON keys per DEC-DOC-005. Spanish business codes per DEC-DOC-006.
"""
import hashlib
import hmac
import json
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.catalogue.models import Category, Product
from apps.logistics.models import Courier, ShipmentEvent, ShipmentGuide
from apps.orders.models import Order, OrderAddress, OrderItem, OrderValue

pytestmark = pytest.mark.integration


WEBHOOK_URL = '/api/v1/logistics/webhook/courier/'
WEBHOOK_SECRET = 'super-secret-courier-key'


def _sign(secret: str, raw_body: bytes) -> str:
    return hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()


def _post(client, payload: dict, secret=WEBHOOK_SECRET, signature=None):
    """POST raw JSON with an HMAC signature header.

    Passing signature=... overrides the computed one (to test bad/missing
    signatures). Passing secret=None sends no signature header at all.
    """
    raw_body = json.dumps(payload).encode()
    headers = {'content_type': 'application/json'}
    if signature is not None:
        headers['HTTP_X_SIGNATURE'] = signature
    elif secret is not None:
        headers['HTTP_X_SIGNATURE'] = _sign(secret, raw_body)
    return client.post(WEBHOOK_URL, data=raw_body, **headers)


@pytest.fixture
def cat_log(db):
    return Category.objects.create(name='Logistics', slug='log-cat', is_active=True)


@pytest.fixture
def prod_log(db, cat_log):
    p = Product.objects.create(
        name='Pulsera Yoruba', slug='pulsera-yoruba', sku='LOG-PY-001',
        price=Decimal('500.00'), stock=10, is_active=True, is_published=True,
    )
    p.categories.add(cat_log)
    return p


@pytest.fixture
def order_log(db, user, prod_log):
    o = Order.objects.create(user=user, status=Order.STATUS_SHIPPED)
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
    c = Courier.objects.create(name='Estafeta', code='ESF')
    c.set_webhook_secret(WEBHOOK_SECRET)
    c.save()
    return c


@pytest.fixture
def guide_log(db, order_log, courier_log):
    return ShipmentGuide.objects.create(
        order=order_log, courier=courier_log,
        tracking_number='TRK-0001', status=ShipmentGuide.STATUS_PICKED_UP,
    )


class TestCourierWebhookSignature:

    def test_firma_valida_actualiza_guia_y_crea_evento(self, api_client, guide_log, db):
        occurred = timezone.now().replace(microsecond=0).isoformat()
        payload = {
            'courier_code': 'ESF',
            'tracking_number': 'TRK-0001',
            'status': 'in_transit',
            'occurred_at': occurred,
            'note': 'En ruta',
        }
        r = _post(api_client, payload)
        assert r.status_code == 200, r.content

        guide_log.refresh_from_db()
        assert guide_log.status == ShipmentGuide.STATUS_IN_TRANSIT
        ev = guide_log.events.first()
        assert ev is not None
        assert ev.status == ShipmentGuide.STATUS_IN_TRANSIT
        assert ev.recorded_by is None

    def test_firma_invalida_rechaza_sin_cambios(self, api_client, guide_log, db):
        payload = {
            'courier_code': 'ESF', 'tracking_number': 'TRK-0001',
            'status': 'in_transit', 'occurred_at': timezone.now().isoformat(),
        }
        r = _post(api_client, payload, signature='deadbeef')
        assert r.status_code == 401, r.content
        guide_log.refresh_from_db()
        assert guide_log.status == ShipmentGuide.STATUS_PICKED_UP
        assert guide_log.events.count() == 0

    def test_firma_ausente_rechaza(self, api_client, guide_log, db):
        payload = {
            'courier_code': 'ESF', 'tracking_number': 'TRK-0001',
            'status': 'in_transit', 'occurred_at': timezone.now().isoformat(),
        }
        r = _post(api_client, payload, secret=None)
        assert r.status_code == 401, r.content
        guide_log.refresh_from_db()
        assert guide_log.status == ShipmentGuide.STATUS_PICKED_UP


class TestCourierWebhookLookup:

    def test_courier_desconocido_404(self, api_client, guide_log, db):
        payload = {
            'courier_code': 'NOPE', 'tracking_number': 'TRK-0001',
            'status': 'in_transit', 'occurred_at': timezone.now().isoformat(),
        }
        # Sign with the real courier secret so we exercise the lookup, not auth.
        # But the unknown courier has no secret; signature can't be verified ->
        # we still must reject before lookup. Use a valid courier_code mismatch:
        # send a known guide's tracking but a courier_code that does not exist.
        r = _post(api_client, payload)
        # Unknown courier -> signature cannot be verified -> 401 (fail closed).
        assert r.status_code in (401, 404), r.content
        guide_log.refresh_from_db()
        assert guide_log.status == ShipmentGuide.STATUS_PICKED_UP

    def test_tracking_desconocido_404(self, api_client, courier_log, guide_log, db):
        payload = {
            'courier_code': 'ESF', 'tracking_number': 'TRK-MISSING',
            'status': 'in_transit', 'occurred_at': timezone.now().isoformat(),
        }
        r = _post(api_client, payload)
        assert r.status_code == 404, r.content
        body = r.json()
        assert 'codigo_error' in body


class TestCourierWebhookPayload:

    def test_status_desconocido_400(self, api_client, guide_log, db):
        payload = {
            'courier_code': 'ESF', 'tracking_number': 'TRK-0001',
            'status': 'teleported', 'occurred_at': timezone.now().isoformat(),
        }
        r = _post(api_client, payload)
        assert r.status_code == 400, r.content
        body = r.json()
        assert 'codigo_error' in body
        guide_log.refresh_from_db()
        assert guide_log.status == ShipmentGuide.STATUS_PICKED_UP

    def test_campos_faltantes_400(self, api_client, courier_log, guide_log, db):
        payload = {'courier_code': 'ESF', 'status': 'in_transit'}
        r = _post(api_client, payload)
        assert r.status_code == 400, r.content
        body = r.json()
        assert 'codigo_error' in body


class TestCourierWebhookIdempotency:

    def test_reenvio_idempotente_no_duplica_evento(self, api_client, guide_log, db):
        occurred = timezone.now().replace(microsecond=0).isoformat()
        payload = {
            'courier_code': 'ESF', 'tracking_number': 'TRK-0001',
            'status': 'in_transit', 'occurred_at': occurred,
        }
        r1 = _post(api_client, payload)
        assert r1.status_code == 200, r1.content
        count_after_first = ShipmentEvent.objects.filter(guide=guide_log).count()
        assert count_after_first == 1

        # Replay the exact same event.
        r2 = _post(api_client, payload)
        assert r2.status_code == 200, r2.content
        count_after_second = ShipmentEvent.objects.filter(guide=guide_log).count()
        assert count_after_second == 1, 'replay must not duplicate the event'


class TestCourierWebhookSecretUnset:

    def test_secret_no_configurado_rechazo_seguro(self, api_client, order_log, db):
        courier = Courier.objects.create(name='SinSecreto', code='NOSEC')
        guide = ShipmentGuide.objects.create(
            order=order_log, courier=courier,
            tracking_number='TRK-NOSEC', status=ShipmentGuide.STATUS_PICKED_UP,
        )
        payload = {
            'courier_code': 'NOSEC', 'tracking_number': 'TRK-NOSEC',
            'status': 'in_transit', 'occurred_at': timezone.now().isoformat(),
        }
        # Any signature; the courier has no secret -> fail closed (401).
        r = _post(api_client, payload, signature='whatever')
        assert r.status_code == 401, r.content
        guide.refresh_from_db()
        assert guide.status == ShipmentGuide.STATUS_PICKED_UP
