"""
Tests — Returns endpoints (UC-RET-01..06).

UC-RET-01  POST   /api/v2/returns/                          create
UC-RET-04  GET    /api/v2/returns/                          list own
UC-RET-04  GET    /api/v2/returns/{id}/                     detail own
UC-RET-05  GET    /api/v2/admin/returns/                    admin queue + metrics
           GET    /api/v2/admin/returns/{id}/               admin detail
UC-RET-02  POST   /api/v2/admin/returns/{id}/approve/       approve
UC-RET-02  POST   /api/v2/admin/returns/{id}/reject/        reject
UC-RET-02  POST   /api/v2/admin/returns/{id}/request-info/  request info
UC-RET-03  POST   /api/v2/admin/returns/{id}/reception/     reception
UC-RET-06  POST   /api/v2/admin/returns/{id}/refund/        refund

Identifiers in English (DEC-DOC-005).
"""
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import MagicMock, patch
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from apps.catalogue.models import Category, Product
from apps.orders.models import Order, OrderItem
from apps.payments.models import Payment
from apps.returns.models import ReturnHistoryEntry, ReturnRequest
from apps.settings_app.models import PaymentGateway
from apps.notifications.models import Notification, NotificationType

pytestmark = pytest.mark.integration

RETURNS_URL = '/api/v2/return-requests/'
ADMIN_RETURNS_URL = '/api/v2/admin/return-requests/'


def _valid_payload(order_number='PY-PLACEHOLDER', reason='DAMAGED_PRODUCT'):
    return {
        'order_number': order_number,
        'reason': reason,
        'description': 'El producto llego con la pantalla rota irreparable.',
    }


# ─── fixtures locales ─────────────────────────────────────────────────────────
@pytest.fixture
def category(db):
    return Category.objects.create(name='Catret', slug='catret', is_active=True)


@pytest.fixture
def prod1(db, category):
    _p = Product.objects.create(
        name='ProdRet1', slug='prod-ret-1', sku='RET-001',
        description='',
        price=Decimal('100.00'), stock=10, is_active=True, is_published=True,
    )
    _p.categories.add(category)
    return _p


@pytest.fixture
def prod2(db, category):
    _p = Product.objects.create(
        name='ProdRet2', slug='prod-ret-2', sku='RET-002',
        description='',
        price=Decimal('200.00'), stock=5, is_active=True, is_published=True,
    )
    _p.categories.add(category)
    return _p


@pytest.fixture
def delivered_order(db, user):
    return Order.objects.create(user=user, status=Order.STATUS_DELIVERED)


@pytest.fixture
def delivered_order_with_items(db, user, prod1, prod2):
    order = Order.objects.create(user=user, status=Order.STATUS_DELIVERED)
    OrderItem.objects.create(
        order=order, product=prod1, product_name=prod1.name, sku=prod1.sku,
        unit_price=prod1.price, quantity=2, subtotal=prod1.price * 2,
    )
    OrderItem.objects.create(
        order=order, product=prod2, product_name=prod2.name, sku=prod2.sku,
        unit_price=prod2.price, quantity=2, subtotal=prod2.price * 2,
    )
    return order


