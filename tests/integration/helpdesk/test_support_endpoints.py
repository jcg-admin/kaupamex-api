"""
Tests — Support tickets (UC-SUPP-01..05)

UC-SUPP-01  POST   /api/v2/support/tickets/                     create ticket
UC-SUPP-02  GET    /api/v2/support/tickets/                     list user tickets
UC-SUPP-02  GET    /api/v2/support/tickets/{id}/                ticket detail
UC-SUPP-03  POST   /api/v2/support/tickets/{id}/replies/        add reply
UC-SUPP-04  POST   /api/v2/support/tickets/{id}/close/          close ticket
UC-SUPP-04  POST   /api/v2/support/tickets/{id}/reopen/         reopen ticket
UC-SUPP-05  GET    /api/v2/admin/support/tickets/               admin queue

Identifiers in English (DEC-DOC-005).
"""
import csv
import io
import time
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from addons.authz.services import is_superadmin
from addons.helpdesk.models import SupportTicket, SupportTicketReply
from addons.helpdesk.management.commands.auto_close_support_tickets import (
    AUTO_CLOSE_DAYS,
)
from addons.mail.models import Notification, NotificationType
from tests.factories.order_factory import make_order
from addons.sale.status_projection import STATUS_PENDING

pytestmark = pytest.mark.integration

TICKETS_URL = '/api/v2/support/tickets/'
ADMIN_TICKETS_URL = '/api/v2/admin/support/tickets/'


class TestSupportCapabilityGate:
    """Enforcement (ADR-020, DEC-ENF-01): el soporte propio exige
    ``account.support``. Autenticado sin la capacidad → 403."""

    def test_requires_account_support(self, api_client, db):
        u = get_user_model().objects.create_user(
            login='norole-support@practicayoruba.mx', password='TestPass123!')
        api_client.force_login(u)
        assert api_client.get(TICKETS_URL).status_code == 403


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

    def test_create_ticket_with_order_number_resolves(self, auth_client, user, db):
        # H-18: la UI solo conoce order_number (el PK no se expone). El
        # serializer debe resolverlo al order_id del comprador.
        order = make_order(
            user=user, order_number='PY-SUP00001', status='DELIVERED',
        )
        res = auth_client.post(TICKETS_URL, {
            'subject': 'Problema con mi pedido',
            'body': 'El producto llegó incompleto, falta una pieza.',
            'category': 'ORDER',
            'order_number': 'PY-SUP00001',
        }, format='json')
        assert res.status_code == 201, res.content
        assert res.json()['order_id'] == order.pk

    def test_create_ticket_unknown_order_number_returns_400(self, auth_client, user, db):
        res = auth_client.post(TICKETS_URL, {
            'subject': 'Problema con mi pedido',
            'body': 'El producto llegó incompleto, falta una pieza.',
            'category': 'ORDER',
            'order_number': 'PY-NOEXISTE9',
        }, format='json')
        assert res.status_code == 400
        assert res.json().get('codigo_error') == 'ORDER_NOT_FOUND'

    def test_create_ticket_notifies_buyer(self, auth_client, user, db):
        # H-18: crear un ticket ahora avisa al comprador (in-app + email).
        res = auth_client.post(TICKETS_URL, {
            'subject': 'Consulta general de prueba',
            'body': 'Quisiera saber más sobre los envíos a mi zona.',
        }, format='json')
        assert res.status_code == 201
        assert Notification.objects.filter(
            user=user, type=NotificationType.SUPPORT_UPDATE,
        ).exists()

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
        ticket = SupportTicket.objects.get(pk=res.json()['ticket_id'])
        assert ticket.priority == 'HIGH'
        assert ticket.category == 'URGENT'


