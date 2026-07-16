"""
Tests — Contact endpoints (UC-COM-01..03)

Public:
  POST /api/v2/contact/messages/                          create message

Admin:
  GET  /api/v2/admin/contact/messages/                    inbox
  GET  /api/v2/admin/contact/messages/<id>/               detail
  POST /api/v2/admin/contact/messages/<id>/read/          mark as read
  POST /api/v2/admin/contact/messages/<id>/reply/         send reply

JSON keys + identifiers in English (DEC-DOC-005).
"""
import pytest
from apps.modules.contact.models import ContactMessage
from django.core import mail

pytestmark = pytest.mark.integration

CREATE_URL = '/api/v2/contact/messages/'
ADMIN_LIST_URL = '/api/v2/admin/contact/messages/'


def _admin_detail_url(pk):
    return f'/api/v2/admin/contact/messages/{pk}/'


def _admin_read_url(pk):
    return f'/api/v2/admin/contact/messages/{pk}/read/'


def _admin_reply_url(pk):
    return f'/api/v2/admin/contact/messages/{pk}/reply/'


def _make_message(**kwargs):
    defaults = {
        'name': 'Juan',
        'email': 'juan@example.com',
        'phone': '5555-5555',
        'subject': 'Consulta',
        'body': 'Hola, quisiera saber...',
    }
    defaults.update(kwargs)
    return ContactMessage.objects.create(**defaults)


# ─── POST /contact/messages — public create ──────────────────────────────
class TestCreateContactMessage:
    def test_anonymous_can_create_message(self, api_client, db):
        res = api_client.post(CREATE_URL, {
            'name': 'Maria',
            'email': 'maria@example.com',
            'subject': 'Pregunta sobre envios',
            'body': 'Hacen envios a Veracruz?',
        }, format='json')
        assert res.status_code == 201
        body = res.json()
        for key in ('id', 'name', 'email', 'subject', 'body', 'created_at'):
            assert key in body

        assert ContactMessage.objects.filter(
            email='maria@example.com',
        ).count() == 1

    def test_create_notifies_contact_mailbox(self, api_client, db, settings):
        # UC-COM-01: el alta pública avisa al equipo en el buzón de contacto
        # (hola@) con el remitente en el cuerpo, sin filtrarlo al campo From.
        mail.outbox.clear()
        res = api_client.post(CREATE_URL, {
            'name': 'Maria',
            'email': 'maria@example.com',
            'subject': 'Pregunta sobre envios',
            'body': 'Hacen envios a Veracruz?',
        }, format='json')
        assert res.status_code == 201
        notices = [
            m for m in mail.outbox
            if settings.CONTACT_NOTIFY_EMAIL in m.to
        ]
        assert len(notices) == 1
        notice = notices[0]
        assert notice.from_email == settings.CONTACT_FROM_EMAIL
        assert 'maria@example.com' in notice.body
        assert 'Hacen envios a Veracruz?' in notice.body

    def test_email_is_required(self, api_client, db):
        res = api_client.post(CREATE_URL, {
            'name': 'X',
            'subject': 'Y',
            'body': 'Hola mundo',
        }, format='json')
        assert res.status_code == 400

    def test_short_body_rejected(self, api_client, db):
        res = api_client.post(CREATE_URL, {
            'name': 'Maria',
            'email': 'm@example.com',
            'subject': 'Pregunta',
            'body': 'X',
        }, format='json')
        assert res.status_code == 400


# ─── GET /admin/contact/messages — admin list ────────────────────────────
class TestAdminListMessages:
    def test_requires_auth(self, api_client, db):
        res = api_client.get(ADMIN_LIST_URL)
        assert res.status_code == 401

    def test_requires_staff(self, auth_client, db):
        res = auth_client.get(ADMIN_LIST_URL)
        assert res.status_code == 403

    def test_admin_lists_all(self, admin_client, db):
        _make_message(subject='A')
        _make_message(subject='B')
        res = admin_client.get(ADMIN_LIST_URL)
        assert res.status_code == 200
        body = res.json()
        assert 'results' in body
        assert len(body['results']) == 2

    def test_admin_lists_empty(self, admin_client, db):
        res = admin_client.get(ADMIN_LIST_URL)
        assert res.status_code == 200
        assert res.json()['results'] == []


# ─── GET /admin/contact/messages/<id> — admin detail ─────────────────────
class TestAdminDetail:
    def test_requires_staff(self, auth_client, db):
        msg = _make_message()
        res = auth_client.get(_admin_detail_url(msg.pk))
        assert res.status_code == 403

    def test_admin_gets_detail(self, admin_client, db):
        msg = _make_message(subject='Detalle')
        res = admin_client.get(_admin_detail_url(msg.pk))
        assert res.status_code == 200
        body = res.json()
        assert body['id'] == msg.pk
        assert body['subject'] == 'Detalle'

    def test_admin_detail_returns_404_for_missing(self, admin_client, db):
        res = admin_client.get(_admin_detail_url(999999))
        assert res.status_code == 404


# ─── POST /admin/contact/messages/<id>/read ──────────────────────────────
class TestAdminMarkRead:
    def test_requires_staff(self, auth_client, db):
        msg = _make_message()
        res = auth_client.post(_admin_read_url(msg.pk))
        assert res.status_code == 403

    def test_marks_as_read(self, admin_client, db):
        msg = _make_message(read=False)
        res = admin_client.post(_admin_read_url(msg.pk))
        assert res.status_code == 200
        msg.refresh_from_db()
        assert msg.read is True


# ─── POST /admin/contact/messages/<id>/reply ─────────────────────────────
class TestAdminReply:
    def test_requires_staff(self, auth_client, db):
        msg = _make_message()
        res = auth_client.post(_admin_reply_url(msg.pk),
                               {'reply_body': 'Gracias por tu mensaje.'},
                               format='json')
        assert res.status_code == 403

    def test_reply_records_and_sends_email(self, admin_client, db):
        msg = _make_message(email='destino@example.com',
                            subject='Pregunta sobre envios')
        res = admin_client.post(_admin_reply_url(msg.pk), {
            'reply_body': 'Hola, gracias. Si enviamos a Veracruz.',
        }, format='json')
        assert res.status_code == 200
        body = res.json()
        assert body['replied'] is True
        assert body['read'] is True
        assert body['reply_body'] == 'Hola, gracias. Si enviamos a Veracruz.'

        msg.refresh_from_db()
        assert msg.replied is True
        assert msg.reply_sent_at is not None
        # Outbox should contain the reply.
        assert any(
            'destino@example.com' in m.to and 'Re: Pregunta sobre envios' == m.subject
            for m in mail.outbox
        )

    def test_reply_body_required(self, admin_client, db):
        msg = _make_message()
        res = admin_client.post(_admin_reply_url(msg.pk),
                                {}, format='json')
        assert res.status_code == 400

    def test_reply_returns_404_for_missing(self, admin_client, db):
        res = admin_client.post(_admin_reply_url(999999),
                                {'reply_body': 'Hola'}, format='json')
        assert res.status_code == 404