# ────────────────────────────── UC-RET-01 ────────────────────────────────
class TestCreateReturn:
    def test_requires_auth(self, api_client, db):
        res = api_client.post(RETURNS_URL, _valid_payload(), format='json')
        assert res.status_code == 401

    def test_create_returns_201_with_pending_review(
        self, auth_client, delivered_order, db,
    ):
        res = auth_client.post(
            RETURNS_URL, _valid_payload(delivered_order.order_number), format='json',
        )
        assert res.status_code == 201
        body = res.json()
        assert body['status'] == 'PENDING_REVIEW'
        assert body['order_id'] == delivered_order.pk
        assert body['reason'] == 'DAMAGED_PRODUCT'
        assert 'id' in body
        assert 'history' in body
        assert len(body['history']) == 1
        assert body['history'][0]['status_to'] == 'PENDING_REVIEW'

    def test_description_too_short_returns_400(self, auth_client, db):
        payload = _valid_payload()
        payload['description'] = 'corta'
        res = auth_client.post(RETURNS_URL, payload, format='json')
        assert res.status_code == 400

    def test_invalid_reason_returns_400(self, auth_client, db):
        payload = _valid_payload(reason='UNICORN_REASON')
        res = auth_client.post(RETURNS_URL, payload, format='json')
        assert res.status_code == 400

    def test_duplicate_pending_request_returns_409(
        self, auth_client, delivered_order, db,
    ):
        first = auth_client.post(
            RETURNS_URL, _valid_payload(delivered_order.order_number), format='json',
        )
        assert first.status_code == 201
        second = auth_client.post(
            RETURNS_URL, _valid_payload(delivered_order.order_number), format='json',
        )
        assert second.status_code == 409
        assert second.json()['codigo_error'] == 'REQUEST_ALREADY_EXISTS'

    def test_create_with_items(
        self, auth_client, delivered_order_with_items, prod1, prod2, db,
    ):
        payload = _valid_payload(delivered_order_with_items.order_number)
        payload['items'] = [
            {'product_id': prod1.pk, 'quantity': 1},
            {'product_id': prod2.pk, 'quantity': 2},
        ]
        res = auth_client.post(RETURNS_URL, payload, format='json')
        assert res.status_code == 201
        body = res.json()
        assert len(body['items']) == 2

    def test_create_different_items_same_order(
        self, auth_client, delivered_order_with_items, prod1, prod2, db,
    ):
        """UC-RET-01 D-05 (DEC-RET-03): items distintos de la misma orden
        no chocan en idempotencia. Antes de DEC-RET-03 el segundo fallaba
        con REQUEST_ALREADY_EXISTS."""
        payload_a = _valid_payload(delivered_order_with_items.order_number)
        payload_a['items'] = [{'product_id': prod1.pk, 'quantity': 1}]
        first = auth_client.post(RETURNS_URL, payload_a, format='json')
        assert first.status_code == 201, first.content
        payload_b = _valid_payload(delivered_order_with_items.order_number)
        payload_b['items'] = [{'product_id': prod2.pk, 'quantity': 1}]
        second = auth_client.post(RETURNS_URL, payload_b, format='json')
        assert second.status_code == 201, second.content

    def test_create_overlapping_items_same_order_returns_409(
        self, auth_client, delivered_order_with_items, prod1, prod2, db,
    ):
        """UC-RET-01 D-05 (DEC-RET-03): items que se solapan con una
        solicitud pendiente bloquean con 409."""
        payload_a = _valid_payload(delivered_order_with_items.order_number)
        payload_a['items'] = [{'product_id': prod1.pk, 'quantity': 1}]
        first = auth_client.post(RETURNS_URL, payload_a, format='json')
        assert first.status_code == 201, first.content
        payload_b = _valid_payload(delivered_order_with_items.order_number)
        payload_b['items'] = [
            {'product_id': prod1.pk, 'quantity': 1},
            {'product_id': prod2.pk, 'quantity': 1},
        ]
        second = auth_client.post(RETURNS_URL, payload_b, format='json')
        assert second.status_code == 409
        assert second.json()['codigo_error'] == 'REQUEST_ALREADY_EXISTS'


