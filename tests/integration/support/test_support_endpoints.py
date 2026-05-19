"""
Tests — Support tickets (UC-SUPP-01..05)

UC-SUPP-01  POST   /api/v1/support/tickets/                     create ticket
UC-SUPP-02  GET    /api/v1/support/tickets/                     list user tickets
UC-SUPP-02  GET    /api/v1/support/tickets/{id}/                ticket detail
UC-SUPP-03  POST   /api/v1/support/tickets/{id}/replies/        add reply
UC-SUPP-04  POST   /api/v1/support/tickets/{id}/close/          close ticket
UC-SUPP-04  POST   /api/v1/support/tickets/{id}/reopen/         reopen ticket
UC-SUPP-05  GET    /api/v1/admin/support/tickets/               admin queue

Identifiers in English (DEC-DOC-005).
"""
import pytest

pytestmark = pytest.mark.integration

TICKETS_URL = '/api/v1/support/tickets/'
ADMIN_TICKETS_URL = '/api/v1/admin/support/tickets/'


# ────────────────────────────── UC-SUPP-01 ────────────────────────────────
class TestCreateTicket:
    def test_requires_auth(self, api_client, db):
        res = api_client.post(TICKETS_URL, {
            'subject': 'Producto dañado',
            'body': 'El paquete tenía la caja rota y el producto rayado.',
        }, format='json')
        assert res.status_code == 401

    def test_create_minimal_ticket_returns_201(self, auth_client, db):
        res = auth_client.post(TICKETS_URL, {
            'subject': 'Producto dañado',
            'body': 'El paquete tenía la caja rota y el producto rayado.',
        }, format='json')
        assert res.status_code == 201
        body = res.json()
        assert body['status'] == 'OPEN'
        assert body['subject'] == 'Producto dañado'
        assert 'ticket_id' in body
        assert 'created_at' in body

    def test_subject_too_short_returns_400(self, auth_client, db):
        res = auth_client.post(TICKETS_URL, {
            'subject': 'abc',
            'body': 'Mensaje suficientemente largo de soporte.',
        }, format='json')
        assert res.status_code == 400

    def test_body_too_short_returns_400(self, auth_client, db):
        res = auth_client.post(TICKETS_URL, {
            'subject': 'Asunto válido',
            'body': 'corto',
        }, format='json')
        assert res.status_code == 400

    def test_category_urgent_promotes_priority_high(self, auth_client, db):
        res = auth_client.post(TICKETS_URL, {
            'subject': 'Urgente revisión',
            'body': 'Detecté un cargo no reconocido a mi cuenta.',
            'category': 'URGENT',
        }, format='json')
        assert res.status_code == 201
        from apps.support.models import SupportTicket
        ticket = SupportTicket.objects.get(pk=res.json()['ticket_id'])
        assert ticket.priority == 'HIGH'
        assert ticket.category == 'URGENT'


# ────────────────────────────── UC-SUPP-02 ────────────────────────────────
class TestListAndDetail:
    def test_list_only_own_tickets(self, auth_client, user, admin_user, db):
        from apps.support.models import SupportTicket
        SupportTicket.objects.create(
            user=user, subject='Mio uno', body='Mensaje suficientemente largo.')
        SupportTicket.objects.create(
            user=admin_user, subject='Otro user', body='No deberia verse.')
        res = auth_client.get(TICKETS_URL)
        assert res.status_code == 200
        data = res.json()
        items = data['results'] if isinstance(data, dict) else data
        assert len(items) == 1
        assert items[0]['subject'] == 'Mio uno'

    def test_detail_returns_replies(self, auth_client, user, db):
        from apps.support.models import SupportTicket, SupportTicketReply
        t = SupportTicket.objects.create(
            user=user, subject='Detalle', body='Mensaje del ticket original.')
        SupportTicketReply.objects.create(
            ticket=t, author=user, body='Respuesta del comprador.')
        res = auth_client.get(f'{TICKETS_URL}{t.pk}/')
        assert res.status_code == 200
        body = res.json()
        assert body['ticket_id'] == t.pk
        assert len(body['replies']) == 1
        assert 'available_actions' in body

    def test_detail_other_user_returns_404(self, auth_client, admin_user, db):
        """RNF-SEC-003 — leak prevention."""
        from apps.support.models import SupportTicket
        t = SupportTicket.objects.create(
            user=admin_user, subject='Ajeno', body='No accesible para el otro.')
        res = auth_client.get(f'{TICKETS_URL}{t.pk}/')
        assert res.status_code == 404

    def test_buyer_does_not_see_internal_notes(self, auth_client, user, admin_user, db):
        from apps.support.models import SupportTicket, SupportTicketReply
        t = SupportTicket.objects.create(
            user=user, subject='Notas', body='Mensaje del ticket original.')
        SupportTicketReply.objects.create(
            ticket=t, author=admin_user, body='Nota interna del staff.',
            is_internal_note=True)
        SupportTicketReply.objects.create(
            ticket=t, author=admin_user, body='Respuesta visible al cliente.')
        res = auth_client.get(f'{TICKETS_URL}{t.pk}/')
        assert res.status_code == 200
        bodies = [r['body'] for r in res.json()['replies']]
        assert 'Nota interna del staff.' not in bodies
        assert 'Respuesta visible al cliente.' in bodies


