"""
Tests integration — AuthEvent audit log (D-09, D-10, D-19, D-25).

Cubre audit-log-eventos-auth: login/logout/refresh emiten
AuthEvent. last_login se actualiza al hacer login (D-09).
"""
import pytest
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken
from apps.users.models import AuthEvent

# transaction=True para que transaction.on_commit (DEC-AL-4)
# se ejecute durante el test. Default django_db usa atomic
# rollback que swallows on_commit callbacks.
pytestmark = [pytest.mark.integration, pytest.mark.django_db(transaction=True)]


class TestLoginAuditEvent:
    """POST /api/v1/auth/login/ emite LOGIN_SUCCESS o LOGIN_FAIL."""

    def test_login_exitoso_emite_login_success(self, api_client, user):
        url = reverse('users:login')
        r = api_client.post(url, {
            'username': user.username,
            'password': 'TestPass123!',
        }, format='json')
        assert r.status_code == 200

        ev = AuthEvent.objects.filter(
            user=user, action=AuthEvent.ACTION_LOGIN_SUCCESS,
        ).first()
        assert ev is not None, 'AuthEvent LOGIN_SUCCESS no fue creado'

    def test_login_fallido_emite_login_fail(self, api_client, user):
        url = reverse('users:login')
        r = api_client.post(url, {
            'username': user.username,
            'password': 'WrongPassword!',
        }, format='json')
        assert r.status_code == 401

        ev = AuthEvent.objects.filter(
            action=AuthEvent.ACTION_LOGIN_FAIL,
        ).order_by('-created_at').first()
        assert ev is not None
        assert ev.reason == AuthEvent.REASON_BAD_CREDS

    def test_login_actualiza_last_login_d09(self, api_client, user):
        prev = user.last_login
        url = reverse('users:login')
        r = api_client.post(url, {
            'username': user.username,
            'password': 'TestPass123!',
        }, format='json')
        assert r.status_code == 200
        user.refresh_from_db()
        assert user.last_login is not None
        assert user.last_login != prev, 'last_login no fue actualizado'


class TestLogoutAuditEvent:
    """POST /api/v1/auth/logout/ emite LOGOUT."""

    def test_logout_emite_logout(self, api_client, user):
        refresh = RefreshToken.for_user(user)
        url = reverse('users:logout')
        r = api_client.post(url, {'refresh': str(refresh)}, format='json')
        assert r.status_code == 200

        ev = AuthEvent.objects.filter(
            action=AuthEvent.ACTION_LOGOUT,
        ).order_by('-created_at').first()
        assert ev is not None


class TestRefreshAuditEvent:
    """POST /api/v1/auth/refresh/ emite REFRESH_SUCCESS o REFRESH_FAIL."""

    def test_refresh_exitoso_emite_refresh_success(self, api_client, user):
        refresh = RefreshToken.for_user(user)
        url = reverse('users:token-refresh')
        r = api_client.post(url, {'refresh': str(refresh)}, format='json')
        assert r.status_code == 200

        ev = AuthEvent.objects.filter(
            user=user, action=AuthEvent.ACTION_REFRESH_SUCCESS,
        ).first()
        assert ev is not None

    def test_refresh_user_inactivo_emite_refresh_fail_account_inactive(self, api_client, user):
        refresh = RefreshToken.for_user(user)
        user.is_active = False
        user.save(update_fields=['is_active'])

        url = reverse('users:token-refresh')
        r = api_client.post(url, {'refresh': str(refresh)}, format='json')
        assert r.status_code == 401

        ev = AuthEvent.objects.filter(
            user=user, action=AuthEvent.ACTION_REFRESH_FAIL,
            reason=AuthEvent.REASON_ACCOUNT_INACTIVE,
        ).first()
        assert ev is not None


class TestAuditEventPIISafe:
    """DEC-AL-3: ningun password/token en el payload."""

    def test_extra_json_no_contiene_password_ni_token(self, api_client, user):
        url = reverse('users:login')
        r = api_client.post(url, {
            'username': user.username,
            'password': 'TestPass123!',
        }, format='json')
        assert r.status_code == 200

        for ev in AuthEvent.objects.all():
            extra = str(ev.extra_json or {}).lower()
            assert 'password' not in extra, f'password leak en extra_json: {extra}'
            assert 'testpass' not in extra
            assert 'refresh' not in extra or 'refresh' in str(ev.action).lower()
