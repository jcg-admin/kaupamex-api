"""
Tests del filtro ?deactivated_reason= en AdminUserViewSet (UC-AUTH-11).
"""
import pytest
from django.utils import timezone
from django.contrib.auth import get_user_model

pytestmark = pytest.mark.api

URL = '/api/v2/admin/users/'


@pytest.fixture
def users_set(db):
    """Tres usuarios — uno por motivo de inactividad."""
    User = get_user_model()
    now = timezone.now()
    return [
        User.objects.create_user(
            email='u1@x.mx', password='x',
            is_active=False, deactivated_reason='unverified',
            deactivated_at=now,
        ),
        User.objects.create_user(
            email='s1@x.mx', password='x',
            is_active=False, deactivated_reason='suspended',
            deactivated_at=now,
        ),
        User.objects.create_user(
            email='d1@x.mx', password='x',
            is_active=False, deactivated_reason='self_deleted',
            deactivated_at=now,
        ),
    ]


class TestAdminFilterPorReason:

    def test_sin_filtro_lista_todos(self, admin_auth_client, users_set, admin_user):
        r = admin_auth_client.get(URL)
        assert r.status_code == 200
        body = r.json()
        # Includes the 3 fixtures + the admin himself.
        assert body['count'] >= 4

    def test_filtro_unverified_devuelve_solo_unverified(
        self, admin_auth_client, users_set,
    ):
        r = admin_auth_client.get(f'{URL}?deactivated_reason=unverified')
        assert r.status_code == 200
        users = r.json()['results']
        assert all(u['deactivated_reason'] == 'unverified' for u in users)
        assert len(users) == 1

    def test_filtro_suspended_devuelve_solo_suspendidos(
        self, admin_auth_client, users_set,
    ):
        r = admin_auth_client.get(f'{URL}?deactivated_reason=suspended')
        assert r.status_code == 200
        users = r.json()['results']
        assert all(u['deactivated_reason'] == 'suspended' for u in users)
        assert len(users) == 1

    def test_filtro_self_deleted_devuelve_solo_self_deleted(
        self, admin_auth_client, users_set,
    ):
        r = admin_auth_client.get(f'{URL}?deactivated_reason=self_deleted')
        assert r.status_code == 200
        users = r.json()['results']
        assert all(u['deactivated_reason'] == 'self_deleted' for u in users)
        assert len(users) == 1

    def test_filtro_motivo_invalido_devuelve_lista_vacia(
        self, admin_auth_client, users_set,
    ):
        r = admin_auth_client.get(f'{URL}?deactivated_reason=nonsense')
        assert r.status_code == 200
        assert r.json()['results'] == []


class TestAdminListSerializerExponeNuevosCampos:
    """AdminUserListSerializer expone deactivated_reason y deactivated_at."""

    def test_response_incluye_deactivated_reason(
        self, admin_auth_client, users_set,
    ):
        r = admin_auth_client.get(URL)
        for u in r.json()['results']:
            assert 'deactivated_reason' in u

    def test_response_incluye_deactivated_at(
        self, admin_auth_client, users_set,
    ):
        r = admin_auth_client.get(URL)
        for u in r.json()['results']:
            assert 'deactivated_at' in u