# ────────────────────────────── UC-SUPP-03 ────────────────────────────────
class TestReplies:
    def test_buyer_can_reply_to_own_ticket(self, auth_client, user, db):
        from apps.support.models import SupportTicket
        t = SupportTicket.objects.create(
            user=user, subject='Reply test', body='Mensaje original del ticket.')
        res = auth_client.post(f'{TICKETS_URL}{t.pk}/replies/', {
            'body': 'Gracias por la respuesta del equipo.',
        }, format='json')
        assert res.status_code == 201
        assert res.json()['body'].startswith('Gracias')

    def test_reply_too_short_returns_400(self, auth_client, user, db):
        from apps.support.models import SupportTicket
        t = SupportTicket.objects.create(
            user=user, subject='Reply test', body='Mensaje original del ticket.')
        res = auth_client.post(f'{TICKETS_URL}{t.pk}/replies/', {
            'body': 'no',
        }, format='json')
        assert res.status_code == 400

    def test_reply_to_closed_ticket_returns_409(self, auth_client, user, db):
        from apps.support.models import SupportTicket
        t = SupportTicket.objects.create(
            user=user, subject='Cerrado', body='Mensaje original del ticket.',
            status='CLOSED')
        res = auth_client.post(f'{TICKETS_URL}{t.pk}/replies/', {
            'body': 'No debería poder responder esto.',
        }, format='json')
        assert res.status_code == 409

    def test_reply_to_other_user_ticket_returns_404(self, auth_client, admin_user, db):
        from apps.support.models import SupportTicket
        t = SupportTicket.objects.create(
            user=admin_user, subject='Ajeno', body='Mensaje original del ticket.')
        res = auth_client.post(f'{TICKETS_URL}{t.pk}/replies/', {
            'body': 'Intento de respuesta ajena.',
        }, format='json')
        assert res.status_code == 404

    def test_buyer_cannot_post_internal_note(self, auth_client, user, db):
        from apps.support.models import SupportTicket
        t = SupportTicket.objects.create(
            user=user, subject='Notas', body='Mensaje original del ticket.')
        res = auth_client.post(f'{TICKETS_URL}{t.pk}/replies/', {
            'body': 'Quiero marcar esto como nota interna.',
            'is_internal_note': True,
        }, format='json')
        assert res.status_code == 403

    def test_admin_can_post_internal_note(self, admin_client, user, db):
        from apps.support.models import SupportTicket
        t = SupportTicket.objects.create(
            user=user, subject='Admin reply', body='Mensaje original del ticket.')
        res = admin_client.post(f'{TICKETS_URL}{t.pk}/replies/', {
            'body': 'Nota interna del equipo solo visible al staff.',
            'is_internal_note': True,
        }, format='json')
        assert res.status_code == 201
        assert res.json()['is_internal_note'] is True


