"""Integration — portal de cuenta (≙ ``/my/*`` de ``odoo19c: portal``).

Ejercita el contrato montado en ``addons/portal/controllers/``: contacto,
direcciones, seguridad y baja. Cada test nombra la ruta de la referencia que
adapta, para que el drift sea visible al leer.

``force_login`` (Django) y no ``force_authenticate`` (DRF) donde el flujo toca
la **sesión**: el cambio de contraseña rehace el hash de sesión y la baja la
cierra — con ``session_key=''`` esos pasos no se ejercitarían de verdad
(ADR-018: la sesión de servidor es la credencial).
"""
import logging

from addons.authz.models import Role, RoleAssignment
from addons.authz.services import invalidate_capabilities
from addons.base.models import SystemParameter
from addons.base.models.res_partner import ResPartner
from addons.base.models.res_users_deletion import ResUsersDeletion

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APIClient

pytestmark = pytest.mark.integration

User = get_user_model()

ACCOUNT = '/api/v2/portal/account/'
ADDRESSES = '/api/v2/portal/addresses/'
SECURITY = '/api/v2/portal/security/'
PASSWORD = '/api/v2/portal/security/password/'
DEACTIVATIONS = '/api/v2/portal/deactivations/'

PASS_VIEJA = 'PortalPass123!'
PASS_NUEVA = 'PortalPass456!'


@pytest.fixture
def comprador(db):
    """Usuario con su partner y el rol comprador — el sujeto de ``/my/*``."""
    call_command('seed_authz')
    partner = ResPartner.objects.create(name='Ana Portal',
                                        email='ana@portal.test')
    user = User.objects.create_user(login='ana@portal.test',
                                    password=PASS_VIEJA, partner=partner)
    rol = Role.objects.get(code='comprador')
    RoleAssignment.objects.create(user=user, role=rol)
    invalidate_capabilities(user.id)
    return user


def _customer(user):
    client = APIClient()
    client.force_login(user)
    return client


class TestContacto:
    """≙ ``/my/account``."""

    def test_get_devuelve_el_contacto_del_usuario(self, comprador):
        r = _customer(comprador).get(ACCOUNT)
        assert r.status_code == 200, r.data
        assert r.data['name'] == 'Ana Portal'

    def test_patch_edita_solo_campos_del_allowlist(self, comprador):
        r = _customer(comprador).patch(
            ACCOUNT, {'city': 'Mérida', 'phone': '9991234567'}, format='json')
        assert r.status_code == 200, r.data
        comprador.partner.refresh_from_db()
        assert comprador.partner.city == 'Mérida'

    def test_campo_fuera_del_allowlist_no_viaja(self, comprador):
        # ``active`` no está en frontend_writable_fields(): el serializer ni
        # lo declara, así que se ignora en vez de desactivar la cuenta.
        r = _customer(comprador).patch(ACCOUNT, {'active': False},
                                      format='json')
        assert r.status_code == 200, r.data
        comprador.partner.refresh_from_db()
        assert comprador.partner.active is True

    def test_sin_capacidad_da_403(self, db):
        call_command('seed_authz')
        u = User.objects.create_user(login='sinrol@portal.test',
                                     password=PASS_VIEJA)
        assert _customer(u).get(ACCOUNT).status_code == 403


class TestAddresses:
    """≙ ``/my/addresses`` y ``/my/address/archive`` (ambas sólo en 19c)."""

    def test_lista_incluye_la_principal_y_las_hijas(self, comprador):
        ResPartner.objects.create(name='Bodega', parent=comprador.partner,
                                  type=ResPartner.TYPE_DELIVERY)
        r = _customer(comprador).get(ADDRESSES)
        assert r.status_code == 200, r.data
        nombres = [d['name'] for d in r.data]
        assert nombres == ['Ana Portal', 'Bodega']

    def test_archivar_una_hija_la_saca_de_la_lista(self, comprador):
        hija = ResPartner.objects.create(name='Bodega',
                                         parent=comprador.partner,
                                         type=ResPartner.TYPE_DELIVERY)
        client = _customer(comprador)
        assert client.post(f'{ADDRESSES}{hija.pk}/archive/').status_code == 204
        assert [d['name'] for d in client.get(ADDRESSES).data] == ['Ana Portal']

    def test_no_se_archiva_la_principal(self, comprador):
        r = _customer(comprador).post(
            f'{ADDRESSES}{comprador.partner.pk}/archive/')
        assert r.status_code == 400
        assert r.data['codigo_error'] == 'MAIN_ADDRESS'

    def test_direccion_ajena_da_403(self, comprador, db):
        ajena = ResPartner.objects.create(name='De otro',
                                          type=ResPartner.TYPE_DELIVERY)
        r = _customer(comprador).post(f'{ADDRESSES}{ajena.pk}/archive/')
        assert r.status_code == 403
        assert r.data['codigo_error'] == 'ADDRESS_FORBIDDEN'

    def test_direccion_inexistente_da_404(self, comprador):
        r = _customer(comprador).post(f'{ADDRESSES}999999/archive/')
        assert r.status_code == 404
        assert r.data['codigo_error'] == 'ADDRESS_NOT_FOUND'


