"""
Tests de integracion — API v2 F5: logistics, newsletter, contact,
settings/pages, backups, auth §2.1

Verifica los endpoints /api/v2/ para el bloque F5. F7 elimino
la coexistencia v1/v2 — los tests de doble-corrida se removieron.
"""
import pytest
from unittest.mock import patch
from django.core import signing

from addons.mass_mailing import services as mm
from addons.website.models import StaticPage

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
# El prefijo /api/v2/auth/ nunca existió: el alta y el reset viven en
# ``authz_signup``, la cuenta propia en ``portal`` y la sesión en ``web``.
# Ver el triage de rutas y H-API-279.
V2_AUTH_EMAIL_VER    = '/api/v2/authz/verify-email/'      # PENDIENTE (sin módulo de tokens)
V2_AUTH_PWD_RESETS   = '/api/v2/authz/request-reset/'
V2_AUTH_PWD_CONFIRM  = '/api/v2/authz/signup/'            # set-password con token
V2_AUTH_ME           = '/api/v2/portal/deactivations/'
V2_AUTH_SESSIONS     = '/api/v2/web/session/destroy/'


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
        with patch('addons.website_mass_mailing.controllers.subscribe._send_confirmation_email'):
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
        sub = mm.create_pending(email, token)
        r = api_client.post(V2_NEWSLETTER_CONF, {'token': token}, format='json')
        assert r.status_code == 200
        sub.refresh_from_db()
        assert mm.status_of(sub) == 'CONFIRMED'


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
        sub = mm.create_pending('admin_v2@example.com', None)
        sub.confirm()
        r = admin_client.delete(V2_ADMIN_NL_UNSUB(sub.pk))
        assert r.status_code == 200
        sub.refresh_from_db()
        assert mm.status_of(sub) == 'UNSUBSCRIBED'


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


# ─── Reports v2 — RETIRADA, no hay superficie que probar ─────────────────────
#
# ``/api/v2/admin/reports/<slug>/exports/`` no existe y **no se va a crear**.
# Medido sobre ``odoo-tools@622ddc2a``: en todo ``odoo19c:`` no hay una sola
# ``@route`` cuyo path contenga ``report``; el reporte es un **modelo**, no una
# superficie HTTP — ``odoo19c: addons/sale/report/sale_report.py:10`` declara
# ``_auto = False`` (vista SQL de sólo lectura), igual en ``odoo18c:``.
#
# Crear el endpoint sería invención, no adaptación — mismo criterio ya aplicado
# a ``admin/users/*`` en H-API-279. Los dos tests que lo ejercían se eliminan.


# ─── Auth §2.1 v2 ────────────────────────────────────────────────────────────

class TestAuthV2EmailVerifications:
    """PENDIENTE — el módulo de tokens de correo no existe.

    H-API-252 midió ``send_verification_email`` → 0 hits en ``src/``. Estos
    dos quedan rojos a propósito: son el inventario ejecutable del hueco.
    """

    def test_resend_verification(self, api_client, db):
        r = api_client.post(V2_AUTH_EMAIL_VER,
                            {'login': 'nobody@example.com'},
                            format='json')
        assert r.status_code == 200

    def test_invalid_token_returns_400(self, api_client, db):
        r = api_client.post(V2_AUTH_EMAIL_VER,
                            {'token': 'invalid-token'},
                            format='json')
        assert r.status_code == 400


class TestAuthV2PasswordResets:
    """Reset de contraseña — ``authz_signup``.

    El campo es ``login``, no ``email``: la credencial de acceso es el login
    (``ResUsers.USERNAME_FIELD``), y el correo llega delegado del partner.
    """

    def test_request_missing_login_400(self, api_client, db):
        r = api_client.post(V2_AUTH_PWD_RESETS, {}, format='json')
        assert r.status_code == 400

    def test_request_unknown_login_is_silent(self, api_client, db):
        r = api_client.post(V2_AUTH_PWD_RESETS,
                            {'login': 'nobody@example.com'},
                            format='json')
        # 202, no 200: la petición se acepta pero el envío es asíncrono y
        # sólo ocurre si hay cuenta. Mismo código para login inexistente —
        # distinguirlos revelaría qué cuentas existen.
        assert r.status_code == 202

    def test_confirm_missing_fields_400(self, api_client, db):
        r = api_client.post(V2_AUTH_PWD_CONFIRM, {}, format='json')
        assert r.status_code == 400


class TestAuthV2Me:
    """Baja de cuenta — ≙ ``/my/deactivate_account`` de ``odoo19c: portal``."""

    def test_unauthenticated_401(self, api_client):
        # POST, no DELETE: la referencia modela la baja como una ACCIÓN sobre
        # la cuenta (``deactivate_account``), no como el borrado del recurso —
        # ``ResPartner.active`` se apaga, la fila se conserva.
        r = api_client.post(V2_AUTH_ME)
        assert r.status_code == 401


class TestAuthV2Sessions:
    """Cierre de sesión — ``web`` (≙ ``/web/session/destroy``)."""

    def test_unauthenticated_401(self, api_client):
        r = api_client.post(V2_AUTH_SESSIONS)
        assert r.status_code == 401

    def test_authenticated_closes_session(self, auth_client):
        # 204, no 200: cerrar sesión no devuelve cuerpo.
        r = auth_client.post(V2_AUTH_SESSIONS)
        assert r.status_code == 204

