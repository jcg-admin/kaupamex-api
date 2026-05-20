"""
Tests de integracion — Direcciones de envio
UC-AUTH-07: Gestionar Direcciones de Envio
"""
import pytest
from django.contrib.auth import get_user_model
from apps.users.models import Address
from rest_framework_simplejwt.tokens import RefreshToken

pytestmark = pytest.mark.integration

ADDR_URL = '/api/v1/auth/addresses/'

VALID_ADDR = {
    'alias': 'Casa',
    'recipient_name': 'Demo Yoruba',
    'street': 'Insurgentes Sur 1234',
    'city': 'Ciudad de Mexico',
    'state': 'CDMX',
    'zip_code': '03100',
    'country': 'MX',
    'phone': '5551234567',
}


class TestAddressList:

    def test_listar_retorna_200(self, auth_client, db):
        r = auth_client.get(ADDR_URL)
        assert r.status_code == 200

    def test_sin_autenticar_retorna_401(self, api_client, db):
        r = api_client.get(ADDR_URL)
        assert r.status_code == 401

    def test_lista_vacia_inicialmente(self, auth_client, db):
        r = auth_client.get(ADDR_URL)
        assert r.json() == []

    def test_solo_ve_sus_propias_direcciones(self, api_client, db):
        User = get_user_model()
        u1 = User.objects.create_user(username='u1', email='u1@test.mx', password='Pass123!')
        u2 = User.objects.create_user(username='u2', email='u2@test.mx', password='Pass123!')
        Address.objects.create(user=u2, **VALID_ADDR)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(u1).access_token}')
        r = api_client.get(ADDR_URL)
        assert r.json() == []


class TestAddressCreate:

    def test_crear_retorna_201(self, auth_client, db):
        r = auth_client.post(ADDR_URL, VALID_ADDR, format='json')
        assert r.status_code == 201

    def test_primera_direccion_es_default(self, auth_client, db):
        auth_client.post(ADDR_URL, VALID_ADDR, format='json')
        r = auth_client.get(ADDR_URL)
        assert r.json()[0]['is_default'] is True

    def test_segunda_direccion_no_es_default_automaticamente(self, auth_client, db):
        auth_client.post(ADDR_URL, VALID_ADDR, format='json')
        addr2 = {**VALID_ADDR, 'alias': 'Trabajo'}
        auth_client.post(ADDR_URL, addr2, format='json')
        r = auth_client.get(ADDR_URL)
        defaults = [a for a in r.json() if a['is_default']]
        assert len(defaults) == 1

    def test_marcar_nueva_como_default_cambia_la_anterior(self, auth_client, db):
        auth_client.post(ADDR_URL, VALID_ADDR, format='json')
        addr2 = {**VALID_ADDR, 'alias': 'Trabajo', 'is_default': True}
        r2 = auth_client.post(ADDR_URL, addr2, format='json')
        assert r2.json()['is_default'] is True
        r = auth_client.get(ADDR_URL)
        defaults = [a for a in r.json() if a['is_default']]
        assert len(defaults) == 1
        assert defaults[0]['alias'] == 'Trabajo'

    def test_limite_5_direcciones(self, auth_client, db):
        for i in range(5):
            auth_client.post(ADDR_URL, {**VALID_ADDR, 'alias': f'Dir{i}'}, format='json')
        r = auth_client.post(ADDR_URL, {**VALID_ADDR, 'alias': 'Sexta'}, format='json')
        assert r.status_code == 422

    def test_campos_requeridos(self, auth_client, db):
        r = auth_client.post(ADDR_URL, {'alias': 'Solo alias'}, format='json')
        assert r.status_code == 400

    def test_sin_autenticar_retorna_401(self, api_client, db):
        r = api_client.post(ADDR_URL, VALID_ADDR, format='json')
        assert r.status_code == 401


class TestAddressUpdate:

    def test_editar_alias(self, auth_client, user, db):
        addr = Address.objects.create(user=user, **VALID_ADDR)
        r = auth_client.patch(f'{ADDR_URL}{addr.pk}/', {'alias': 'Nuevo alias'}, format='json')
        assert r.status_code == 200
        addr.refresh_from_db()
        assert addr.alias == 'Nuevo alias'

    def test_no_puede_editar_direccion_de_otro_usuario(self, api_client, db):
        User = get_user_model()
        u1 = User.objects.create_user(username='u1b', email='u1b@test.mx', password='Pass123!')
        u2 = User.objects.create_user(username='u2b', email='u2b@test.mx', password='Pass123!')
        addr = Address.objects.create(user=u2, **VALID_ADDR)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(u1).access_token}')
        r = api_client.patch(f'{ADDR_URL}{addr.pk}/', {'alias': 'Hack'}, format='json')
        assert r.status_code == 404


class TestAddressDelete:

    def test_eliminar_retorna_204(self, auth_client, user, db):
        addr = Address.objects.create(user=user, **VALID_ADDR)
        r = auth_client.delete(f'{ADDR_URL}{addr.pk}/')
        assert r.status_code == 204

    def test_eliminar_direccion_default_libera_default(self, auth_client, user, db):
        a1 = Address.objects.create(user=user, is_default=True, **VALID_ADDR)
        a2 = Address.objects.create(user=user, is_default=False, **{**VALID_ADDR, 'alias': 'Otra'})
        auth_client.delete(f'{ADDR_URL}{a1.pk}/')
        a2.refresh_from_db()
        assert a2.is_default is True

    def test_no_puede_eliminar_direccion_de_otro(self, api_client, db):
        User = get_user_model()
        u1 = User.objects.create_user(username='u1c', email='u1c@test.mx', password='Pass123!')
        u2 = User.objects.create_user(username='u2c', email='u2c@test.mx', password='Pass123!')
        addr = Address.objects.create(user=u2, **VALID_ADDR)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(u1).access_token}')
        r = api_client.delete(f'{ADDR_URL}{addr.pk}/')
        assert r.status_code == 404
