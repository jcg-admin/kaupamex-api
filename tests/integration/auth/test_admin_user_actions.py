"""
Tests de integracion — Acciones admin sobre usuarios
UC-AUTH-12 (ver perfil), UC-AUTH-13 (suspender),
UC-AUTH-14 (reactivar), UC-AUTH-15 (crear admin)
"""
import pytest
from apps.users.models import BusinessEvent
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework_simplejwt.tokens import RefreshToken

pytestmark = pytest.mark.integration

USERS_URL = '/api/v1/admin/users/'


@pytest.fixture
def target_user(db):
    return get_user_model().objects.create_user(
        username='targetuser', email='target@test.mx',
        password='Pass123!', is_active=True,
    )


@pytest.fixture
def superuser_target(db):
    return get_user_model().objects.create_user(
        username='superusertarget', email='super@test.mx',
        password='Pass123!', is_active=True,
        is_staff=True, is_superuser=True,
    )


class TestAdminUserDetail:

    def test_admin_puede_ver_perfil_de_usuario(self, admin_auth_client, target_user, db):
        r = admin_auth_client.get(f'{USERS_URL}{target_user.pk}/')
        assert r.status_code == 200

    def test_comprador_no_puede_ver_perfil_de_usuario(self, auth_client, target_user, db):
        r = auth_client.get(f'{USERS_URL}{target_user.pk}/')
        assert r.status_code == 403

    def test_perfil_contiene_campos_esperados(self, admin_auth_client, target_user, db):
        r = admin_auth_client.get(f'{USERS_URL}{target_user.pk}/')
        data = r.json()
        for field in ['id', 'username', 'email', 'is_active', 'is_staff', 'date_joined']:
            assert field in data

    def test_usuario_inexistente_retorna_404(self, admin_auth_client, db):
        r = admin_auth_client.get(f'{USERS_URL}99999/')
        assert r.status_code == 404

    def test_detalle_expone_groups_del_usuario(self, admin_auth_client, target_user, db):
        # H-UI-02 / UC-ADM-02: el detalle debe devolver los grupos actuales
        # (ids + nombres) para que el form de permisos los pre-cargue antes
        # del POST a /permissions/ (que hace .set() y reemplaza todo).
        g1 = Group.objects.create(name='editores')
        g2 = Group.objects.create(name='soporte')
        target_user.groups.set([g1.pk, g2.pk])

        r = admin_auth_client.get(f'{USERS_URL}{target_user.pk}/')
        assert r.status_code == 200
        data = r.json()
        assert 'groups' in data
        returned = {(g['id'], g['name']) for g in data['groups']}
        assert returned == {(g1.pk, 'editores'), (g2.pk, 'soporte')}


class TestAdminSuspendUser:

    def test_suspender_usuario_retorna_200(self, admin_auth_client, target_user, db):
        r = admin_auth_client.post(f'{USERS_URL}{target_user.pk}/suspend/')
        assert r.status_code == 200

    def test_suspender_establece_is_active_false(self, admin_auth_client, target_user, db):
        admin_auth_client.post(f'{USERS_URL}{target_user.pk}/suspend/')
        target_user.refresh_from_db()
        assert target_user.is_active is False

    def test_suspender_invalida_sesiones(self, admin_auth_client, target_user, db, api_client):
        refresh = str(RefreshToken.for_user(target_user))
        admin_auth_client.post(f'{USERS_URL}{target_user.pk}/suspend/')
        r = api_client.post('/api/v1/auth/refresh/', {'refresh': refresh}, format='json')
        assert r.status_code == 401

    def test_comprador_no_puede_suspender(self, auth_client, target_user, db):
        r = auth_client.post(f'{USERS_URL}{target_user.pk}/suspend/')
        assert r.status_code == 403

    def test_admin_no_puede_suspenderse_a_si_mismo(self, admin_auth_client, admin_user, db):
        r = admin_auth_client.post(f'{USERS_URL}{admin_user.pk}/suspend/')
        assert r.status_code == 400

    def test_suspender_superusuario_es_rechazado(
        self, admin_auth_client, superuser_target, db
    ):
        # UC-AUTH-13 PRE-04 / EX-03 / PARTE 6 (Protección de superusuario):
        # una cuenta is_superuser=True no puede suspenderse desde el
        # backoffice. PARTE 7.3 → 403 / codigo_error = ACCOUNT_PROTECTED.
        r = admin_auth_client.post(f'{USERS_URL}{superuser_target.pk}/suspend/')
        assert r.status_code == 403
        assert r.json().get('codigo_error') == 'ACCOUNT_PROTECTED'

    def test_suspender_superusuario_no_muta_estado(
        self, admin_auth_client, superuser_target, db
    ):
        # POST-F01: is_active conserva el valor True tras el rechazo.
        admin_auth_client.post(f'{USERS_URL}{superuser_target.pk}/suspend/')
        superuser_target.refresh_from_db()
        assert superuser_target.is_active is True


class TestAdminReactivateUser:

    @pytest.fixture
    def inactive_target(self, db):
        return get_user_model().objects.create_user(
            username='inactiveuser', email='inactive@test.mx',
            password='Pass123!', is_active=False,
        )

    def test_reactivar_retorna_200(self, admin_auth_client, inactive_target, db):
        r = admin_auth_client.post(f'{USERS_URL}{inactive_target.pk}/reactivate/')
        assert r.status_code == 200

    def test_reactivar_establece_is_active_true(self, admin_auth_client, inactive_target, db):
        admin_auth_client.post(f'{USERS_URL}{inactive_target.pk}/reactivate/')
        inactive_target.refresh_from_db()
        assert inactive_target.is_active is True

    def test_comprador_no_puede_reactivar(self, auth_client, inactive_target, db):
        r = auth_client.post(f'{USERS_URL}{inactive_target.pk}/reactivate/')
        assert r.status_code == 403


