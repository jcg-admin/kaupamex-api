"""
Tests de integracion — API v2 F5: logistics, newsletter, contact,
settings/pages, backups, reports, auth §2.1

Verifica los endpoints /api/v2/ para el bloque F5. F7 elimino
la coexistencia v1/v2 — los tests de doble-corrida se removieron.
"""
import pytest
from unittest.mock import patch
from django.core import signing

from addons.newsletter.models import NewsletterSubscriber
from addons.settings_app.models import StaticPage

pytestmark = pytest.mark.integration

# ─── URLs v2 F5 ──────────────────────────────────────────────────────────────
V2_SHIPMENTS         = '/api/v2/shipments/'
V2_NEWSLETTER_SUBS   = '/api/v2/newsletter/subscriptions/'
V2_NEWSLETTER_CONF   = '/api/v2/newsletter/subscriptions/confirmations/'
V2_ADMIN_NL_UNSUB    = lambda pk: f'/api/v2/admin/newsletter/subscribers/{pk}/subscription/'
V2_ADMIN_CONTACT_MSG = lambda pk: f'/api/v2/admin/contact/messages/{pk}/'
V2_ADMIN_CONTACT_REP = lambda pk: f'/api/v2/admin/contact/messages/{pk}/replies/'
V2_ADMIN_PAGE_STATUS = lambda slug: f'/api/v2/admin/pages/{slug}/status/'
V2_ADMIN_PAGE_REST   = lambda slug: f'/api/v2/admin/pages/{slug}/restorations/'
V2_ADMIN_BACKUPS     = '/api/v2/admin/backups/'
V2_ADMIN_REPORT_EXP  = lambda slug: f'/api/v2/admin/reports/{slug}/exports/'
V2_AUTH_EMAIL_VER    = '/api/v2/auth/email-verifications/'
V2_AUTH_PWD_RESETS   = '/api/v2/auth/password-resets/'
V2_AUTH_PWD_CONFIRM  = '/api/v2/auth/password-resets/confirm/'
V2_AUTH_ME           = '/api/v2/auth/me/'
V2_AUTH_SESSIONS     = '/api/v2/auth/sessions/'


# ─── Logistics / Shipments ───────────────────────────────────────────────────

class TestShipmentsV2Auth:
    def test_list_unauthenticated_401(self, api_client):
        r = api_client.get(V2_SHIPMENTS)
        assert r.status_code == 401

    def test_list_non_admin_403(self, auth_client):
        r = auth_client.get(V2_SHIPMENTS)
        assert r.status_code == 403

    def test_list_admin_200(self, admin_client):
        r = admin_client.get(V2_SHIPMENTS)
        assert r.status_code == 200

    def test_detail_unauthenticated_401(self, api_client):
        r = api_client.get('/api/v2/shipments/99999/')
        assert r.status_code == 401

    def test_detail_nonexistent_404(self, admin_client):
        r = admin_client.get('/api/v2/shipments/99999/')
        assert r.status_code == 404

    def test_cancellations_unauthenticated_401(self, api_client):
        r = api_client.post('/api/v2/shipments/1/cancellations/', {})
        assert r.status_code == 401

    def test_deliveries_unauthenticated_401(self, api_client):
        r = api_client.post('/api/v2/shipments/1/deliveries/', {})
        assert r.status_code == 401

    def test_problem_report_unauthenticated_401(self, api_client):
        r = api_client.post('/api/v2/shipments/1/problem-reports/', {})
        assert r.status_code == 401

    def test_problem_report_nonexistent_shipment_404(self, auth_client):
        r = auth_client.post('/api/v2/shipments/99999/problem-reports/', {})
        assert r.status_code == 404

    def test_order_shipment_unauthenticated_401(self, api_client):
        r = api_client.get('/api/v2/orders/1/shipment/')
        assert r.status_code == 401


# ─── Newsletter v2 ───────────────────────────────────────────────────────────

class TestNewsletterSubscriptionsV2:
    def test_subscribe_201(self, api_client, db):
        with patch('addons.newsletter.views._send_confirmation_email'):
            r = api_client.post(V2_NEWSLETTER_SUBS,
                                {'email': 'v2test@example.com'},
                                format='json')
        assert r.status_code == 201
        assert r.json()['email'] == 'v2test@example.com'

    def test_unsubscribe_delete_requires_token(self, api_client, db):
        r = api_client.delete(V2_NEWSLETTER_SUBS,
                              {'token': 'invalid'},
                              format='json')
        assert r.status_code == 400

    def test_confirm_missing_token_400(self, api_client, db):
        r = api_client.post(V2_NEWSLETTER_CONF, {}, format='json')
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'TOKEN_REQUIRED'

    def test_confirm_invalid_token_400(self, api_client, db):
        r = api_client.post(V2_NEWSLETTER_CONF,
                            {'token': 'bad-token'},
                            format='json')
        assert r.status_code == 400

    def test_confirm_valid_token(self, api_client, db):
        email = 'confirm_v2@example.com'
        token = signing.dumps(email, salt='newsletter-confirm')
        sub = NewsletterSubscriber.objects.create(
            email=email,
            status='PENDING',
            confirmation_token=token,
        )
        r = api_client.post(V2_NEWSLETTER_CONF, {'token': token}, format='json')
        assert r.status_code == 200
        sub.refresh_from_db()
        assert sub.status == 'CONFIRMED'


