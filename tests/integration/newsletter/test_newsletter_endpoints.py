"""
Tests — Newsletter endpoints (UC-NEW-01..04)

Public:
  POST /api/v1/newsletter/subscribe/
  POST /api/v1/newsletter/unsubscribe/

Admin:
  GET  /api/v1/admin/newsletter/subscribers/
  POST /api/v1/admin/newsletter/subscribers/<id>/unsubscribe/
  POST /api/v1/admin/newsletter/campaigns/

JSON keys + identifiers in English (DEC-DOC-005).
"""
import pytest

pytestmark = pytest.mark.integration

SUBSCRIBE_URL = '/api/v1/newsletter/subscribe/'
UNSUB_URL = '/api/v1/newsletter/unsubscribe/'
ADMIN_LIST_URL = '/api/v1/admin/newsletter/subscribers/'
ADMIN_CAMPAIGN_URL = '/api/v1/admin/newsletter/campaigns/'


def _admin_force_unsub_url(pk):
    return f'/api/v1/admin/newsletter/subscribers/{pk}/unsubscribe/'


def _make_subscriber(email='sub@example.com', status='CONFIRMED'):
    from apps.newsletter.models import NewsletterSubscriber
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

        from apps.newsletter.models import NewsletterSubscriber
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


# ─── POST /newsletter/unsubscribe ────────────────────────────────────────
class TestUnsubscribe:
    def test_invalid_token_returns_404(self, api_client, db):
        res = api_client.post(UNSUB_URL,
                              {'token': 'no-existe-este-token-12345678'},
                              format='json')
        assert res.status_code == 404

    def test_valid_token_unsubscribes(self, api_client, db):
        sub = _make_subscriber('out@example.com', status='CONFIRMED')
        res = api_client.post(UNSUB_URL,
                              {'token': sub.unsubscribe_token},
                              format='json')
        assert res.status_code == 200
        body = res.json()
        assert body['status'] == 'UNSUBSCRIBED'

        sub.refresh_from_db()
        assert sub.status == 'UNSUBSCRIBED'
        assert sub.unsubscribed_at is not None

    def test_token_required(self, api_client, db):
        res = api_client.post(UNSUB_URL, {}, format='json')
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
        from django.core import mail
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

    def test_subject_and_body_required(self, admin_client, db):
        res = admin_client.post(ADMIN_CAMPAIGN_URL, {}, format='json')
        assert res.status_code == 400

    def test_empty_audience_creates_with_zero_recipients(self, admin_client, db):
        res = admin_client.post(ADMIN_CAMPAIGN_URL, {
            'subject': 'Promo de junio',
            'body': 'Sin destinatarios todavia.',
        }, format='json')
        assert res.status_code == 201
        assert res.json()['recipients_count'] == 0
