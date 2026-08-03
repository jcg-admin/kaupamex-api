"""authz_signup — auto-registro y reset gobernados por política L2 (editable).

Adaptación nativa de ``authz_signup`` de Odoo: abrir/cerrar el registro público
y el reset de contraseña son config-params en runtime
(``authz.signup_allow_uninvited`` / ``authz.signup_reset_password``), no un
comportamiento cableado en las vistas. Verifica:

- default sembrado = abierto (sin regresión: registro y reset siguen operando);
- cerrar la bandera L2 hace que ``RegisterView`` devuelva 403 SIGNUP_CLOSED;
- cerrar el reset hace que ``PasswordResetRequestView`` devuelva 403.
"""
import pytest
from rest_framework.test import APIClient

from addons.base.models import SystemParameter, _clear_cache
from addons.authz_signup.models.policy import password_reset_enabled, signup_open

pytestmark = pytest.mark.django_db

REGISTER_URL = '/api/v2/auth/register/'
RESET_URL = '/api/v2/auth/password-reset/'


@pytest.fixture(autouse=True)
def _reset_param_cache():
    _clear_cache()
    yield
    _clear_cache()


def test_defaults_seeded_open_not_hardcoded():
    assert signup_open() is True
    assert password_reset_enabled() is True
    assert SystemParameter.get_param('authz.signup_allow_uninvited') == '1'
    assert SystemParameter.get_param('authz.signup_reset_password') == '1'


def test_register_open_by_default_not_403():
    """Con el default abierto, el gate NO bloquea (payload vacío -> 400, no 403)."""
    resp = APIClient().post(REGISTER_URL, {}, format='json')
    assert resp.status_code != 403


def test_register_403_when_signup_closed():
    SystemParameter.set_param('authz.signup_allow_uninvited', '0')
    resp = APIClient().post(REGISTER_URL, {}, format='json')
    assert resp.status_code == 403
    assert resp.data['codigo_error'] == 'SIGNUP_CLOSED'


def test_reset_open_by_default_not_403():
    resp = APIClient().post(RESET_URL, {}, format='json')
    assert resp.status_code != 403


def test_reset_403_when_reset_disabled():
    SystemParameter.set_param('authz.signup_reset_password', '0')
    resp = APIClient().post(RESET_URL, {}, format='json')
    assert resp.status_code == 403
    assert resp.data['codigo_error'] == 'PASSWORD_RESET_DISABLED'