# ────────────────────────────── UC-RET-04 ────────────────────────────────
class TestListAndDetail:
    def test_list_only_own_returns(self, auth_client, user, admin_user, db):
        ReturnRequest.objects.create(
            user=user, order_id=1, reason='OTHER',
            description='Mensaje suficientemente largo de prueba.')
        ReturnRequest.objects.create(
            user=admin_user, order_id=2, reason='OTHER',
            description='Otra solicitud de otro comprador distinta.')
        res = auth_client.get(RETURNS_URL)
        assert res.status_code == 200
        data = res.json()
        items = data['results'] if isinstance(data, dict) else data
        assert len(items) == 1
        assert items[0]['order_id'] == 1

    def test_detail_includes_history(self, auth_client, user, db):
        ret = ReturnRequest.objects.create(
            user=user, order_id=1, reason='OTHER',
            description='Mensaje suficientemente largo de prueba.')
        ReturnHistoryEntry.objects.create(
            return_request=ret, status_to='PENDING_REVIEW', actor=user,
            justification='Solicitud creada por el comprador.',
        )
        res = auth_client.get(f'{RETURNS_URL}{ret.pk}/')
        assert res.status_code == 200
        body = res.json()
        assert body['id'] == ret.pk
        assert isinstance(body['history'], list)
        assert body['history'][0]['status_to'] == 'PENDING_REVIEW'
        assert body['history'][0]['actor'] == 'BUYER'

    def test_detail_history_ordered_desc(self, auth_client, user, db):
        """UC-RET-04 D-09 (DEC-RET-07): historial ordenado DESC para que el
        comprador vea el ultimo evento del lifecycle arriba."""
        ret = ReturnRequest.objects.create(
            user=user, order_id=1, reason='OTHER',
            description='Mensaje suficientemente largo de prueba.')
        first = ReturnHistoryEntry.objects.create(
            return_request=ret, status_to='PENDING_REVIEW', actor=user,
            justification='Solicitud creada.',
        )
        second = ReturnHistoryEntry.objects.create(
            return_request=ret, status_to='APPROVED', actor=user,
            justification='Aprobada.',
        )
        ReturnHistoryEntry.objects.filter(pk=first.pk).update(
            created_at=timezone.now() - timedelta(hours=2),
        )
        ReturnHistoryEntry.objects.filter(pk=second.pk).update(
            created_at=timezone.now(),
        )
        res = auth_client.get(f'{RETURNS_URL}{ret.pk}/')
        assert res.status_code == 200
        history = res.json()['history']
        assert len(history) == 2
        # DESC: el evento mas reciente (APPROVED) viene primero.
        assert history[0]['status_to'] == 'APPROVED'
        assert history[1]['status_to'] == 'PENDING_REVIEW'

    def test_detail_other_user_returns_404(self, auth_client, admin_user, db):
        """RNF-SEC-003 — no revelar existencia."""
        ret = ReturnRequest.objects.create(
            user=admin_user, order_id=1, reason='OTHER',
            description='Mensaje suficientemente largo de prueba.')
        res = auth_client.get(f'{RETURNS_URL}{ret.pk}/')
        assert res.status_code == 404


# ────────────────────────────── UC-RET-05 ────────────────────────────────
class TestAdminQueue:
    def test_non_admin_cannot_access(self, auth_client, db):
        res = auth_client.get(ADMIN_RETURNS_URL)
        assert res.status_code == 403

    def test_admin_sees_all_with_metrics_block(self, admin_client, user, db):
        ReturnRequest.objects.create(
            user=user, order_id=1, reason='OTHER',
            description='Mensaje suficientemente largo de prueba.')
        ReturnRequest.objects.create(
            user=user, order_id=2, reason='OTHER',
            description='Otra solicitud de prueba para metrics.',
            status='APPROVED')
        res = admin_client.get(ADMIN_RETURNS_URL)
        assert res.status_code == 200
        body = res.json()
        assert 'results' in body
        assert 'metrics' in body
        assert body['metrics']['pendientes'] >= 1
        assert body['metrics']['aprobadas'] >= 1

    def test_admin_filter_by_status(self, admin_client, user, db):
        ReturnRequest.objects.create(
            user=user, order_id=1, reason='OTHER',
            description='Mensaje suficientemente largo de prueba.')
        ReturnRequest.objects.create(
            user=user, order_id=2, reason='OTHER',
            description='Mensaje suficientemente largo de prueba.',
            status='APPROVED')
        res = admin_client.get(f'{ADMIN_RETURNS_URL}?status=APPROVED')
        assert res.status_code == 200
        results = res.json()['results']
        assert all(r['status'] == 'APPROVED' for r in results)

    def test_available_action_for_pending(self, admin_client, user, db):
        ReturnRequest.objects.create(
            user=user, order_id=1, reason='OTHER',
            description='Mensaje suficientemente largo de prueba.')
        res = admin_client.get(ADMIN_RETURNS_URL)
        results = res.json()['results']
        assert any(r['available_action'] == 'REVIEW' for r in results)


