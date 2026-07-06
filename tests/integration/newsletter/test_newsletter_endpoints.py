"""
Tests — Newsletter endpoints (UC-NEW-01..04)

Public:
  POST /api/v2/newsletter/subscribe/
  POST /api/v2/newsletter/subscriptions/confirmations/<token>/
  POST /api/v2/newsletter/unsubscribe/

Admin:
  GET  /api/v2/admin/newsletter/subscribers/
  POST /api/v2/admin/newsletter/subscribers/<id>/unsubscribe/
  POST /api/v2/admin/newsletter/campaigns/

JSON keys + identifiers in English (DEC-DOC-005).
"""
import time
from unittest.mock import patch

import pytest
from apps.newsletter.models import NewsletterSubscriber
from django.core import mail, signing

pytestmark = pytest.mark.integration

SUBSCRIBE_URL = '/api/v2/newsletter/subscriptions/'
CONFIRM_URL = '/api/v2/newsletter/subscriptions/confirmations/'
UNSUB_URL = '/api/v2/newsletter/subscriptions/'
ADMIN_LIST_URL = '/api/v2/admin/newsletter/subscribers/'
ADMIN_CAMPAIGN_URL = '/api/v2/admin/newsletter/campaigns/'


def _admin_force_unsub_url(pk):
    return f'/api/v2/admin/newsletter/subscribers/{pk}/unsubscribe/'


def _make_subscriber(email='sub@example.com', status='CONFIRMED'):
    return NewsletterSubscriber.objects.create(email=email, status=status)


# ─── POST /newsletter/subscribe ──────────────────────────────────────────
class TestSubscribe:
    def test_anonymous_can_subscribe(self, api_client, db):
        res = api_client.post(SUBSCRIBE_URL,
                              {'email': 'nuevo@example.com'},
                              format='json')
        assert res.status_code == 201
        body = res.json()
        assert body['email'] == 'nuevo@example.com'
        assert body['status'] == 'PENDING'

        assert NewsletterSubscriber.objects.filter(
            email='nuevo@example.com',
        ).count() == 1

    def test_invalid_email_rejected(self, api_client, db):
        res = api_client.post(SUBSCRIBE_URL,
                              {'email': 'no-es-email'},
                              format='json')
        assert res.status_code == 400

    def test_duplicate_email_returns_200_idempotent(self, api_client, db):
        _make_subscriber('repe@example.com', status='CONFIRMED')
        res = api_client.post(SUBSCRIBE_URL,
                              {'email': 'repe@example.com'},
                              format='json')
        assert res.status_code == 200
        assert res.json()['status'] == 'CONFIRMED'

    def test_reopt_in_from_unsubscribed_goes_to_pending(self, api_client, db):
        _make_subscriber('back@example.com', status='UNSUBSCRIBED')
        res = api_client.post(SUBSCRIBE_URL,
                              {'email': 'back@example.com'},
                              format='json')
        assert res.status_code == 200
        assert res.json()['status'] == 'PENDING'