class TestSeguridad:
    """≙ el GET y el POST de ``/my/security`` (``_update_password``)."""

    def test_get_devuelve_login_y_bandera_de_api_keys(self, comprador):
        SystemParameter.set_param('authz.password_minlength', '10')
        r = _customer(comprador).get(SECURITY)
        assert r.status_code == 200, r.data
        assert r.data['login'] == 'ana@portal.test'
        assert r.data['allow_api_keys'] is False
        # Fold de auth_password_policy_portal: la política viaja en /my/security.
        assert r.data['password_minimum_length'] == 10

    def test_cambio_de_contrasena(self, comprador):
        r = _customer(comprador).post(
            PASSWORD,
            {'old': PASS_VIEJA, 'new1': PASS_NUEVA, 'new2': PASS_NUEVA},
            format='json')
        assert r.status_code == 200, r.data
        comprador.refresh_from_db()
        assert comprador.check_password(PASS_NUEVA)

    def test_the_change_leaves_an_audit_trace(self, comprador, caplog):
        """El endpoint delega en ``_change_password``, y ese eslabon registra
        quien cambio la contrasena de quien y desde donde.

        Es el control que puede fallar de esa delegacion: si la vista vuelve a
        hacer ``set_password`` + ``save`` a mano —que es lo que hacia— el
        cambio sigue funcionando y este caso cae. Medido: revirtiendo la
        delegacion, este es el unico de los 29 del subconjunto que falla.
        """
        with caplog.at_level(
                logging.INFO, logger='addons.base.models.res_users'):
            r = _customer(comprador).post(
                PASSWORD,
                {'old': PASS_VIEJA, 'new1': PASS_NUEVA, 'new2': PASS_NUEVA},
                format='json')
        assert r.status_code == 200, r.data
        trace = [x.getMessage() for x in caplog.records
                  if 'Cambio de contraseña' in x.getMessage()]
        assert trace, 'el cambio no dejo constancia'
        assert comprador.get_username() in trace[0]

    def test_campo_vacio_se_rechaza_antes_de_comparar(self, comprador):
        r = _customer(comprador).post(
            PASSWORD, {'old': '', 'new1': PASS_NUEVA, 'new2': 'otra'},
            format='json')
        assert r.status_code == 400
        # El orden de la referencia manda: vacío primero, no "no coinciden".
        assert r.data['codigo_error'] == 'PASSWORD_EMPTY'

    def test_confirmacion_distinta_se_rechaza(self, comprador):
        r = _customer(comprador).post(
            PASSWORD,
            {'old': PASS_VIEJA, 'new1': PASS_NUEVA, 'new2': 'DistintaX123!'},
            format='json')
        assert r.status_code == 400
        assert r.data['codigo_error'] == 'PASSWORD_MISMATCH'

    def test_contrasena_anterior_incorrecta_no_cambia_nada(self, comprador):
        r = _customer(comprador).post(
            PASSWORD,
            {'old': 'NoEsLaMia1!', 'new1': PASS_NUEVA, 'new2': PASS_NUEVA},
            format='json')
        assert r.status_code == 400
        assert r.data['codigo_error'] == 'PASSWORD_INCORRECT'
        comprador.refresh_from_db()
        assert comprador.check_password(PASS_VIEJA)


class TestBaja:
    """≙ ``/my/deactivate_account`` — las DOS pruebas de la referencia."""

    def test_baja_desactiva_y_registra_la_solicitud(self, comprador):
        r = _customer(comprador).post(
            DEACTIVATIONS,
            {'validation': 'ana@portal.test', 'password': PASS_VIEJA},
            format='json')
        assert r.status_code == 204, getattr(r, 'data', r)
        comprador.refresh_from_db()
        assert comprador.active is False
        assert ResUsersDeletion.objects.filter(user_int=comprador.pk).exists()

    def test_validation_que_no_es_el_login_no_da_de_baja(self, comprador):
        r = _customer(comprador).post(
            DEACTIVATIONS,
            {'validation': 'otro@portal.test', 'password': PASS_VIEJA},
            format='json')
        assert r.status_code == 400
        assert r.data['codigo_error'] == 'VALIDATION_MISMATCH'
        comprador.refresh_from_db()
        assert comprador.active is True

    def test_contrasena_incorrecta_no_da_de_baja(self, comprador):
        r = _customer(comprador).post(
            DEACTIVATIONS,
            {'validation': 'ana@portal.test', 'password': 'NoEsLaMia1!'},
            format='json')
        assert r.status_code == 400
        assert r.data['codigo_error'] == 'PASSWORD_INCORRECT'
        comprador.refresh_from_db()
        assert comprador.active is True
