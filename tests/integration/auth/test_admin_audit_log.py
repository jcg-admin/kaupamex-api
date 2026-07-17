"""
Tests de integracion — Audit Log admin (UC-ADM-03)
T-119: AuditLogView — GET /api/v2/admin/audit-log/
"""
import pytest
from django.contrib.auth import get_user_model
from addons.users.models import AuthEvent, BusinessEvent, UserDeactivationEvent

pytestmark = pytest.mark.integration

AUDIT_LOG_URL = '/api/v2/admin/audit-log/'

User = get_user_model()


@pytest.fixture
def audit_data(db, admin_user):
    """Crea registros en los tres modelos de audit log."""
    buyer = User.objects.create_user(
        email='buyer_audit@test.mx',
        password='Pass123!', is_active=True,
    )
    AuthEvent.objects.create(
        user=buyer,
        action=AuthEvent.ACTION_LOGIN_SUCCESS,
        ip_addr='127.0.0.1',
    )
    AuthEvent.objects.create(
        user=buyer,
        action=AuthEvent.ACTION_LOGIN_FAIL,
        ip_addr='127.0.0.1',
        reason=AuthEvent.REASON_BAD_CREDS,
    )
    BusinessEvent.objects.create(
        actor=buyer,
        action=BusinessEvent.ACTION_ORDER_CREATED,
        target_type='order',
        target_id=1,
    )
    UserDeactivationEvent.objects.create(
        user=buyer,
        reason=User.DEACTIVATION_SUSPENDED,
        source=UserDeactivationEvent.SOURCE_ADMIN,
        actor=admin_user,
    )
    return buyer


class TestAdminAuditLog:

    def test_admin_puede_ver_audit_log(self, admin_auth_client, audit_data, db):
        r = admin_auth_client.get(AUDIT_LOG_URL)
        assert r.status_code == 200

    def test_comprador_no_puede_ver_audit_log(self, auth_client, audit_data, db):
        r = auth_client.get(AUDIT_LOG_URL)
        assert r.status_code == 403

    def test_sin_autenticar_retorna_401(self, api_client, db):
        r = api_client.get(AUDIT_LOG_URL)
        assert r.status_code == 401

    def test_respuesta_paginada(self, admin_auth_client, audit_data, db):
        r = admin_auth_client.get(AUDIT_LOG_URL)
        data = r.json()
        assert 'count' in data
        assert 'page' in data
        assert 'pages' in data
        assert 'results' in data
        assert isinstance(data['results'], list)

    def test_filtro_event_type_auth(self, admin_auth_client, audit_data, db):
        r = admin_auth_client.get(AUDIT_LOG_URL, {'event_type': 'auth'})
        data = r.json()
        assert data['count'] >= 2
        for item in data['results']:
            assert item['event_type'] == 'auth'

    def test_filtro_event_type_business(self, admin_auth_client, audit_data, db):
        r = admin_auth_client.get(AUDIT_LOG_URL, {'event_type': 'business'})
        for item in r.json()['results']:
            assert item['event_type'] == 'business'

    def test_filtro_event_type_deactivation(self, admin_auth_client, audit_data, db):
        r = admin_auth_client.get(AUDIT_LOG_URL, {'event_type': 'deactivation'})
        for item in r.json()['results']:
            assert item['event_type'] == 'deactivation'

    def test_filtro_user_id(self, admin_auth_client, audit_data, db):
        r = admin_auth_client.get(AUDIT_LOG_URL, {'user_id': audit_data.pk})
        data = r.json()
        assert data['count'] >= 1
        for item in data['results']:
            assert item['user_id'] == audit_data.pk

    def test_campos_retornados(self, admin_auth_client, audit_data, db):
        r = admin_auth_client.get(AUDIT_LOG_URL)
        item = r.json()['results'][0]
        for field in ['id', 'event_type', 'user_id', 'username', 'action', 'created_at', 'extra']:
            assert field in item