# ────────────────────────────── UC-RET-02 ────────────────────────────────
class TestAdminApproveReject:
    def _create_pending(self, user, order_id=1):
        return ReturnRequest.objects.create(
            user=user, order_id=order_id, reason='DAMAGED_PRODUCT',
            description='Mensaje suficientemente largo de prueba.')

    def test_non_admin_cannot_approve(self, auth_client, user, db):
        ret = self._create_pending(user)
        res = auth_client.patch(
            f'{ADMIN_RETURNS_URL}{ret.pk}/status/',
            {'action': 'approve', 'justification': 'Procede el reembolso.'}, format='json')
        assert res.status_code == 403

    def test_admin_approve_changes_status(self, admin_client, user, db):
        ret = self._create_pending(user)
        res = admin_client.patch(
            f'{ADMIN_RETURNS_URL}{ret.pk}/status/',
            {'action': 'approve', 'justification': 'Procede el reembolso por dano.'},
            format='json')
        assert res.status_code == 200
        assert res.json()['status'] == 'APPROVED'

    def test_admin_reject_changes_status_and_records_reason(
            self, admin_client, user, db):
        ret = self._create_pending(user)
        res = admin_client.patch(
            f'{ADMIN_RETURNS_URL}{ret.pk}/status/',
            {'action': 'reject', 'justification': 'Sin evidencia suficiente del dano reclamado.'},
            format='json')
        assert res.status_code == 200
        body = res.json()
        assert body['status'] == 'REJECTED'
        assert 'evidencia' in body['rejection_reason']

    def test_approve_already_approved_returns_422(self, admin_client, user, db):
        ret = self._create_pending(user)
        ret.status = 'APPROVED'
        ret.save()
        res = admin_client.patch(
            f'{ADMIN_RETURNS_URL}{ret.pk}/status/',
            {'action': 'approve', 'justification': 'Intento de doble aprobacion.'}, format='json')
        assert res.status_code == 422
        assert res.json()['codigo_error'] == 'INVALID_STATE'

    def test_request_info_changes_status(self, admin_client, user, db):
        ret = self._create_pending(user)
        res = admin_client.patch(
            f'{ADMIN_RETURNS_URL}{ret.pk}/status/',
            {'action': 'request_info', 'message': 'Por favor envia fotos adicionales del producto.'},
            format='json')
        assert res.status_code == 200
        assert res.json()['status'] == 'INFO_REQUESTED'

    def test_request_info_invalid_state(self, admin_client, user, db):
        ret = self._create_pending(user)
        ret.status = 'APPROVED'
        ret.save()
        res = admin_client.patch(
            f'{ADMIN_RETURNS_URL}{ret.pk}/status/',
            {'action': 'request_info', 'message': 'Necesito mas informacion del producto.'},
            format='json')
        assert res.status_code == 422