# ────────────────────────────── UC-SUPP-04 ────────────────────────────────
class TestCloseReopen:
    def test_buyer_can_close_own_ticket(self, auth_client, user, db):
        from apps.support.models import SupportTicket
        t = SupportTicket.objects.create(
            user=user, subject='Cerrar', body='Mensaje original del ticket.')
        res = auth_client.post(f'{TICKETS_URL}{t.pk}/close/', {}, format='json')
        assert res.status_code == 200
        assert res.json()['status'] == 'CLOSED'

    def test_close_already_closed_returns_409(self, auth_client, user, db):
        from apps.support.models import SupportTicket
        t = SupportTicket.objects.create(
            user=user, subject='Cerrar', body='Mensaje original del ticket.',
            status='CLOSED')
        res = auth_client.post(f'{TICKETS_URL}{t.pk}/close/', {}, format='json')
        assert res.status_code == 409

    def test_close_other_user_ticket_returns_404(self, auth_client, admin_user, db):
        from apps.support.models import SupportTicket
        t = SupportTicket.objects.create(
            user=admin_user, subject='Ajeno', body='Mensaje original del ticket.')
        res = auth_client.post(f'{TICKETS_URL}{t.pk}/close/', {}, format='json')
        assert res.status_code == 404

    def test_reopen_closed_ticket(self, auth_client, user, db):
        from apps.support.models import SupportTicket
        t = SupportTicket.objects.create(
            user=user, subject='Reabrir', body='Mensaje original del ticket.',
            status='CLOSED')
        res = auth_client.post(f'{TICKETS_URL}{t.pk}/reopen/', {}, format='json')
        assert res.status_code == 200
        assert res.json()['status'] == 'OPEN'

    def test_reopen_open_ticket_returns_409(self, auth_client, user, db):
        from apps.support.models import SupportTicket
        t = SupportTicket.objects.create(
            user=user, subject='Reabrir', body='Mensaje original del ticket.')
        res = auth_client.post(f'{TICKETS_URL}{t.pk}/reopen/', {}, format='json')
        assert res.status_code == 409


# ────────────────────────────── UC-SUPP-05 ────────────────────────────────
class TestAdminQueue:
    def test_admin_lists_all_tickets(self, admin_client, user, db):
        from apps.support.models import SupportTicket
        SupportTicket.objects.create(
            user=user, subject='Uno', body='Mensaje suficientemente largo.')
        SupportTicket.objects.create(
            user=user, subject='Dos', body='Otro mensaje suficientemente largo.',
            status='RESOLVED')
        res = admin_client.get(ADMIN_TICKETS_URL)
        assert res.status_code == 200
        data = res.json()
        items = data['results'] if isinstance(data, dict) else data
        assert len(items) >= 2

    def test_non_admin_cannot_access_admin_queue(self, auth_client, db):
        res = auth_client.get(ADMIN_TICKETS_URL)
        assert res.status_code == 403

    def test_admin_filter_by_status(self, admin_client, user, db):
        from apps.support.models import SupportTicket
        SupportTicket.objects.create(
            user=user, subject='Abierto', body='Mensaje suficientemente largo.')
        SupportTicket.objects.create(
            user=user, subject='Cerrado', body='Mensaje suficientemente largo.',
            status='CLOSED')
        res = admin_client.get(f'{ADMIN_TICKETS_URL}?status=CLOSED')
        assert res.status_code == 200
        data = res.json()
        items = data['results'] if isinstance(data, dict) else data
        assert all(item['status'] == 'CLOSED' for item in items)

    def test_admin_filter_by_priority(self, admin_client, user, db):
        from apps.support.models import SupportTicket
        SupportTicket.objects.create(
            user=user, subject='Alta', body='Mensaje suficientemente largo.',
            priority='HIGH')
        SupportTicket.objects.create(
            user=user, subject='Normal', body='Mensaje suficientemente largo.',
            priority='NORMAL')
        res = admin_client.get(f'{ADMIN_TICKETS_URL}?priority=HIGH')
        assert res.status_code == 200
        data = res.json()
        items = data['results'] if isinstance(data, dict) else data
        assert all(item['priority'] == 'HIGH' for item in items)


# ────────────── UC-SUPP-01 AC-03 — order ownership + duplicate (D-002/D-003) ─

