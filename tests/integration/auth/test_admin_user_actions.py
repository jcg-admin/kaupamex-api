"""
Tests de integracion — Acciones admin sobre usuarios
UC-AUTH-12 (ver perfil), UC-AUTH-13 (suspender),
UC-AUTH-14 (reactivar), UC-AUTH-15 (crear admin)
"""
import pytest
from apps.platform.authz.models import Role, RoleAssignment
from apps.platform.authz.services import SUPERADMIN_ROLE_CODE, is_superadmin
from apps.modules.users.models import BusinessEvent
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

pytestmark = pytest.mark.integration

USERS_URL = '/api/v2/admin/users/'


def _superadmin_role():
    role, _ = Role.objects.get_or_create(
        code=SUPERADMIN_ROLE_CODE, defaults={'name': 'Superadministrador'},
    )
    return role


@pytest.fixture
def target_user(db):
    return get_user_model().objects.create_user(
        email='target@test.mx',
        password='Pass123!', is_active=True,
    )


@pytest.fixture
def superuser_target(db):
    # Party/authz (T-201, DEC-01=B): "superusuario" = titular del rol
    # superadmin (no hay is_staff/is_superuser nativos).
    user = get_user_model().objects.create_user(
        email='super@test.mx',
        password='Pass123!', is_active=True,
    )
    RoleAssignment.objects.create(user=user, role=_superadmin_role())
    return user


class TestAdminUserDetail:

    def test_admin_puede_ver_perfil_de_usuario(self, admin_auth_client, target_user, db):
        r = admin_auth_client.get(f'{USERS_URL}{target_user.pk}/')
        assert r.status_code == 200

    def test_comprador_no_puede_ver_perfil_de_usuario(self, auth_client, target_user, db):
        r = auth_client.get(f'{USERS_URL}{target_user.pk}/')
        assert r.status_code == 403

    def test_perfil_contiene_campos_esperados(self, admin_auth_client, target_user, db):
        # Party/authz (T-201): username/is_staff ya no existen; el detalle
        # expone email, is_admin y la lista de roles authz.
        r = admin_auth_client.get(f'{USERS_URL}{target_user.pk}/')
        data = r.json()
        for field in ['id', 'email', 'is_active', 'is_admin', 'date_joined', 'roles']:
            assert field in data

    def test_usuario_inexistente_retorna_404(self, admin_auth_client, db):
        r = admin_auth_client.get(f'{USERS_URL}99999/')
        assert r.status_code == 404

    def test_detalle_expone_roles_del_usuario(self, admin_auth_client, target_user, db):
        # H-UI-02 / UC-ADM-02 (party/authz): el detalle devuelve los roles
        # authz actuales (id + code + name) para que el form de permisos los
        # pre-cargue antes del POST a /permissions/ (que reemplaza el set).
        r1 = Role.objects.create(code='editores', name='Editores')
        r2 = Role.objects.create(code='soporte', name='Soporte')
        RoleAssignment.objects.create(user=target_user, role=r1)
        RoleAssignment.objects.create(user=target_user, role=r2)

        r = admin_auth_client.get(f'{USERS_URL}{target_user.pk}/')
        assert r.status_code == 200
        data = r.json()
        assert 'roles' in data
        returned = {(g['id'], g['code']) for g in data['roles']}
        assert returned == {(r1.pk, 'editores'), (r2.pk, 'soporte')}


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
        r = api_client.post('/api/v2/auth/refresh/', {'refresh': refresh}, format='json')
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
        # una cuenta con rol superadmin no puede suspenderse desde el
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
            email='inactive@test.mx',
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
    # Party/authz (T-201): el alta de admin es email + password (sin
    # username). El usuario creado recibe el rol superadmin.

    def test_crear_admin_retorna_201(self, admin_auth_client, db):
        r = admin_auth_client.post(USERS_URL, {
            'email': 'newadmin@test.mx',
            'password': 'AdminPass123!',
        }, format='json')
        assert r.status_code == 201

    def test_nuevo_admin_tiene_rol_superadmin(self, admin_auth_client, db):
        admin_auth_client.post(USERS_URL, {
            'email': 'newadmin2@test.mx',
            'password': 'AdminPass123!',
        }, format='json')
        user = get_user_model().objects.get(email='newadmin2@test.mx')
        assert is_superadmin(user) is True

    def test_nuevo_admin_esta_activo(self, admin_auth_client, db):
        admin_auth_client.post(USERS_URL, {
            'email': 'newadmin3@test.mx',
            'password': 'AdminPass123!',
        }, format='json')
        user = get_user_model().objects.get(email='newadmin3@test.mx')
        assert user.is_active is True

    def test_comprador_no_puede_crear_admin(self, auth_client, db):
        r = auth_client.post(USERS_URL, {
            'email': 'hack@test.mx',
            'password': 'HackPass123!',
        }, format='json')
        assert r.status_code == 403


