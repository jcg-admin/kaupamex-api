"""
Tests — UC-AUTH-17 (H-16): sesiones activas del comprador.

GET  /api/v2/auth/sessions/active/        lista sesiones vivas del usuario
POST /api/v2/auth/sessions/<pk>/revoke/   cierra una sesión específica
"""
import pytest
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session

from addons.users.models import UserSession

pytestmark = pytest.mark.integration

LIST_URL = '/api/v2/auth/sessions/active/'


def _make_django_session():
    s = SessionStore()
    s['v'] = 1
    s.save()
    return s.session_key


@pytest.fixture
def session_row(user, db):
    key = _make_django_session()
    return UserSession.objects.create(
        user=user, session_key=key, ip_address='1.2.3.4',
        user_agent='Mozilla/5.0 (Windows NT 10.0) Chrome/120.0',
    )


class TestSessionList:
    def test_requires_auth(self, api_client, db):
        assert api_client.get(LIST_URL).status_code in (401, 403)

    def test_lists_own_active_sessions(self, auth_client, session_row, db):
        res = auth_client.get(LIST_URL)
        assert res.status_code == 200
        body = res.json()
        assert body['count'] == 1
        row = body['results'][0]
        assert row['ip_address'] == '1.2.3.4'
        assert 'Chrome' in row['device'] and 'Windows' in row['device']
        # RNF-SEC-003 / BR-013: no se expone el session_key.
        assert 'session_key' not in row

    def test_excludes_sessions_without_django_session(self, auth_client, user, db):
        # UserSession cuyo django_session ya no existe (expiró/cerró) no se lista.
        UserSession.objects.create(
            user=user, session_key='deadkey-no-django-session',
            ip_address='9.9.9.9', user_agent='x',
        )
        assert auth_client.get(LIST_URL).json()['count'] == 0


class TestSessionRevoke:
    def test_revoke_own_session(self, auth_client, session_row, db):
        key = session_row.session_key
        res = auth_client.post(f'/api/v2/auth/sessions/{session_row.pk}/revoke/')
        assert res.status_code == 204
        assert not UserSession.objects.filter(pk=session_row.pk).exists()
        assert not Session.objects.filter(session_key=key).exists()

    def test_revoke_other_user_returns_404(self, auth_client, admin_user, db):
        key = _make_django_session()
        other = UserSession.objects.create(
            user=admin_user, session_key=key, ip_address='2.2.2.2', user_agent='x',
        )
        res = auth_client.post(f'/api/v2/auth/sessions/{other.pk}/revoke/')
        assert res.status_code == 404
        assert UserSession.objects.filter(pk=other.pk).exists()