class TestCreateTicketOrderOwnership:
    """D-002 — order_id solo se acepta si pertenece al comprador autenticado."""

    def _make_order(self, owner):
        from apps.orders.models import Order
        return Order.objects.create(user=owner, status=Order.STATUS_PENDING)

    def test_create_ticket_with_own_order_returns_201(self, auth_client, user, db):
        order = self._make_order(user)
        res = auth_client.post(TICKETS_URL, {
            'subject': 'Producto dañado',
            'body':    'El paquete tenía la caja rota.',
            'order_id': order.pk,
        }, format='json')
        assert res.status_code == 201, res.content
        assert res.json()['order_id'] == order.pk

    def test_create_ticket_with_other_user_order_returns_400(
            self, auth_client, user, admin_user, db):
        other_order = self._make_order(admin_user)  # owned by admin, not buyer
        res = auth_client.post(TICKETS_URL, {
            'subject': 'Producto dañado',
            'body':    'El paquete tenía la caja rota.',
            'order_id': other_order.pk,
        }, format='json')
        assert res.status_code == 400
        body = res.json()
        # DRF anida el error bajo el nombre del campo.
        order_errs = body.get('order_id') or body.get('order_id', [])
        # validate_order_id raises ValidationError({...}); DRF lo expone
        # como lista de dicts o dict.
        flat = str(order_errs)
        assert 'ORDER_NOT_FOUND' in flat

    def test_create_ticket_with_nonexistent_order_returns_400(
            self, auth_client, db):
        res = auth_client.post(TICKETS_URL, {
            'subject': 'Producto dañado',
            'body':    'El paquete tenía la caja rota.',
            'order_id': 999999,
        }, format='json')
        assert res.status_code == 400
        assert 'ORDER_NOT_FOUND' in str(res.content)


class TestCreateTicketDuplicateDetection:
    """D-003 — UC-SUPP-01 AC-03: 409 DUPLICATE_TICKET si ya hay uno activo."""

    def test_second_ticket_same_category_returns_409(self, auth_client, db):
        first = auth_client.post(TICKETS_URL, {
            'subject': 'Pedido perdido',
            'body':    'Lleva 2 semanas sin entregarse.',
            'category': 'GENERAL',
        }, format='json')
        assert first.status_code == 201

        second = auth_client.post(TICKETS_URL, {
            'subject': 'Pedido perdido nuevamente',
            'body':    'Sigue sin llegar al domicilio indicado.',
            'category': 'GENERAL',
        }, format='json')
        assert second.status_code == 409
        body = second.json()
        assert body['error_code'] == 'DUPLICATE_TICKET'
        assert body['ticket_id'] == first.json()['ticket_id']

    def test_different_category_allows_new_ticket(self, auth_client, db):
        first = auth_client.post(TICKETS_URL, {
            'subject': 'Pedido perdido',
            'body':    'Lleva semanas sin entregarse.',
            'category': 'GENERAL',
        }, format='json')
        assert first.status_code == 201

        second = auth_client.post(TICKETS_URL, {
            'subject': 'Producto dañado',
            'body':    'El paquete llego destrozado.',
            'category': 'DAMAGED',
        }, format='json')
        assert second.status_code == 201

    def test_closed_ticket_does_not_block_new_one(self, auth_client, user, db):
        from apps.support.models import SupportTicket
        SupportTicket.objects.create(
            user=user, subject='Antiguo', body='Mensaje suficientemente largo.',
            category='GENERAL', status=SupportTicket.Status.CLOSED)

        res = auth_client.post(TICKETS_URL, {
            'subject': 'Caso nuevo',
            'body':    'Detalle suficientemente largo del caso reciente.',
            'category': 'GENERAL',
        }, format='json')
        assert res.status_code == 201

    def test_different_order_allows_new_ticket(self, auth_client, user, db):
        from apps.orders.models import Order
        order_a = Order.objects.create(user=user, status=Order.STATUS_PENDING)
        order_b = Order.objects.create(user=user, status=Order.STATUS_PENDING)

        first = auth_client.post(TICKETS_URL, {
            'subject': 'Problema con orden A',
            'body':    'La orden A tiene un problema visible.',
            'category': 'ORDER',
            'order_id': order_a.pk,
        }, format='json')
        assert first.status_code == 201

        second = auth_client.post(TICKETS_URL, {
            'subject': 'Problema con orden B',
            'body':    'La orden B tiene otro problema distinto.',
            'category': 'ORDER',
            'order_id': order_b.pk,
        }, format='json')
        assert second.status_code == 201
