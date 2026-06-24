"""
Tests de integracion — API v2 F3: orders, returns, reviews, questions, support

Verifica que los endpoints /api/v2/ para el bloque F3 son funcionales:
  - orders:    cancellations/, shipping-address/, shipping-method/ (Tier A)
  - returns:   return-requests/ y admin status/ (Tier A + B)
  - reviews:   PATCH sin /edit/ y admin status/ (Tier B)
  - questions: admin answers/ y admin status/ (Tier A + B)
  - support:   PATCH tickets/<id>/status/ (Tier B)

F3 no elimina v1; verifica coexistencia (doble-corrida).
"""
import pytest
from apps.support.models import SupportTicket

pytestmark = pytest.mark.integration

# ─── URLs v2 ────────────────────────────────────────────────────────────────
V2_ORDERS_BASE          = '/api/v2/orders/'
V2_RETURNS_BASE         = '/api/v2/return-requests/'
V2_ADMIN_RETURNS_BASE   = '/api/v2/admin/return-requests/'
V2_PRODUCTS_BASE        = '/api/v2/products/'
V2_ADMIN_REVIEWS_BASE   = '/api/v2/admin/reviews/'
V2_ADMIN_QUESTIONS_BASE = '/api/v2/admin/questions/'
V2_SUPPORT_BASE         = '/api/v2/support/tickets/'

# ─── URLs v1 (dual-run) ──────────────────────────────────────────────────────
V1_ORDER_CANCEL_URL         = '/api/v1/orders/{n}/cancel/'
V1_ORDER_ADDRESS_URL        = '/api/v1/orders/{n}/address/'
V1_ORDER_SHIPPING_URL       = '/api/v1/orders/{n}/shipping/'
V1_RETURNS_URL              = '/api/v1/returns/'
V1_ADMIN_RETURN_APPROVE_URL = '/api/v1/admin/returns/{id}/approve/'
V1_REVIEW_EDIT_URL          = '/api/v1/products/{pid}/reviews/{pk}/edit/'
V1_SUPPORT_CLOSE_URL        = '/api/v1/support/tickets/{id}/close/'


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def ticket(db, user):
    return SupportTicket.objects.create(
        user=user,
        subject='Ticket de prueba F3',
        body='Tengo un problema con mi pedido',
    )


@pytest.fixture
def closed_ticket(db, user):
    return SupportTicket.objects.create(
        user=user,
        subject='Ticket cerrado F3',
        body='Problema resuelto',
        status=SupportTicket.Status.CLOSED,
    )


# ─── Orders Tier A ──────────────────────────────────────────────────────────

class TestOrderCancellationsV2:
    def test_unauthenticated_returns_401(self, api_client):
        url = V2_ORDERS_BASE + 'ORD-0001/cancellations/'
        r = api_client.post(url, {})
        assert r.status_code == 401

    def test_v1_cancel_still_works(self, api_client):
        url = V1_ORDER_CANCEL_URL.format(n='ORD-0001')
        r = api_client.post(url, {})
        assert r.status_code == 401


class TestOrderShippingAddressV2:
    def test_unauthenticated_returns_401(self, api_client):
        url = V2_ORDERS_BASE + 'ORD-0001/shipping-address/'
        r = api_client.patch(url, {}, content_type='application/json')
        assert r.status_code == 401

    def test_v1_address_still_works(self, api_client):
        url = V1_ORDER_ADDRESS_URL.format(n='ORD-0001')
        r = api_client.patch(url, {}, content_type='application/json')
        assert r.status_code == 401


class TestOrderShippingMethodV2:
    def test_unauthenticated_returns_401(self, api_client):
        url = V2_ORDERS_BASE + 'ORD-0001/shipping-method/'
        r = api_client.patch(url, {}, content_type='application/json')
        assert r.status_code == 401

    def test_v1_shipping_still_works(self, api_client):
        url = V1_ORDER_SHIPPING_URL.format(n='ORD-0001')
        r = api_client.patch(url, {}, content_type='application/json')
        assert r.status_code == 401


# ─── Returns Tier A + B ─────────────────────────────────────────────────────

class TestReturnRequestsV2:
    def test_list_unauthenticated_returns_401(self, api_client):
        r = api_client.get(V2_RETURNS_BASE)
        assert r.status_code == 401

    def test_v1_returns_still_works(self, api_client):
        r = api_client.get(V1_RETURNS_URL)
        assert r.status_code == 401