class TestAdminNewsletterV2:
    def test_unsub_delete_unauthenticated_401(self, api_client):
        r = api_client.delete(V2_ADMIN_NL_UNSUB(1))
        assert r.status_code == 401

    def test_unsub_delete_non_admin_403(self, auth_client):
        r = auth_client.delete(V2_ADMIN_NL_UNSUB(1))
        assert r.status_code == 403

    def test_unsub_delete_nonexistent_404(self, admin_client, db):
        r = admin_client.delete(V2_ADMIN_NL_UNSUB(99999))
        assert r.status_code == 404

    def test_unsub_delete_confirmed_subscriber(self, admin_client, db):
        sub = NewsletterSubscriber.objects.create(
            email='admin_v2@example.com', status='CONFIRMED',
        )
        r = admin_client.delete(V2_ADMIN_NL_UNSUB(sub.pk))
        assert r.status_code == 200
        sub.refresh_from_db()
        assert sub.status == 'UNSUBSCRIBED'


# ─── Contact admin v2 ────────────────────────────────────────────────────────

class TestContactAdminV2:
    def test_patch_read_unauthenticated_401(self, api_client):
        r = api_client.patch(V2_ADMIN_CONTACT_MSG(1), {'is_read': True})
        assert r.status_code == 401

    def test_patch_read_non_admin_403(self, auth_client):
        r = auth_client.patch(V2_ADMIN_CONTACT_MSG(1), {'is_read': True})
        assert r.status_code == 403

    def test_patch_read_missing_field_400(self, admin_client):
        r = admin_client.patch(V2_ADMIN_CONTACT_MSG(1), {}, format='json')
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'INVALID_PAYLOAD'

    def test_reply_unauthenticated_401(self, api_client):
        r = api_client.post(V2_ADMIN_CONTACT_REP(1), {})
        assert r.status_code == 401


# ─── Settings/pages v2 ───────────────────────────────────────────────────────

class TestStaticPagesV2:
    def test_status_unauthenticated_401(self, api_client):
        r = api_client.patch(V2_ADMIN_PAGE_STATUS('home'), {})
        assert r.status_code == 401

    def test_status_non_admin_403(self, auth_client):
        r = auth_client.patch(V2_ADMIN_PAGE_STATUS('home'), {})
        assert r.status_code == 403

    def test_restoration_unauthenticated_401(self, api_client):
        r = api_client.post(V2_ADMIN_PAGE_REST('home'), {})
        assert r.status_code == 401

    def test_restoration_missing_version_400(self, admin_client, db):
        page = StaticPage.objects.create(slug='home', title='Home')
        r = admin_client.post(V2_ADMIN_PAGE_REST('home'), {}, format='json')
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'VERSION_REQUIRED'
        page.delete()

    def test_restoration_invalid_version_400(self, admin_client, db):
        page = StaticPage.objects.create(slug='home2', title='Home2')
        r = admin_client.post(V2_ADMIN_PAGE_REST('home2'),
                              {'version': 'abc'}, format='json')
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'INVALID_VERSION'
        page.delete()


# ─── Backups v2 ──────────────────────────────────────────────────────────────

class TestBackupsV2:
    def test_trigger_unauthenticated_401(self, api_client):
        r = api_client.post(V2_ADMIN_BACKUPS, {})
        assert r.status_code == 401

    def test_trigger_non_admin_403(self, auth_client):
        r = auth_client.post(V2_ADMIN_BACKUPS, {})
        assert r.status_code == 403


# ─── Reports v2 ──────────────────────────────────────────────────────────────

class TestReportsV2:
    def test_export_unauthenticated_401(self, api_client):
        r = api_client.post(V2_ADMIN_REPORT_EXP('sales'), {})
        assert r.status_code == 401

    def test_export_non_admin_403(self, auth_client):
        r = auth_client.post(V2_ADMIN_REPORT_EXP('sales'), {})
        assert r.status_code == 403


# ─── Auth §2.1 v2 ────────────────────────────────────────────────────────────

class TestAuthV2EmailVerifications:
    def test_no_token_routes_to_resend_200(self, api_client, db):
        r = api_client.post(V2_AUTH_EMAIL_VER,
                            {'email': 'nobody@example.com'},
                            format='json')
        # No 'token' key → resend path; unknown email → silent 200 (anti-enum)
        assert r.status_code == 200

    def test_token_key_routes_to_verify_invalid_400(self, api_client, db):
        r = api_client.post(V2_AUTH_EMAIL_VER,
                            {'token': 'invalid-token'},
                            format='json')
        assert r.status_code == 400


class TestAuthV2PasswordResets:
    def test_request_missing_email_400(self, api_client, db):
        r = api_client.post(V2_AUTH_PWD_RESETS, {}, format='json')
        assert r.status_code == 400

    def test_request_valid_email_200(self, api_client, db):
        r = api_client.post(V2_AUTH_PWD_RESETS,
                            {'email': 'nobody@example.com'},
                            format='json')
        # silent OK even if email not found (anti-enumeration)
        assert r.status_code == 200

    def test_confirm_missing_fields_400(self, api_client, db):
        r = api_client.post(V2_AUTH_PWD_CONFIRM, {}, format='json')
        assert r.status_code == 400


class TestAuthV2Me:
    def test_delete_unauthenticated_401(self, api_client):
        r = api_client.delete(V2_AUTH_ME)
        assert r.status_code == 401


class TestAuthV2Sessions:
    def test_delete_unauthenticated_401(self, api_client):
        r = api_client.delete(V2_AUTH_SESSIONS)
        assert r.status_code == 401

    def test_delete_authenticated_200(self, auth_client):
        r = auth_client.delete(V2_AUTH_SESSIONS)
        assert r.status_code == 200