# ────────────────────────────── UC-SUPP-02 ────────────────────────────────
class TestListAndDetail:
    def test_list_only_own_tickets(self, auth_client, user, admin_user, db):
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
        t = SupportTicket.objects.create(
            user=admin_user, subject='Ajeno', body='No accesible para el otro.')
        res = auth_client.get(f'{TICKETS_URL}{t.pk}/')
        assert res.status_code == 404

    def test_buyer_does_not_see_internal_notes(self, auth_client, user, admin_user, db):
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
        t = SupportTicket.objects.create(
            user=user, subject='Reply test', body='Mensaje original del ticket.')
        res = auth_client.post(f'{TICKETS_URL}{t.pk}/replies/', {
            'body': 'Gracias por la respuesta del equipo.',
        }, format='json')
        assert res.status_code == 201
        assert res.json()['body'].startswith('Gracias')

    def test_reply_too_short_returns_400(self, auth_client, user, db):
        t = SupportTicket.objects.create(
            user=user, subject='Reply test', body='Mensaje original del ticket.')
        res = auth_client.post(f'{TICKETS_URL}{t.pk}/replies/', {
            'body': 'no',
        }, format='json')
        assert res.status_code == 400

    def test_reply_to_closed_ticket_returns_409(self, auth_client, user, db):
        t = SupportTicket.objects.create(
            user=user, subject='Cerrado', body='Mensaje original del ticket.',
            status='CLOSED')
        res = auth_client.post(f'{TICKETS_URL}{t.pk}/replies/', {
            'body': 'No debería poder responder esto.',
        }, format='json')
        assert res.status_code == 409

    def test_reply_to_other_user_ticket_returns_404(self, auth_client, admin_user, db):
        t = SupportTicket.objects.create(
            user=admin_user, subject='Ajeno', body='Mensaje original del ticket.')
        res = auth_client.post(f'{TICKETS_URL}{t.pk}/replies/', {
            'body': 'Intento de respuesta ajena.',
        }, format='json')
        assert res.status_code == 404

    def test_buyer_cannot_post_internal_note(self, auth_client, user, db):
        t = SupportTicket.objects.create(
            user=user, subject='Notas', body='Mensaje original del ticket.')
        res = auth_client.post(f'{TICKETS_URL}{t.pk}/replies/', {
            'body': 'Quiero marcar esto como nota interna.',
            'is_internal_note': True,
        }, format='json')
        assert res.status_code == 403

    def test_admin_can_post_internal_note(self, admin_client, user, db):
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
        t = SupportTicket.objects.create(
            user=user, subject='Cerrar', body='Mensaje original del ticket.')
        res = auth_client.patch(
            f'{TICKETS_URL}{t.pk}/status/', {'action': 'close'}, format='json')
        assert res.status_code == 200
        assert res.json()['status'] == 'CLOSED'

    def test_buyer_close_notifies_as_buyer_not_staff(self, auth_client, user, db):
        # H-API-404: SupportTicketCloseView.post no seteaba
        # ticket._closed_by_staff antes de guardar, asi que el default
        # True del signal _support_ticket_closed (handlers.py) se
        # aplicaba tambien cuando cerraba el propio comprador.
        t = SupportTicket.objects.create(
            user=user, subject='Cerrar', body='Mensaje original del ticket.')
        res = auth_client.patch(
            f'{TICKETS_URL}{t.pk}/status/', {'action': 'close'}, format='json')
        assert res.status_code == 200
        notification = Notification.objects.get(
            user=user, type=NotificationType.SUPPORT_UPDATE)
        assert notification.subject == f'Ticket #{t.pk} cerrado'
        assert 'resuelto' not in notification.subject

    def test_admin_close_notifies_as_staff(self, admin_client, user, admin_user, db):
        t = SupportTicket.objects.create(
            user=user, subject='Cerrar', body='Mensaje original del ticket.')
        res = admin_client.patch(
            f'{TICKETS_URL}{t.pk}/status/', {'action': 'close'}, format='json')
        assert res.status_code == 200
        notification = Notification.objects.get(
            user=user, type=NotificationType.SUPPORT_UPDATE)
        assert notification.subject == f'Ticket #{t.pk} resuelto — Soporte'

    def test_close_already_closed_returns_409(self, auth_client, user, db):
        t = SupportTicket.objects.create(
            user=user, subject='Cerrar', body='Mensaje original del ticket.',
            status='CLOSED')
        res = auth_client.patch(
            f'{TICKETS_URL}{t.pk}/status/', {'action': 'close'}, format='json')
        assert res.status_code == 409

    def test_close_other_user_ticket_returns_404(self, auth_client, admin_user, db):
        t = SupportTicket.objects.create(
            user=admin_user, subject='Ajeno', body='Mensaje original del ticket.')
        res = auth_client.patch(
            f'{TICKETS_URL}{t.pk}/status/', {'action': 'close'}, format='json')
        assert res.status_code == 404

    def test_reopen_closed_ticket(self, auth_client, user, db):
        t = SupportTicket.objects.create(
            user=user, subject='Reabrir', body='Mensaje original del ticket.',
            status='CLOSED')
        res = auth_client.patch(
            f'{TICKETS_URL}{t.pk}/status/', {'action': 'reopen'}, format='json')
        assert res.status_code == 200
        assert res.json()['status'] == 'OPEN'

    def test_reopen_open_ticket_returns_409(self, auth_client, user, db):
        t = SupportTicket.objects.create(
            user=user, subject='Reabrir', body='Mensaje original del ticket.')
        res = auth_client.patch(
            f'{TICKETS_URL}{t.pk}/status/', {'action': 'reopen'}, format='json')
        assert res.status_code == 409