# ─── POST /newsletter/subscriptions/confirmations/<token> ────────────────────────────────────
class TestConfirmSubscription:
    def test_confirm_valid_token(self, api_client, db):
        email = 'pending@example.com'
        token = signing.dumps(email, salt='newsletter-confirm')
        sub = NewsletterSubscriber.objects.create(
            email=email,
            status='PENDING',
            confirmation_token=token,
        )

        res = api_client.post(CONFIRM_URL, {'token': token}, format='json')
        assert res.status_code == 200
        body = res.json()
        assert body['status'] == 'CONFIRMED'
        assert body['email'] == email

        sub.refresh_from_db()
        assert sub.status == 'CONFIRMED'
        assert sub.confirmed_at is not None
        assert sub.confirmation_token is None

    def test_confirm_invalid_token_returns_400(self, api_client, db):
        res = api_client.post(CONFIRM_URL, {'token': 'not-a-valid-signed-token'}, format='json')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'INVALID_TOKEN'

    def test_confirm_expired_token_returns_400(self, api_client, db):
        email = 'expire@example.com'
        past = time.time() - 25 * 3600  # 25 hours ago — beyond 24h TTL
        with patch('time.time', return_value=past):
            expired_token = signing.dumps(email, salt='newsletter-confirm')
        NewsletterSubscriber.objects.create(
            email=email,
            status='PENDING',
            confirmation_token=expired_token,
        )

        res = api_client.post(CONFIRM_URL, {'token': expired_token}, format='json')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'TOKEN_EXPIRED'

    def test_confirm_already_confirmed_idempotent(self, api_client, db):
        email = 'already@example.com'
        token = signing.dumps(email, salt='newsletter-confirm')
        NewsletterSubscriber.objects.create(
            email=email,
            status='CONFIRMED',
            confirmation_token=None,
        )
        # Token signature is valid but confirmation_token cleared — returns 400
        res = api_client.post(CONFIRM_URL, {'token': token}, format='json')
        assert res.status_code == 400

    def test_confirm_subscribe_sends_confirmation_email(self, api_client, db):
        mail.outbox.clear()
        res = api_client.post(SUBSCRIBE_URL, {'email': 'newemail@example.com'}, format='json')
        assert res.status_code == 201
        # Give thread pool a moment to deliver
        time.sleep(0.1)
        subjects = [m.subject for m in mail.outbox]
        assert any('Confirma' in s for s in subjects)


# ─── POST /newsletter/unsubscribe ────────────────────────────────────────
class TestUnsubscribe:
    def test_invalid_token_returns_404(self, api_client, db):
        res = api_client.delete(UNSUB_URL,
                                data={'token': 'no-existe-este-token-12345678'},
                                format='json')
        assert res.status_code == 404
        assert res.json()['codigo_error'] == 'INVALID_TOKEN'

    def test_expired_token_returns_400(self, api_client, db):
        past = time.time() - 31 * 24 * 3600  # 31 days ago — beyond 30d TTL
        with patch('time.time', return_value=past):
            expired_token = signing.dumps('x' * 16, salt='newsletter-unsub')
        sub = _make_subscriber('expired@example.com', status='CONFIRMED')
        sub.unsubscribe_token = expired_token
        sub.save(update_fields=['unsubscribe_token'])

        res = api_client.delete(UNSUB_URL, data={'token': expired_token}, format='json')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'TOKEN_EXPIRED'

    def test_valid_token_unsubscribes(self, api_client, db):
        sub = _make_subscriber('out@example.com', status='CONFIRMED')
        res = api_client.delete(UNSUB_URL,
                                data={'token': sub.unsubscribe_token},
                                format='json')
        assert res.status_code == 200
        body = res.json()
        assert body['status'] == 'UNSUBSCRIBED'

        sub.refresh_from_db()
        assert sub.status == 'UNSUBSCRIBED'
        assert sub.unsubscribed_at is not None

    def test_token_required(self, api_client, db):
        res = api_client.delete(UNSUB_URL, data={}, format='json')
        assert res.status_code == 400


# ─── GET /admin/newsletter/subscribers ───────────────────────────────────
class TestAdminListSubscribers:
    def test_requires_auth(self, api_client, db):
        res = api_client.get(ADMIN_LIST_URL)
        assert res.status_code == 401

    def test_requires_staff(self, auth_client, db):
        res = auth_client.get(ADMIN_LIST_URL)
        assert res.status_code == 403

    def test_admin_lists_all(self, admin_client, db):
        _make_subscriber('a@example.com', status='CONFIRMED')
        _make_subscriber('b@example.com', status='PENDING')
        res = admin_client.get(ADMIN_LIST_URL)
        assert res.status_code == 200
        body = res.json()
        assert 'results' in body
        assert len(body['results']) == 2

    def test_admin_filter_by_status(self, admin_client, db):
        _make_subscriber('c@example.com', status='CONFIRMED')
        _make_subscriber('d@example.com', status='PENDING')
        res = admin_client.get(ADMIN_LIST_URL + '?status=CONFIRMED')
        assert res.status_code == 200
        rows = res.json()['results']
        assert len(rows) == 1
        assert rows[0]['email'] == 'c@example.com'


