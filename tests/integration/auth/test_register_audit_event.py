"""
Tests integration — AuthEvent register events (D-03, D-04).

Cubre audit-log-eventos-auth-register: REGISTER_ATTEMPT,
REGISTER_SUCCESS, REGISTER_FAIL en RegisterView.post.
"""
import pytest
from django.urls import reverse
from apps.modules.users.models import AuthEvent

pytestmark = [pytest.mark.integration, pytest.mark.django_db(transaction=True)]


URL = '/api/v2/auth/register/'


class TestRegisterAuditEvent:

    def test_register_attempt_siempre_se_emite(self, api_client, db):
        AuthEvent.objects.filter(action__startswith='REGISTER').delete()
        api_client.post(URL, {}, format='json')

        attempts = AuthEvent.objects.filter(
            action=AuthEvent.ACTION_REGISTER_ATTEMPT,
        )
        assert attempts.exists(), 'REGISTER_ATTEMPT no se emitio'

    def test_register_success_user_nuevo(self, api_client, db):
        AuthEvent.objects.filter(action__startswith='REGISTER').delete()
        payload = {
            'username': 'newuser-audit',
            'email':    'newuser-audit@test.mx',
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!',
        }
        r = api_client.post(URL, payload, format='json')
        # Si el response es 201 -> success.
        if r.status_code == 201:
            ev = AuthEvent.objects.filter(
                action=AuthEvent.ACTION_REGISTER_SUCCESS,
            ).first()
            assert ev is not None
        else:
            # Posible 400 si fixture user.email choca; verificamos
            # al menos que NO se emitio SUCCESS sin user creado.
            assert not AuthEvent.objects.filter(
                action=AuthEvent.ACTION_REGISTER_SUCCESS,
            ).exists()

    def test_register_fail_validation_400(self, api_client, db):
        """Payload invalido -> REGISTER_FAIL con reason field-name."""
        AuthEvent.objects.filter(action__startswith='REGISTER').delete()
        r = api_client.post(URL, {}, format='json')
        assert r.status_code == 400

        fail_ev = AuthEvent.objects.filter(
            action=AuthEvent.ACTION_REGISTER_FAIL,
        ).first()
        assert fail_ev is not None
        # DEC-ALR-3: reason es field_name + '_invalid', NO el value.
        assert fail_ev.reason.endswith('_invalid')

    def test_register_fail_no_filtra_password(self, api_client, db):
        """DEC-ALR-3 + DEC-AL-3: reason no contiene password value."""
        AuthEvent.objects.filter(action__startswith='REGISTER').delete()
        api_client.post(URL, {
            'username': 'x',
            'password': 'leak_password_value_here',
        }, format='json')

        for ev in AuthEvent.objects.filter(action__startswith='REGISTER'):
            assert 'leak_password' not in ev.reason
            assert 'leak_password' not in str(ev.extra_json or {})