# ────────────────────────────── UC-SUPP-05 ────────────────────────────────
class TestAdminQueue:
    def test_admin_lists_all_tickets(self, admin_client, user, db):
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

    def test_admin_list_is_paginated(self, admin_client, user, db):
        for i in range(3):
            SupportTicket.objects.create(
                user=user, subject=f'Ticket {i}',
                body='Mensaje suficientemente largo.')
        res = admin_client.get(ADMIN_TICKETS_URL)
        assert res.status_code == 200
        data = res.json()
        assert 'results' in data
        assert 'count' in data

    def test_admin_list_has_metrics(self, admin_client, user, db):
        SupportTicket.objects.create(
            user=user, subject='Abierto', body='Mensaje suficientemente largo.')
        SupportTicket.objects.create(
            user=user, subject='Resuelto', body='Mensaje suficientemente largo.',
            status='RESOLVED')
        res = admin_client.get(ADMIN_TICKETS_URL)
        assert res.status_code == 200
        data = res.json()
        assert 'metrics' in data
        metrics = data['metrics']
        assert 'open' in metrics
        assert 'in_progress' in metrics
        assert 'awaiting_user' in metrics
        assert 'resolved' in metrics
        assert 'closed' in metrics
        assert metrics['open'] >= 1
        assert metrics['resolved'] >= 1

    def test_admin_list_has_customer_field(self, admin_client, user, db):
        SupportTicket.objects.create(
            user=user, subject='Con buyer', body='Mensaje suficientemente largo.')
        res = admin_client.get(ADMIN_TICKETS_URL)
        assert res.status_code == 200
        items = res.json()['results']
        assert len(items) >= 1
        ticket = items[0]
        assert 'customer' in ticket
        assert ticket['customer']['email'] == user.email

    def test_admin_list_has_replies_count(self, admin_client, user, db):
        ticket = SupportTicket.objects.create(
            user=user, subject='Con respuestas', body='Mensaje suficientemente largo.')
        SupportTicketReply.objects.create(ticket=ticket, author=user, body='Respuesta test.')
        res = admin_client.get(ADMIN_TICKETS_URL)
        assert res.status_code == 200
        items = res.json()['results']
        match = next((t for t in items if t['ticket_id'] == ticket.pk), None)
        assert match is not None
        assert match['replies_count'] == 1

    def test_admin_search_by_email(self, admin_client, user, db):
        SupportTicket.objects.create(
            user=user, subject='Busqueda email', body='Mensaje suficientemente largo.')
        res = admin_client.get(f'{ADMIN_TICKETS_URL}?q={user.email[:5]}')
        assert res.status_code == 200
        items = res.json()['results']
        assert len(items) >= 1

    def test_admin_search_no_match_returns_empty(self, admin_client, db):
        res = admin_client.get(f'{ADMIN_TICKETS_URL}?q=correo_que_no_existe@xyz.com')
        assert res.status_code == 200
        assert res.json()['results'] == []

    def test_admin_list_ordered_oldest_first(self, admin_client, user, db):
        t1 = SupportTicket.objects.create(
            user=user, subject='Primero', body='Mensaje suficientemente largo.')
        time.sleep(0.01)
        t2 = SupportTicket.objects.create(
            user=user, subject='Segundo', body='Mensaje suficientemente largo.')
        res = admin_client.get(ADMIN_TICKETS_URL)
        assert res.status_code == 200
        items = res.json()['results']
        ids = [t['ticket_id'] for t in items[:2]]
        assert ids[0] == t1.pk
        assert ids[1] == t2.pk