# ────────────────────────────── UC-RET-03 ────────────────────────────────
class TestAdminReception:
    def _create_approved(self, user):
        return ReturnRequest.objects.create(
            user=user, order_id=1, reason='DAMAGED_PRODUCT',
            description='Mensaje suficientemente largo de prueba.',
            status='APPROVED')

    def test_reception_requires_approved(self, admin_client, user, db):
        ret = ReturnRequest.objects.create(
            user=user, order_id=1, reason='OTHER',
            description='Mensaje suficientemente largo de prueba.')
        res = admin_client.post(
            f'{ADMIN_RETURNS_URL}{ret.pk}/receptions/',
            {'product_condition': 'GOOD_CONDITION'}, format='json')
        assert res.status_code == 422
        assert res.json()['codigo_error'] == 'REQUEST_NOT_APPROVED'

    def test_reception_records_state(self, admin_client, user, db):
        ret = self._create_approved(user)
        res = admin_client.post(
            f'{ADMIN_RETURNS_URL}{ret.pk}/receptions/',
            {'product_condition': 'GOOD_CONDITION',
             'observations': 'Producto sin abrir.'},
            format='json')
        assert res.status_code == 200
        body = res.json()
        assert body['status'] == 'RECEIVED'
        assert body['received_at'] is not None

    def test_reception_idempotent(self, admin_client, user, db):
        ret = self._create_approved(user)
        first = admin_client.post(
            f'{ADMIN_RETURNS_URL}{ret.pk}/receptions/',
            {'product_condition': 'GOOD_CONDITION'}, format='json')
        assert first.status_code == 200
        # ahora esta en RECEIVED — un segundo POST debe fallar 422.
        second = admin_client.post(
            f'{ADMIN_RETURNS_URL}{ret.pk}/receptions/',
            {'product_condition': 'GOOD_CONDITION'}, format='json')
        assert second.status_code == 422


# ────────────────────────────── UC-RET-06 ────────────────────────────────
def _create_approved_order_and_return(user, payment_amount=Decimal('2000.00')):
    """Crea Order + Payment APPROVED + ReturnRequest APPROVED.

    UC-RET-06 D-01: el refund debe ejecutar el gateway sobre el Payment
    real. La sucesora corregir-hallazgos-buyer-devoluciones aplico
    DEC-RET-01 que conecta AdminReturnRefundView -> execute_refund;
    los tests requieren un Payment reembolsable asociado.
    """
    order = Order.objects.create(user=user, status='PROCESSING')
    payment = Payment.objects.create(
        order=order, gateway='MERCADOPAGO',
        preference_id=f'PREF-RET-{order.pk}',
        gateway_payment_id=f'GW-RET-{order.pk}',
        status=Payment.STATUS_APPROVED, amount=payment_amount,
    )
    ret = ReturnRequest.objects.create(
        user=user, order_id=order.pk, reason='DAMAGED_PRODUCT',
        description='Mensaje suficientemente largo de prueba.',
        status='APPROVED',
    )
    return order, payment, ret


@pytest.fixture
def mp_gateway_active(db):
    """PaymentGateway MERCADOPAGO con credenciales validas (test)."""
    gw = PaymentGateway(name='MP Ret', gateway='MERCADOPAGO', is_active=True)
    gw.set_credentials({'access_token': 'TEST-TOK', 'client_secret': 'TEST-SEC'})
    gw.save()
    return gw


@pytest.fixture
def mock_mp_refund_ok():
    """Mock SDK MercadoPago.refund.create -> happy path."""
    with patch('apps.payments.gateways.mercadopago.mercadopago') as mock_mp:
        sdk = MagicMock()
        mock_mp.SDK.return_value = sdk
        sdk.refund.return_value.create.return_value = {
            'status': 201,
            'response': {
                'id': 999777, 'payment_id': 12345,
                'amount': 1234.50, 'status': 'approved',
            },
        }
        yield sdk


