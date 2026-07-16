"""
Tests de configuracion — DRF throttle en endpoints publicos.

Cubre hardening-throttle-endpoints-publicos: verifica que la
configuracion de throttle esta presente y que las vistas
declaran throttle_scope. Runtime behavior se verifica
manualmente porque testing.py desactiva throttle global y
override_settings de REST_FRAMEWORK no surte efecto sin
reload del api_settings cache de DRF (fragil).
"""
import pytest
from django.conf import settings
from apps.modules.contact.views import ContactMessageCreateView
from apps.modules.users.views import (
    EmailVerifyView, PasswordResetConfirmView, PasswordResetRequestView,
    RegisterView, ResendVerificationView,
)

pytestmark = pytest.mark.integration


class TestThrottleConfiguration:
    """Hardening throttle: settings + view attributes presentes."""

    def test_rest_framework_declara_throttle_classes(self, db):
        rf = settings.REST_FRAMEWORK
        # En testing.py se override a [], pero los rates deben existir.
        assert 'DEFAULT_THROTTLE_RATES' in rf, (
            'Falta DEFAULT_THROTTLE_RATES en REST_FRAMEWORK config.'
        )

    def test_throttle_rates_para_scopes_sensibles(self, db):
        rates = settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {})
        for scope in (
            'register', 'password_reset', 'password_confirm',
            'email_verify', 'resend_verification', 'contact',
        ):
            assert scope in rates, f'Falta rate para scope {scope!r}.'
            # Sanity: el rate tiene formato 'N/period'.
            value = rates[scope]
            assert '/' in value, f'Rate {value!r} inválido para {scope!r}.'

    def test_register_view_declara_scope(self, db):
        assert getattr(RegisterView, 'throttle_scope', None) == 'register'

    def test_password_reset_request_view_declara_scope(self, db):
        assert getattr(PasswordResetRequestView, 'throttle_scope', None) == 'password_reset'

    def test_password_reset_confirm_view_declara_scope(self, db):
        assert getattr(PasswordResetConfirmView, 'throttle_scope', None) == 'password_confirm'

    def test_email_verify_view_declara_scope(self, db):
        assert getattr(EmailVerifyView, 'throttle_scope', None) == 'email_verify'

    def test_resend_verification_view_declara_scope(self, db):
        assert getattr(ResendVerificationView, 'throttle_scope', None) == 'resend_verification'

    def test_contact_view_declara_scope(self, db):
        assert getattr(ContactMessageCreateView, 'throttle_scope', None) == 'contact'
