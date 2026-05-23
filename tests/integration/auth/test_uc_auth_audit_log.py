"""
Tests de UserDeactivationEvent (GAP 10 cierre).

Cada transicion is_active=True -> False debe crear UNA fila en
users_deactivation_event con (reason, source, actor) consistentes.
"""
import pytest
from apps.users.models import UserDeactivationEvent
from django.contrib.auth import get_user_model

pytestmark = pytest.mark.api


class TestEventOnRegister:
    """Cuenta nueva -> evento source='register', actor=None."""

    def test_register_crea_evento_unverified(self, api_client, db):
        api_client.post('/api/v1/auth/register/', {
            'email': 'newev@practicayoruba.mx',
            'password': 'Yoruba2026!',
            'password_confirm': 'Yoruba2026!',
            'terms_accepted': True,
        }, format='json')
        events = UserDeactivationEvent.objects.filter(user__email='newev@practicayoruba.mx')
        assert events.count() == 1
        e = events.first()
        assert e.reason == 'unverified'
        assert e.source == 'register'
        assert e.actor is None


class TestEventOnSelfDeactivate:
    """UC-AUTH-16 -> evento source='self', actor=None."""

    def test_self_deactivate_crea_evento(self, auth_client, user):
        auth_client.post(
            '/api/v1/auth/me/deactivate/',
            {'password': 'TestPass123!'},
            format='json',
        )
        events = UserDeactivationEvent.objects.filter(user=user)
        # 1 evento — el de self-delete (los usuarios de fixtures
        # se crean con is_active=True directo, sin pasar por register).
        assert events.count() == 1
        e = events.first()
        assert e.reason == 'self_deleted'
        assert e.source == 'self'
        assert e.actor is None


class TestEventOnAdminSuspend:
    """UC-AUTH-13 -> evento source='admin', actor=admin_user."""

    @pytest.fixture
    def target_user(self, db):
        return get_user_model().objects.create_user(
            username='tgt', email='tgt@practicayoruba.mx',
            password='X', is_active=True,
        )

    def test_admin_suspend_crea_evento(self, admin_auth_client, admin_user, target_user):
        admin_auth_client.post(
            f'/api/v1/admin/users/{target_user.pk}/suspend/',
        )
        events = UserDeactivationEvent.objects.filter(user=target_user)
        assert events.count() == 1
        e = events.first()
        assert e.reason == 'suspended'
        assert e.source == 'admin'
        assert e.actor == admin_user

    def test_admin_suspend_acepta_note_en_payload(
        self, admin_auth_client, admin_user, target_user,
    ):
        admin_auth_client.post(
            f'/api/v1/admin/users/{target_user.pk}/suspend/',
            {'note': 'usuario reporto fraude'},
            format='json',
        )
        e = UserDeactivationEvent.objects.get(user=target_user)
        assert e.note == 'usuario reporto fraude'


class TestEventOrdering:
    """Re-deactivation tras reactivate crea un evento separado."""

    @pytest.fixture
    def target(self, db):
        return get_user_model().objects.create_user(
            username='cycle', email='cycle@practicayoruba.mx',
            password='X', is_active=True,
        )

    def test_dos_suspensiones_consecutivas_crean_dos_eventos(
        self, admin_auth_client, target,
    ):
        admin_auth_client.post(f'/api/v1/admin/users/{target.pk}/suspend/')
        admin_auth_client.post(f'/api/v1/admin/users/{target.pk}/reactivate/')
        admin_auth_client.post(f'/api/v1/admin/users/{target.pk}/suspend/')
        events = UserDeactivationEvent.objects.filter(user=target).order_by('created_at')
        # 2 events de suspend (la reactivate NO se loguea aqui).
        assert events.count() == 2
        assert all(e.source == 'admin' for e in events)