class TestAdminReturnStatusV2:
    def test_unauthenticated_returns_401(self, api_client):
        url = V2_ADMIN_RETURNS_BASE + '1/status/'
        r = api_client.patch(url, {'action': 'approve'}, content_type='application/json')
        assert r.status_code == 401

    def test_non_admin_returns_403(self, auth_client):
        url = V2_ADMIN_RETURNS_BASE + '1/status/'
        r = auth_client.patch(url, {'action': 'approve'}, content_type='application/json')
        assert r.status_code == 403

    def test_invalid_action_returns_400(self, admin_auth_client):
        url = V2_ADMIN_RETURNS_BASE + '999/status/'
        r = admin_auth_client.patch(url, {'action': 'delete'}, content_type='application/json')
        assert r.status_code == 400
        assert r.data['codigo_error'] == 'INVALID_ACTION'

    def test_v1_approve_still_works(self, api_client):
        url = V1_ADMIN_RETURN_APPROVE_URL.format(id=999)
        r = api_client.post(url, {})
        assert r.status_code == 401


# ─── Reviews Tier B ─────────────────────────────────────────────────────────

class TestReviewDetailV2:
    def test_patch_without_edit_suffix_returns_401(self, api_client):
        url = V2_PRODUCTS_BASE + '1/reviews/1/'
        r = api_client.patch(url, {}, content_type='application/json')
        assert r.status_code == 401

    def test_v1_edit_url_still_works(self, api_client):
        url = V1_REVIEW_EDIT_URL.format(pid=1, pk=1)
        r = api_client.patch(url, {}, content_type='application/json')
        assert r.status_code == 401


class TestAdminReviewStatusV2:
    def test_unauthenticated_returns_401(self, api_client):
        url = V2_ADMIN_REVIEWS_BASE + '1/status/'
        r = api_client.patch(url, {'action': 'approve'}, content_type='application/json')
        assert r.status_code == 401

    def test_non_admin_returns_403(self, auth_client):
        url = V2_ADMIN_REVIEWS_BASE + '1/status/'
        r = auth_client.patch(url, {'action': 'approve'}, content_type='application/json')
        assert r.status_code == 403

    def test_invalid_action_returns_400(self, admin_auth_client):
        url = V2_ADMIN_REVIEWS_BASE + '999/status/'
        r = admin_auth_client.patch(url, {'action': 'delete'}, content_type='application/json')
        assert r.status_code == 400
        assert r.data['codigo_error'] == 'INVALID_ACTION'


# ─── Questions Tier A + B ────────────────────────────────────────────────────

class TestAdminQuestionAnswersV2:
    def test_unauthenticated_returns_401(self, api_client):
        url = V2_ADMIN_QUESTIONS_BASE + '1/answers/'
        r = api_client.post(url, {'answer_body': 'resp'}, content_type='application/json')
        assert r.status_code == 401

    def test_non_admin_returns_403(self, auth_client):
        url = V2_ADMIN_QUESTIONS_BASE + '1/answers/'
        r = auth_client.post(url, {'answer_body': 'resp'}, content_type='application/json')
        assert r.status_code == 403


class TestAdminQuestionStatusV2:
    def test_unauthenticated_returns_401(self, api_client):
        url = V2_ADMIN_QUESTIONS_BASE + '1/status/'
        r = api_client.patch(url, {'action': 'approve'}, content_type='application/json')
        assert r.status_code == 401

    def test_invalid_action_returns_400(self, admin_auth_client):
        url = V2_ADMIN_QUESTIONS_BASE + '999/status/'
        r = admin_auth_client.patch(url, {'action': 'delete'}, content_type='application/json')
        assert r.status_code == 400
        assert r.data['codigo_error'] == 'INVALID_ACTION'


# ─── Support Tier B ─────────────────────────────────────────────────────────

class TestSupportTicketStatusV2:
    def test_unauthenticated_returns_401(self, api_client):
        url = V2_SUPPORT_BASE + '1/status/'
        r = api_client.patch(url, {'action': 'close'}, content_type='application/json')
        assert r.status_code == 401

    def test_invalid_action_returns_400(self, auth_client, ticket):
        url = V2_SUPPORT_BASE + f'{ticket.pk}/status/'
        r = auth_client.patch(url, {'action': 'delete'}, content_type='application/json')
        assert r.status_code == 400
        assert r.data['codigo_error'] == 'INVALID_ACTION'

    def test_close_ticket(self, auth_client, ticket):
        url = V2_SUPPORT_BASE + f'{ticket.pk}/status/'
        r = auth_client.patch(url, {'action': 'close'}, content_type='application/json')
        assert r.status_code == 200
        ticket.refresh_from_db()
        assert ticket.status == SupportTicket.Status.CLOSED

    def test_reopen_ticket(self, auth_client, closed_ticket):
        url = V2_SUPPORT_BASE + f'{closed_ticket.pk}/status/'
        r = auth_client.patch(url, {'action': 'reopen'}, content_type='application/json')
        assert r.status_code == 200
        closed_ticket.refresh_from_db()
        assert closed_ticket.status == SupportTicket.Status.OPEN

    def test_v1_close_still_works(self, api_client, ticket):
        url = V1_SUPPORT_CLOSE_URL.format(id=ticket.pk)
        r = api_client.post(url, {})
        assert r.status_code == 401