class TestAdminCreateAdmin:

    def test_crear_admin_retorna_201(self, admin_auth_client, db):
        r = admin_auth_client.post(USERS_URL, {
            'username': 'newadmin',
            'email': 'newadmin@test.mx',
            'password': 'AdminPass123!',
        }, format='json')
        assert r.status_code == 201

    def test_nuevo_admin_tiene_is_staff_true(self, admin_auth_client, db):
        admin_auth_client.post(USERS_URL, {
            'username': 'newadmin2',
            'email': 'newadmin2@test.mx',
            'password': 'AdminPass123!',
        }, format='json')
        user = get_user_model().objects.get(username='newadmin2')
        assert user.is_staff is True

    def test_nuevo_admin_esta_activo(self, admin_auth_client, db):
        admin_auth_client.post(USERS_URL, {
            'username': 'newadmin3',
            'email': 'newadmin3@test.mx',
            'password': 'AdminPass123!',
        }, format='json')
        user = get_user_model().objects.get(username='newadmin3')
        assert user.is_active is True

    def test_comprador_no_puede_crear_admin(self, auth_client, db):
        r = auth_client.post(USERS_URL, {
            'username': 'hackadmin',
            'email': 'hack@test.mx',
            'password': 'HackPass123!',
        }, format='json')
        assert r.status_code == 403


class TestAdminEditPermissions:
    """UC-ADM-02: POST /api/v1/admin/users/<pk>/permissions/"""

    def _url(self, pk):
        return f'{USERS_URL}{pk}/permissions/'

    def test_admin_puede_promover_a_staff_y_superuser(self, admin_auth_client, target_user, db):
        r = admin_auth_client.post(
            self._url(target_user.pk),
            {'is_staff': True, 'is_superuser': True},
            format='json',
        )
        assert r.status_code == 200
        target_user.refresh_from_db()
        assert target_user.is_staff is True
        assert target_user.is_superuser is True

    def test_admin_puede_asignar_groups(self, admin_auth_client, target_user, db):
        g1 = Group.objects.create(name='editores')
        g2 = Group.objects.create(name='soporte')
        r = admin_auth_client.post(
            self._url(target_user.pk),
            {'groups': [g1.pk, g2.pk]},
            format='json',
        )
        assert r.status_code == 200
        assert set(target_user.groups.values_list('pk', flat=True)) == {g1.pk, g2.pk}

    def test_cambio_se_audita_en_business_event(
        self, admin_auth_client, target_user, admin_user, db,
        django_capture_on_commit_callbacks,
    ):
        # audit_log_business emite el BusinessEvent vía transaction.on_commit
        # (DEC-CC-2); en el atomic-rollback default del test los callbacks no
        # disparan, así que se capturan/ejecutan explícitamente.
        with django_capture_on_commit_callbacks(execute=True):
            admin_auth_client.post(
                self._url(target_user.pk),
                {'is_staff': True},
                format='json',
            )
        ev = BusinessEvent.objects.filter(
            action='ADMIN_PERMISSIONS_CHANGED',
            target_type='user',
            target_id=target_user.pk,
        ).first()
        assert ev is not None
        assert ev.actor_id == admin_user.pk
        assert ev.extra_json['changes']['is_staff'] is True

    def test_admin_no_puede_quitarse_superuser_a_si_mismo(self, admin_auth_client, admin_user, db):
        admin_user.is_superuser = True
        admin_user.save(update_fields=['is_superuser'])
        r = admin_auth_client.post(
            self._url(admin_user.pk),
            {'is_superuser': False},
            format='json',
        )
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'CANNOT_DEMOTE_SELF'
        admin_user.refresh_from_db()
        assert admin_user.is_superuser is True

    def test_admin_no_puede_quitarse_staff_a_si_mismo(self, admin_auth_client, admin_user, db):
        r = admin_auth_client.post(
            self._url(admin_user.pk),
            {'is_staff': False},
            format='json',
        )
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'CANNOT_DEMOTE_SELF'
        admin_user.refresh_from_db()
        assert admin_user.is_staff is True

    def test_comprador_no_puede_editar_permisos(self, auth_client, target_user, db):
        r = auth_client.post(
            self._url(target_user.pk),
            {'is_staff': True},
            format='json',
        )
        assert r.status_code == 403
        target_user.refresh_from_db()
        assert target_user.is_staff is False

    def test_payload_invalido_retorna_400(self, admin_auth_client, target_user, db):
        r = admin_auth_client.post(
            self._url(target_user.pk),
            {'is_staff': 'no-es-bool', 'groups': [999999]},
            format='json',
        )
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'INVALID_PAYLOAD'

    def test_grupo_inexistente_retorna_400(self, admin_auth_client, target_user, db):
        r = admin_auth_client.post(
            self._url(target_user.pk),
            {'groups': [424242]},
            format='json',
        )
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'INVALID_PAYLOAD'

    def test_usuario_inexistente_retorna_404(self, admin_auth_client, db):
        r = admin_auth_client.post(
            self._url(999999),
            {'is_staff': True},
            format='json',
        )
        assert r.status_code == 404
        assert r.json()['codigo_error'] == 'USER_NOT_FOUND'
