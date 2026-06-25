"""
Tests de integracion — UC-AUTH-01 Alt-A: Email ya registrado.

Cubre las tres ramas refinadas en docs@103eb25 + implementadas en
RegisterView.post (commit posterior al refactor PEP 8):

- A.1 cuenta activa -> 400 con mensaje explicito.
- A.2 cuenta inactiva reactivable (unverified / self_deleted) ->
      201 indistinguible de cuenta nueva + reenvio de email.
- A.3 cuenta suspendida por admin -> 201 indistinguible, SIN email.
"""
import pytest
from django.core import mail
from django.utils import timezone
from django.contrib.auth import get_user_model

pytestmark = pytest.mark.api

URL = '/api/v2/auth/register/'

NEW_REGISTRATION = {
    'email':            'rebote@practicayoruba.mx',
    'password':         'Yoruba2026!',
    'password_confirm': 'Yoruba2026!',
    'terms_accepted':   True,
}


@pytest.fixture
def active_user(db):
    return get_user_model().objects.create_user(
        username='activo',
        email='rebote@practicayoruba.mx',
        password='Old123!',
        is_active=True,
    )


@pytest.fixture
def unverified_user(db):
    User = get_user_model()
    u = User.objects.create_user(
        username='unverif',
        email='rebote@practicayoruba.mx',
        password='Old123!',
        is_active=False,
    )
    u.deactivated_reason = User.DEACTIVATION_UNVERIFIED
    u.deactivated_at = timezone.now()
    u.save(update_fields=['deactivated_reason', 'deactivated_at'])
    return u


@pytest.fixture
def self_deleted_user(db):
    User = get_user_model()
    u = User.objects.create_user(
        username='exuser',
        email='rebote@practicayoruba.mx',
        password='Old123!',
        is_active=False,
    )
    u.deactivated_reason = User.DEACTIVATION_SELF_DELETED
    u.deactivated_at = timezone.now()
    u.save(update_fields=['deactivated_reason', 'deactivated_at'])
    return u


@pytest.fixture
def suspended_user(db):
    User = get_user_model()
    u = User.objects.create_user(
        username='suspended',
        email='rebote@practicayoruba.mx',
        password='Old123!',
        is_active=False,
    )
    u.deactivated_reason = User.DEACTIVATION_SUSPENDED
    u.deactivated_at = timezone.now()
    u.save(update_fields=['deactivated_reason', 'deactivated_at'])
    return u


class TestAltA1CuentaActiva:
    """Email registrado y is_active=True."""

    def test_responde_409(self, api_client, active_user):
        r = api_client.post(URL, NEW_REGISTRATION, format='json')
        assert r.status_code == 409

    def test_mensaje_indica_que_inicie_sesion(self, api_client, active_user):
        r = api_client.post(URL, NEW_REGISTRATION, format='json')
        body = r.json()
        msg = (body.get('email') or [''])[0].lower()
        assert 'sesion' in msg or 'inicia' in msg

    def test_no_envia_email(self, api_client, active_user):
        mail.outbox.clear()
        api_client.post(URL, NEW_REGISTRATION, format='json')
        assert len(mail.outbox) == 0


class TestAltA2InactivaReactivable:
    """unverified / self_deleted -> reenvio silencioso."""

    def test_unverified_responde_201(self, api_client, unverified_user):
        r = api_client.post(URL, NEW_REGISTRATION, format='json')
        assert r.status_code == 201

    def test_self_deleted_responde_201(self, api_client, self_deleted_user):
        r = api_client.post(URL, NEW_REGISTRATION, format='json')
        assert r.status_code == 201

    def test_unverified_envia_email_de_verificacion(
        self, api_client, unverified_user,
    ):
        mail.outbox.clear()
        api_client.post(URL, NEW_REGISTRATION, format='json')
        assert len(mail.outbox) >= 1

    def test_self_deleted_envia_email_de_verificacion(
        self, api_client, self_deleted_user,
    ):
        mail.outbox.clear()
        api_client.post(URL, NEW_REGISTRATION, format='json')
        assert len(mail.outbox) >= 1

    def test_no_crea_usuario_duplicado(self, api_client, unverified_user):
        api_client.post(URL, NEW_REGISTRATION, format='json')
        count = get_user_model().objects.filter(
            email__iexact='rebote@practicayoruba.mx',
        ).count()
        assert count == 1


class TestAltA3Suspendida:
    """suspended por admin -> respuesta indistinguible pero SIN email."""

    def test_responde_201_indistinguible(self, api_client, suspended_user):
        r = api_client.post(URL, NEW_REGISTRATION, format='json')
        # Misma forma que cuenta nueva o A.2 — sin enumeration leak.
        assert r.status_code == 201

    def test_no_envia_email(self, api_client, suspended_user):
        mail.outbox.clear()
        api_client.post(URL, NEW_REGISTRATION, format='json')
        # Operacionalmente bloqueado — solo UC-AUTH-14 puede reactivar.
        assert len(mail.outbox) == 0

    def test_cuenta_sigue_suspendida(self, api_client, suspended_user):
        api_client.post(URL, NEW_REGISTRATION, format='json')
        suspended_user.refresh_from_db()
        assert suspended_user.is_active is False
        assert suspended_user.deactivated_reason == 'suspended'


class TestRegistroNuevoFlujoEstandar:
    """Camino sin colision sigue funcionando."""

    def test_email_nuevo_se_crea_201(self, api_client, db):
        r = api_client.post(URL, NEW_REGISTRATION, format='json')
        assert r.status_code == 201

    def test_email_nuevo_setea_reason_unverified(self, api_client, db):
        api_client.post(URL, NEW_REGISTRATION, format='json')
        u = get_user_model().objects.get(email='rebote@practicayoruba.mx')
        assert u.is_active is False
        assert u.deactivated_reason == 'unverified'
        assert u.deactivated_at is not None