class TestAdminEditPermissions:
    """UC-ADM-02 (party/authz): POST /api/v2/admin/users/<pk>/permissions/

    Party/authz (T-201, DEC-01=B): los is_staff/is_superuser/groups nativos
    ya no existen. ``roles`` (lista de ids de Role) reemplaza el set de
    RoleAssignment del usuario.
    """

    def _url(self, pk):
        return f'{USERS_URL}{pk}/permissions/'

    def test_admin_puede_promover_a_superadmin(self, admin_auth_client, target_user, db):
        role = _superadmin_role()
        r = admin_auth_client.post(
            self._url(target_user.pk),
            {'roles': [role.pk]},
            format='json',
        )
        assert r.status_code == 200
        assert is_superadmin(target_user) is True

    def test_admin_puede_asignar_roles(self, admin_auth_client, target_user, db):
        r1 = Role.objects.create(code='editores', name='Editores')
        r2 = Role.objects.create(code='soporte', name='Soporte')
        r = admin_auth_client.post(
            self._url(target_user.pk),
            {'roles': [r1.pk, r2.pk]},
            format='json',
        )
        assert r.status_code == 200
        assert set(
            RoleAssignment.objects.filter(user=target_user)
            .values_list('role_id', flat=True)
        ) == {r1.pk, r2.pk}

    def test_cambio_se_audita_en_business_event(
        self, admin_auth_client, target_user, admin_user, db,
        django_capture_on_commit_callbacks,
    ):
        # audit_log_business emite el BusinessEvent vía transaction.on_commit
        # (DEC-CC-2); en el atomic-rollback default del test los callbacks no
        # disparan, así que se capturan/ejecutan explícitamente.
        role = Role.objects.create(code='editores', name='Editores')
        with django_capture_on_commit_callbacks(execute=True):
            admin_auth_client.post(
                self._url(target_user.pk),
                {'roles': [role.pk]},
                format='json',
            )
        ev = BusinessEvent.objects.filter(
            action='ADMIN_PERMISSIONS_CHANGED',
            target_type='user',
            target_id=target_user.pk,
        ).first()
        assert ev is not None
        assert ev.actor_id == admin_user.pk
        assert ev.extra_json['changes']['roles'] == [role.pk]

    def test_admin_no_puede_quitarse_superadmin_a_si_mismo(self, admin_auth_client, admin_user, db):
        # admin_user ya es titular del rol superadmin (conftest). Quitarse el
        # rol (roles=[]) lo dejaría sin acceso al panel → 400.
        assert is_superadmin(admin_user) is True
        r = admin_auth_client.post(
            self._url(admin_user.pk),
            {'roles': []},
            format='json',
        )
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'CANNOT_DEMOTE_SELF'
        assert is_superadmin(admin_user) is True

    def test_comprador_no_puede_editar_permisos(self, auth_client, target_user, db):
        role = _superadmin_role()
        r = auth_client.post(
            self._url(target_user.pk),
            {'roles': [role.pk]},
            format='json',
        )
        assert r.status_code == 403
        assert is_superadmin(target_user) is False

    def test_payload_invalido_retorna_400(self, admin_auth_client, target_user, db):
        r = admin_auth_client.post(
            self._url(target_user.pk),
            {'roles': 'no-es-lista'},
            format='json',
        )
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'INVALID_PAYLOAD'

    def test_rol_inexistente_retorna_400(self, admin_auth_client, target_user, db):
        r = admin_auth_client.post(
            self._url(target_user.pk),
            {'roles': [424242]},
            format='json',
        )
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'INVALID_PAYLOAD'

    def test_usuario_inexistente_retorna_404(self, admin_auth_client, db):
        r = admin_auth_client.post(
            self._url(999999),
            {'roles': []},
            format='json',
        )
        assert r.status_code == 404
        assert r.json()['codigo_error'] == 'USER_NOT_FOUND'