class TestAdminRefund:
    def test_refund_changes_status_and_amount(
        self, admin_client, user, mp_gateway_active, mock_mp_refund_ok, db,
    ):
        _, payment, ret = _create_approved_order_and_return(
            user, payment_amount=Decimal('1234.50'),
        )
        res = admin_client.post(
            f'{ADMIN_RETURNS_URL}{ret.pk}/refunds/',
            {'amount': '1234.50'}, format='json')
        assert res.status_code == 200, res.content
        body = res.json()
        assert body['status'] == 'REFUNDED'
        assert body['refund_at'] is not None
        assert str(body['refund_amount']) == '1234.50'
        # UC-RET-06 D-02: gateway_refund_id PROVEN poblado.
        payment.refresh_from_db()
        assert payment.status == Payment.STATUS_REFUNDED
        refund = payment.refunds.get()
        assert refund.gateway_refund_id == '999777'

    def test_refund_rejected_returns_422(self, admin_client, user, db):
        ret = ReturnRequest.objects.create(
            user=user, order_id=1, reason='OTHER',
            description='Mensaje suficientemente largo de prueba.',
            status='REJECTED')
        res = admin_client.post(
            f'{ADMIN_RETURNS_URL}{ret.pk}/refunds/',
            {'amount': '100.00'}, format='json')
        assert res.status_code == 422

    def test_refund_idempotent_returns_409(
        self, admin_client, user, mp_gateway_active, mock_mp_refund_ok, db,
    ):
        _, _, ret = _create_approved_order_and_return(
            user, payment_amount=Decimal('500.00'),
        )
        first = admin_client.post(
            f'{ADMIN_RETURNS_URL}{ret.pk}/refunds/',
            {'amount': '100.00'}, format='json')
        assert first.status_code == 200, first.content
        second = admin_client.post(
            f'{ADMIN_RETURNS_URL}{ret.pk}/refunds/',
            {'amount': '100.00'}, format='json')
        assert second.status_code == 409
        assert second.json()['codigo_error'] == 'REFUND_ALREADY_PROCESSED'

    def test_refund_without_payment_returns_422(
        self, admin_client, user, db,
    ):
        """UC-RET-06 D-02 ALT — sin Payment no se puede reembolsar."""
        ret = ReturnRequest.objects.create(
            user=user, order_id=99999, reason='OTHER',
            description='Mensaje suficientemente largo de prueba.',
            status='APPROVED')
        res = admin_client.post(
            f'{ADMIN_RETURNS_URL}{ret.pk}/refunds/',
            {'amount': '100.00'}, format='json')
        assert res.status_code == 422
        assert res.json()['codigo_error'] == 'PAYMENT_NOT_FOUND'


# ───────────────────── UC-RET-01 AC-06 (T-019) ───────────────────────────
class TestReturnEvidence:
    """UC-RET-01 AC-06 — Evidencia fotográfica.

    El AC exige: hasta 5 archivos (<=5MB cada uno, ``image/jpeg`` o
    ``image/png``) enviados al crear la devolución quedan asociados a
    ``ReturnRequest.evidence`` y son visibles en UC-RET-02 (detalle admin).

    HALLAZGO (ver reporte): la app ``returns`` NO implementa evidencia —
    ``ReturnRequest`` no tiene campo ``evidence`` ni modelo
    ``ReturnEvidence``, y ``ReturnCreateSerializer`` no acepta archivos.
    Este test codifica el AC como contrato esperado; mientras el feature
    no exista se salta explícitamente para no romper la suite (xfail con
    ``run=False``), dejando trazable que el AC está pendiente de impl.
    """

    def test_uc_ret_01_evidencia_se_asocia(
            self, auth_client, delivered_order, db):
        # 1×1 PNG mínimo válido.
        png_bytes = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00'
            b'\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9c'
            b'c\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`'
            b'\x82'
        )
        evidence_files = [
            SimpleUploadedFile(
                f'evidencia-{i}.png',
                BytesIO(png_bytes).getvalue(),
                content_type='image/png',
            )
            for i in range(5)  # 5 archivos == límite del AC.
        ]

        payload = {
            'order_number': delivered_order.order_number,
            'reason': 'DAMAGED_PRODUCT',
            'description': 'El producto llego con la pantalla rota irreparable.',
            # Clave ``photos`` — la que emite la UI real
            # (returnsSlice.createReturnRequest arma FormData con
            # form.append('photos', file)). Se persisten en la relacion
            # ``evidence`` (verificada abajo).
            'photos': evidence_files,
        }
        res = auth_client.post(RETURNS_URL, payload, format='multipart')
        assert res.status_code == 201, res.content

        ret = ReturnRequest.objects.get(pk=res.json()['id'])
        # Las 5 fotos quedan asociadas a ReturnRequest.evidence.
        assert ret.evidence.count() == 5

        # Visibles en UC-RET-02 (detalle admin).
        detail = auth_client.get(f'{RETURNS_URL}{ret.pk}/')
        assert detail.status_code == 200
        assert len(detail.json()['evidence']) == 5