# ────────────── SUPP-05 (T-009) — metrica tiempo-primera-respuesta ────────
class TestAdminFirstResponseMetric:
    """UC-SUPP-05 — promedio de tiempo hasta la primera respuesta de staff.

    Backlog: `grep csv` = 0 en support antes de este commit; tampoco existia
    ninguna metrica de tiempo-primera-respuesta en ``AdminSupportTicketListView``
    (src/addons/helpdesk/views.py:435-443, solo conteos por status).
    """

    def _create_ticket_with_reply(self, user, admin_user, *, ticket_created_at,
                                   reply_created_at, subject):
        ticket = SupportTicket.objects.create(
            user=user, subject=subject, body='Mensaje suficientemente largo.')
        SupportTicket.objects.filter(pk=ticket.pk).update(
            created_at=ticket_created_at)
        reply = SupportTicketReply.objects.create(
            ticket=ticket, author=admin_user, body='Respuesta de soporte.')
        SupportTicketReply.objects.filter(pk=reply.pk).update(
            created_at=reply_created_at)
        return ticket

    def test_avg_first_response_minutes_computes_correct_average(
        self, admin_client, admin_user, user, db,
    ):
        t0 = timezone.now() - timedelta(days=1)
        # Ticket rapido: 10 minutos hasta la primera respuesta de staff.
        self._create_ticket_with_reply(
            user, admin_user,
            ticket_created_at=t0, reply_created_at=t0 + timedelta(minutes=10),
            subject='Rapido',
        )
        # Ticket lento: 30 minutos hasta la primera respuesta de staff.
        self._create_ticket_with_reply(
            user, admin_user,
            ticket_created_at=t0, reply_created_at=t0 + timedelta(minutes=30),
            subject='Lento',
        )
        # Ticket sin respuesta: no debe contarse en el promedio.
        SupportTicket.objects.create(
            user=user, subject='Sin respuesta',
            body='Mensaje suficientemente largo.')

        res = admin_client.get(ADMIN_TICKETS_URL)
        assert res.status_code == 200
        metrics = res.json()['metrics']
        assert 'avg_first_response_minutes' in metrics
        # (10 + 30) / 2 = 20.0
        assert metrics['avg_first_response_minutes'] == 20.0

    def test_avg_first_response_minutes_none_when_no_replies(
        self, admin_client, user, db,
    ):
        SupportTicket.objects.create(
            user=user, subject='Sin respuesta',
            body='Mensaje suficientemente largo.')
        res = admin_client.get(ADMIN_TICKETS_URL)
        assert res.status_code == 200
        assert res.json()['metrics']['avg_first_response_minutes'] is None

    def test_buyer_only_reply_does_not_count_as_first_response(
        self, admin_client, user, db,
    ):
        # Una respuesta del propio comprador (no staff) no cuenta como
        # primera respuesta — la metrica mide tiempo de respuesta de soporte.
        ticket = SupportTicket.objects.create(
            user=user, subject='Solo comprador',
            body='Mensaje suficientemente largo.')
        SupportTicketReply.objects.create(
            ticket=ticket, author=user, body='Sigo esperando respuesta.')
        res = admin_client.get(ADMIN_TICKETS_URL)
        assert res.status_code == 200
        assert res.json()['metrics']['avg_first_response_minutes'] is None