# ─── POST /admin/newsletter/subscribers/<id>/unsubscribe ─────────────────
class TestAdminForceUnsubscribe:
    def test_requires_staff(self, auth_client, db):
        sub = _make_subscriber()
        res = auth_client.post(_admin_force_unsub_url(sub.pk))
        assert res.status_code == 403

    def test_admin_force_unsubscribes(self, admin_client, db):
        sub = _make_subscriber('force@example.com', status='CONFIRMED')
        res = admin_client.post(_admin_force_unsub_url(sub.pk))
        assert res.status_code == 200
        assert res.json()['status'] == 'UNSUBSCRIBED'
        sub.refresh_from_db()
        assert sub.status == 'UNSUBSCRIBED'

    def test_admin_force_unsub_returns_404_for_missing(self, admin_client, db):
        res = admin_client.post(_admin_force_unsub_url(999999))
        assert res.status_code == 404


# ─── POST /admin/newsletter/campaigns ────────────────────────────────────
class TestAdminCreateCampaign:
    def test_requires_staff(self, auth_client, db):
        res = auth_client.post(ADMIN_CAMPAIGN_URL, {
            'subject': 'Promo de mayo',
            'body': 'Hola, hay promo.',
        }, format='json')
        assert res.status_code == 403

    def test_admin_creates_and_sends_campaign(self, admin_client, db):
        _make_subscriber('uno@example.com', status='CONFIRMED')
        _make_subscriber('dos@example.com', status='CONFIRMED')
        _make_subscriber('pendiente@example.com', status='PENDING')

        res = admin_client.post(ADMIN_CAMPAIGN_URL, {
            'subject': 'Promo de mayo',
            'body': 'Hola, hay promo!',
        }, format='json')
        assert res.status_code == 201
        body = res.json()
        for key in ('id', 'subject', 'audience_filter',
                    'recipients_count', 'sent_at'):
            assert key in body
        assert body['recipients_count'] == 2
        assert body['audience_filter'] == 'CONFIRMED'

        # Outbox contiene un envio con dos destinatarios.
        targets = []
        for m in mail.outbox:
            if m.subject == 'Promo de mayo':
                targets.extend(m.to)
        assert 'uno@example.com' in targets
        assert 'dos@example.com' in targets
        assert 'pendiente@example.com' not in targets

    def test_campaign_enqueues_via_dispatch_email_not_inline(self, admin_client, db):
        """UC-NEW-04: el envío de campaña ENCOLA vía dispatch_email
        (cola async EmailTask + cron), NO un loop síncrono de
        mail.send_mail en el request. Se verifica que la view invoca
        dispatch_email una vez por destinatario CONFIRMED."""
        _make_subscriber('uno@example.com', status='CONFIRMED')
        _make_subscriber('dos@example.com', status='CONFIRMED')
        _make_subscriber('pendiente@example.com', status='PENDING')

        with patch('apps.newsletter.views.dispatch_email') as mock_dispatch:
            res = admin_client.post(ADMIN_CAMPAIGN_URL, {
                'subject': 'Campaña async',
                'body': 'Hola, esto se encola.',
            }, format='json')

        assert res.status_code == 201
        # Un dispatch_email por destinatario CONFIRMED (2), ninguno para PENDING.
        assert mock_dispatch.call_count == 2
        queued = []
        for call in mock_dispatch.call_args_list:
            queued.extend(call.kwargs['recipient_list'])
        assert 'uno@example.com' in queued
        assert 'dos@example.com' in queued
        assert 'pendiente@example.com' not in queued
        # El contrato HTTP responde inmediatamente con la campaña creada.
        assert res.json()['recipients_count'] == 2

    def test_subject_and_body_required(self, admin_client, db):
        res = admin_client.post(ADMIN_CAMPAIGN_URL, {}, format='json')
        assert res.status_code == 400

    def test_empty_audience_rejected_no_recipients(self, admin_client, db):
        # UC-NEW-04 (D-4): un segmento sin destinatarios se rechaza con
        # 422 NO_RECIPIENTS en lugar de crear una campana no-op.
        res = admin_client.post(ADMIN_CAMPAIGN_URL, {
            'subject': 'Promo de junio',
            'body': 'Sin destinatarios todavia.',
        }, format='json')
        assert res.status_code == 422
        assert res.json()['codigo_error'] == 'NO_RECIPIENTS'
