"""Tests — addons.authz_ldap (federación LDAP).

Porta la intención de ``odoo19c: auth_ldap/tests/test_auth_ldap.py`` (65 loc,
leído completo): con ``_get_ldap_dicts`` y ``_authenticate`` mockeados, un
login de un usuario inexistente crea la cuenta federada y autentica. Allí el
vehículo es ``/web/login`` + sesión; aquí es ``django.contrib.auth
.authenticate`` — el punto donde la cadena ``AUTHENTICATION_BACKENDS``
(≙ ``super()._login``) resuelve.

Sin ``python-ldap`` instalado (estado verificado del contenedor): el mock
reemplaza la capa de red, igual que en la referencia, así que la suite corre
sin el binario.
"""
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import authenticate, get_user_model
from django.core.management import call_command
from django.utils import timezone

from addons.authz.models import Capability, Role, RoleAssignment, RoleCapability
from addons.authz.services import invalidate_capabilities
from addons.authz_reauth.models import ReauthSession
from addons.authz_ldap.models import CompanyLdap
from addons.base.models import ResCompany

User = get_user_model()

LDAP_ENTRY = (
    'cn=test_ldap_user,dc=kaupamex,dc=mx',
    {
        'sn': [b'test_ldap_user'],
        'cn': [b'test_ldap_user'],
        'objectClass': [b'inetOrgPerson', b'top'],
    },
)


@pytest.fixture
def company(db):
    return ResCompany.objects.create(code='c-ldap', name='ResCompany LDAP')


def _conf(company, **overrides):
    conf = {
        'id': 1,
        'company_id': company.id,
        'ldap_server': '127.0.0.1',
        'ldap_server_port': 389,
        'ldap_binddn': 'cn=admin,dc=kaupamex,dc=mx',
        'ldap_password': 'admin',
        'ldap_filter': 'cn=%s',
        'ldap_base': 'dc=kaupamex,dc=mx',
        'user_id': None,
        'create_user': True,
        'ldap_tls': False,
    }
    conf.update(overrides)
    return conf


class TestLdapBackend:
    """≙ ``TestAuthLDAP.test_auth_ldap`` de la referencia + los caminos que
    su test no cubre pero su código sí (create_user=False, password vacío)."""

    def test_login_crea_usuario_federado(self, db, company):
        login = 'test_ldap_user@kaupamex.mx'
        assert not User.objects.filter(login=login).exists()

        with patch.object(
            CompanyLdap.objects.__class__, 'get_ldap_dicts',
            return_value=[_conf(company)],
        ), patch.object(
            CompanyLdap, '_authenticate', return_value=LDAP_ENTRY,
        ):
            user = authenticate(username=login, password='secret')

        assert user is not None
        assert user.login == login
        assert user.company_id == company.id
        # La credencial vive en el directorio: sin password local usable.
        assert not user.has_usable_password()
        # single_email_re: el login con forma de email viaja como email.
        assert User.objects.filter(login=login).count() == 1

    def test_password_vacio_no_intenta_bind(self, db, company):
        # RFC 4513 §6.3.1 (unauthenticated authentication) — igual que la
        # referencia, un password vacío jamás llega al directorio.
        with patch.object(
            CompanyLdap, '_authenticate',
        ) as mock_auth:
            assert authenticate(username='x@kaupamex.mx', password='') is None
        mock_auth.assert_not_called()

    def test_create_user_false_no_crea(self, db, company):
        login = 'sin-alta@kaupamex.mx'
        with patch.object(
            CompanyLdap.objects.__class__, 'get_ldap_dicts',
            return_value=[_conf(company, create_user=False)],
        ), patch.object(
            CompanyLdap, '_authenticate', return_value=LDAP_ENTRY,
        ):
            assert authenticate(username=login, password='secret') is None
        assert not User.objects.filter(login=login).exists()

    def test_usuario_existente_password_ldap(self, db, company):
        # Camino _check_credentials: el usuario local existe con password
        # inutilizable; el bind LDAP lo autentica.
        login = 'federado@kaupamex.mx'
        user = User.objects.create_user(login=login)
        user.set_unusable_password()
        user.save(update_fields=['password'])

        with patch.object(
            CompanyLdap.objects.__class__, 'get_ldap_dicts',
            return_value=[_conf(company)],
        ), patch.object(
            CompanyLdap, '_authenticate', return_value=LDAP_ENTRY,
        ):
            assert authenticate(username=login, password='secret') == user

    def test_usuario_inactivo_no_autentica(self, db, company):
        login = 'inactivo@kaupamex.mx'
        user = User.objects.create_user(login=login)
        user.active = False
        user.save(update_fields=['active'])

        with patch.object(
            CompanyLdap.objects.__class__, 'get_ldap_dicts',
            return_value=[_conf(company)],
        ), patch.object(
            CompanyLdap, '_authenticate', return_value=LDAP_ENTRY,
        ):
            assert authenticate(username=login, password='secret') is None


class TestCompanyLdapEndpoint:
    """El CRUD está gateado por ``permissions.ldap`` (fail-closed): 403 sin
    la capacidad, 200 con ella (DEC-11). Como el code es **sensible**, DEC-12
    exige además sesión elevada fresca — se siembra ``ReauthSession`` con
    ``session_key=''`` (``force_authenticate`` no crea sesión Django), mismo
    patrón que ``test_admin_roles.py``."""

    @pytest.fixture
    def seeded(self, db):
        call_command('seed_authz')

    def _grant(self, user):
        cap = Capability.objects.get(code='permissions.ldap')
        role = Role.objects.create(code='r-ldap-admin', name='LDAP admin')
        RoleCapability.objects.create(role=role, capability=cap)
        RoleAssignment.objects.create(user=user, role=role)
        invalidate_capabilities(user.id)

    def _login_elevado(self, client, user):
        client.force_authenticate(user)
        ReauthSession.objects.update_or_create(
            user_id=user.pk, session_key='',
            defaults={'started_at': timezone.now(),
                      'expires_at': timezone.now() + timedelta(seconds=900)})

    def test_sin_capacidad_403(self, seeded, api_client):
        user = User.objects.create_user(
            login='sin-cap@kaupamex.mx', password='x')
        api_client.force_authenticate(user)
        resp = api_client.get('/api/v2/authz/ldap-configs/')
        assert resp.status_code == 403

    def test_con_capacidad_lista(self, seeded, api_client, company):
        user = User.objects.create_user(
            login='con-cap@kaupamex.mx', password='x')
        self._grant(user)
        self._login_elevado(api_client, user)
        resp = api_client.get('/api/v2/authz/ldap-configs/')
        assert resp.status_code == 200, resp.data

    def test_password_ldap_no_vuelve(self, seeded, api_client, company):
        user = User.objects.create_user(
            login='cfg@kaupamex.mx', password='x')
        self._grant(user)
        self._login_elevado(api_client, user)
        resp = api_client.post('/api/v2/authz/ldap-configs/', {
            'company': company.id,
            'ldap_server': 'ldap.kaupamex.mx',
            'ldap_server_port': 389,
            'ldap_password': 'super-secreto',
            'ldap_filter': '(uid=%s)',
            'ldap_base': 'dc=kaupamex,dc=mx',
        }, format='json')
        assert resp.status_code == 201, resp.data
        assert 'ldap_password' not in resp.data
        assert CompanyLdap.objects.get(
            pk=resp.data['id']).ldap_password == 'super-secreto'