# ────────────── SUPP-05 (T-009) — export CSV de tickets ───────────────────
class TestAdminExportCSV:
    """UC-SUPP-05 — export CSV de la cola admin de tickets."""

    ADMIN_EXPORT_URL = f'{ADMIN_TICKETS_URL}export/'

    def test_export_requires_admin(self, auth_client, db):
        res = auth_client.get(self.ADMIN_EXPORT_URL)
        assert res.status_code == 403

    def test_export_returns_csv_content_type(self, admin_client, user, db):
        SupportTicket.objects.create(
            user=user, subject='Exportable',
            body='Mensaje suficientemente largo.')
        res = admin_client.get(self.ADMIN_EXPORT_URL)
        assert res.status_code == 200
        assert res['Content-Type'].startswith('text/csv')
        assert 'attachment' in res['Content-Disposition']

    def test_export_rows_match_tickets(self, admin_client, user, admin_user, db):
        t0 = timezone.now() - timedelta(days=1)
        ticket = SupportTicket.objects.create(
            user=user, subject='Con respuesta',
            body='Mensaje suficientemente largo.')
        SupportTicket.objects.filter(pk=ticket.pk).update(created_at=t0)
        reply = SupportTicketReply.objects.create(
            ticket=ticket, author=admin_user, body='Respuesta de soporte.')
        SupportTicketReply.objects.filter(pk=reply.pk).update(
            created_at=t0 + timedelta(minutes=15))

        res = admin_client.get(self.ADMIN_EXPORT_URL)
        assert res.status_code == 200
        rows = list(csv.reader(io.StringIO(res.content.decode('utf-8'))))
        header, data_rows = rows[0], rows[1:]
        assert header == [
            'id', 'asunto', 'estado', 'prioridad', 'categoria',
            'comprador_email', 'created_at', 'primera_respuesta',
        ]
        match = next(r for r in data_rows if r[0] == str(ticket.pk))
        assert match[1] == 'Con respuesta'
        assert match[2] == 'OPEN'
        assert match[5] == user.email
        assert match[7] != ''   # primera_respuesta poblada

    def test_export_respects_status_filter(self, admin_client, user, db):
        SupportTicket.objects.create(
            user=user, subject='Abierto',
            body='Mensaje suficientemente largo.')
        SupportTicket.objects.create(
            user=user, subject='Cerrado', status='CLOSED',
            body='Mensaje suficientemente largo.')
        res = admin_client.get(f'{self.ADMIN_EXPORT_URL}?status=CLOSED')
        assert res.status_code == 200
        rows = list(csv.reader(io.StringIO(res.content.decode('utf-8'))))
        subjects = [r[1] for r in rows[1:]]
        assert subjects == ['Cerrado']


# ────────────── UC-SUPP-01 AC-03 — order ownership + duplicate (D-002/D-003) ─

class TestCreateTicketOrderOwnership:
    """D-002 — order_id solo se acepta si pertenece al comprador autenticado."""

    def _make_order(self, owner):
        return make_order(user=owner, status=STATUS_PENDING)

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