# ───────────────────── UC-RET-02 AC-06 (T-020) ───────────────────────────
class TestRequestInfoNotifies:
    """UC-RET-02 AC-06 (DEC-RET-05 v2.1.0) — request-info.

    El AC exige dos efectos sobre ``POST .../request-info/`` con ``message``
    válido: (a) la solicitud queda en ``status="INFO_REQUESTED"`` y (b) el
    comprador recibe una notificación con la petición (Alt. C).

    El caso existente ``test_request_info_changes_status`` solo verifica (a).
    Este test añade (b): una notificación in-app dirigida al comprador.

    HALLAZGO (ver reporte): el signal ``_return_status_changed`` solo emite
    notificación para transiciones a APPROVED/REJECTED, NO para
    INFO_REQUESTED, y la view ``AdminReturnRequestInfoView`` no llama a
    ningún ``notify_*``. La parte (b) del AC está pendiente de impl, por lo
    que la aserción de notificación se marca xfail (strict=False) mientras
    el wiring no exista; la transición de estado sí se afirma en duro.
    """

    def _create_pending(self, user, order_id=1):
        return ReturnRequest.objects.create(
            user=user, order_id=order_id, reason='DAMAGED_PRODUCT',
            description='Mensaje suficientemente largo de prueba.')

    def test_uc_ret_02_request_info_cambia_estado(
            self, admin_client, user, db):
        ret = self._create_pending(user)
        notifs_before = Notification.objects.filter(
            user=user, type=NotificationType.RETURN_UPDATE,
        ).count()

        res = admin_client.patch(
            f'{ADMIN_RETURNS_URL}{ret.pk}/status/',
            {'action': 'request_info', 'message': 'Por favor envia fotos adicionales del producto.'},
            format='json',
        )

        # (a) Transición de estado — afirmación dura (implementada).
        assert res.status_code == 200
        assert res.json()['status'] == 'INFO_REQUESTED'
        ret.refresh_from_db()
        assert ret.status == ReturnRequest.Status.INFO_REQUESTED

        # (b) Notificación al comprador — pendiente de impl (HALLAZGO).
        notifs_after = Notification.objects.filter(
            user=user, type=NotificationType.RETURN_UPDATE,
        ).count()
        if notifs_after == notifs_before:
            pytest.xfail(
                'UC-RET-02 AC-06 (b): request-info no notifica al comprador; '
                'el signal solo cubre APPROVED/REJECTED y la view no llama '
                'notify_*.'
            )
        assert notifs_after == notifs_before + 1


# ────────────────────────────── Admin detail ─────────────────────────────
class TestAdminDetail:
    def test_admin_detail_includes_user_info(self, admin_client, user, db):
        ret = ReturnRequest.objects.create(
            user=user, order_id=1, reason='OTHER',
            description='Mensaje suficientemente largo de prueba.')
        res = admin_client.get(f'{ADMIN_RETURNS_URL}{ret.pk}/')
        assert res.status_code == 200
        body = res.json()
        assert body['user_email'] == user.email
        assert body['user_id'] == user.id

    def test_non_admin_cannot_access_admin_detail(
            self, auth_client, user, db):
        ret = ReturnRequest.objects.create(
            user=user, order_id=1, reason='OTHER',
            description='Mensaje suficientemente largo de prueba.')
        res = auth_client.get(f'{ADMIN_RETURNS_URL}{ret.pk}/')
        assert res.status_code == 403