# ───────────────────── UC-SUPP-03 AC-06 (T-017) ──────────────────────────
class TestReplyOwnershipIsolation:
    """UC-SUPP-03 AC-06 — Aislamiento por dueño (RNF-SEC-003).

    Refuerza el caso existente ``test_reply_to_other_user_ticket_returns_404``
    (que usa ``admin_user`` como dueño ajeno, un staff que de todos modos
    haría bypass de la verificación de propiedad). Aquí ambos actores son
    compradores reales sin ``is_staff``: comprador A (``user`` /
    ``auth_client``) y comprador B (``auth_user``). El AC exige que A no
    pueda revelar siquiera la existencia del ticket de B (404, no 403) y
    que no se cree ningún reply.
    """

    def test_uc_supp_03_responder_ticket_ajeno_404(
            self, auth_client, user, auth_user, db):
        # auth_user es un segundo comprador NO-admin (comprador B).
        # Party/authz (T-201): "staff" = titular del rol superadmin.
        assert is_superadmin(auth_user) is False
        ticket_b = SupportTicket.objects.create(
            user=auth_user,
            subject='Ticket del comprador B',
            body='Mensaje original del ticket del comprador B.',
        )
        replies_before = SupportTicketReply.objects.filter(
            ticket=ticket_b).count()

        # Comprador A (auth_client) intenta responder al ticket de B.
        res = auth_client.post(
            f'{TICKETS_URL}{ticket_b.pk}/replies/',
            {'body': 'Intento de respuesta al ticket ajeno del comprador B.'},
            format='json',
        )

        # RNF-SEC-003: 404 (no revelar existencia), no 403.
        assert res.status_code == 404
        # No se crea el reply.
        assert SupportTicketReply.objects.filter(
            ticket=ticket_b).count() == replies_before


# ───────────────────── UC-SUPP-04 AC-06 (T-018) ──────────────────────────
class CierreIdempotenteAutoCloseTest(TestCase):
    """UC-SUPP-04 AC-06 — Cierre idempotente del job de auto-cierre.

    El job ``auto_close_support_tickets`` ejecutado dos veces sobre el
    mismo ticket ya ``CLOSED`` NO debe enviar una segunda notificación al
    comprador (RNF Confiabilidad). Se usa ``TestCase`` (no pytest plano)
    porque el assert requiere ``captureOnCommitCallbacks`` para ejecutar
    el ``transaction.on_commit`` que dispara la notificación.

    El caso existente en ``apps/support/tests_uc_not_08.py`` solo corre el
    comando UNA vez y cuenta 1 notificación; la dimensión de idempotencia
    (correr 2× sin doble notificación) no estaba cubierta.
    """

    def setUp(self):
        User = get_user_model()
        self.buyer = User.objects.create_user(
            login='buyer-supp04-t018@practicayoruba.mx',
            password='BuyerPass123!',
        )

    def _stale_awaiting_ticket(self):
        ticket = SupportTicket.objects.create(
            user=self.buyer,
            subject='Ticket pendiente de respuesta del usuario',
            body='Mensaje original; el staff respondió y espera al usuario.',
            status=SupportTicket.Status.AWAITING_USER,
        )
        stale_time = timezone.now() - timedelta(days=AUTO_CLOSE_DAYS + 1)
        SupportTicket.objects.filter(pk=ticket.pk).update(updated_at=stale_time)
        ticket.refresh_from_db()
        return ticket

    def test_uc_supp_04_cierre_idempotente_sin_doble_notificacion(self):
        ticket = self._stale_awaiting_ticket()

        # Primera ejecución: cierra el ticket y notifica al comprador.
        with self.captureOnCommitCallbacks(execute=True):
            call_command('auto_close_support_tickets')
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, SupportTicket.Status.CLOSED)
        notifs_after_first = Notification.objects.filter(
            user=self.buyer, type=NotificationType.SUPPORT_UPDATE,
        ).count()
        self.assertEqual(notifs_after_first, 1)

        # Segunda ejecución sobre el mismo ticket ya CLOSED: idempotente,
        # sin segunda notificación.
        with self.captureOnCommitCallbacks(execute=True):
            call_command('auto_close_support_tickets')
        notifs_after_second = Notification.objects.filter(
            user=self.buyer, type=NotificationType.SUPPORT_UPDATE,
        ).count()
        self.assertEqual(notifs_after_second, 1)
