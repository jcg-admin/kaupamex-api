"""
Tests de integración — UC-AUTH-01: Registrar Cuenta
TDD: RED

POST /api/v1/auth/register/
Request:  { username, email, password, password_confirm }
Response 201: { message, user_id }
Response 400: errores de validacion por campo

FR-AUTH-01.02 — validar formato
FR-AUTH-01.03 — unicidad con mensaje ambiguo
FR-AUTH-01.04 — is_active=False al crear
"""
import pytest
from django.contrib.auth import get_user_model

pytestmark = pytest.mark.api

URL = '/api/v1/auth/register/'

VALID = {
    'username':         'comprador1',
    'email':            'comprador1@practicayoruba.mx',
    'password':         'Yoruba2026!',
    'password_confirm': 'Yoruba2026!',
}


class TestRegisterHappyPath:

    def test_registro_exitoso_devuelve_201(self, api_client, db):
        assert api_client.post(URL, VALID, format='json').status_code == 201

    def test_respuesta_contiene_user_id(self, api_client, db):
        data = api_client.post(URL, VALID, format='json').json()
        assert 'user_id' in data
        assert isinstance(data['user_id'], int)

    def test_cuenta_creada_con_is_active_false(self, api_client, db):
        api_client.post(URL, VALID, format='json')
        user = get_user_model().objects.get(username=VALID['username'])
        assert user.is_active is False

    def test_email_normalizado_a_minusculas(self, api_client, db):
        d = {**VALID, 'email': 'COMPRADOR@PRACTICAYORUBA.MX'}
        api_client.post(URL, d, format='json')
        user = get_user_model().objects.get(username=VALID['username'])
        assert user.email == 'comprador@practicayoruba.mx'


class TestRegisterValidacion:

    def test_username_vacio_retorna_400(self, api_client, db):
        r = api_client.post(URL, {**VALID, 'username': ''}, format='json')
        assert r.status_code == 400
        assert 'username' in r.json()

    def test_email_invalido_retorna_400(self, api_client, db):
        r = api_client.post(URL, {**VALID, 'email': 'no-es-email'}, format='json')
        assert r.status_code == 400
        assert 'email' in r.json()

    def test_password_corto_retorna_400(self, api_client, db):
        r = api_client.post(URL, {**VALID, 'password': 'Ab1!', 'password_confirm': 'Ab1!'}, format='json')
        assert r.status_code == 400

    def test_passwords_no_coinciden_retorna_400(self, api_client, db):
        r = api_client.post(URL, {**VALID, 'password_confirm': 'Diferente99!'}, format='json')
        assert r.status_code == 400

    def test_username_muy_corto_retorna_400(self, api_client, db):
        r = api_client.post(URL, {**VALID, 'username': 'ab'}, format='json')
        assert r.status_code == 400


class TestRegisterUnicidad:

    def test_username_duplicado_400_mensaje_ambiguo(self, api_client, user):
        r = api_client.post(URL, {**VALID, 'username': user.username}, format='json')
        assert r.status_code == 400
        assert user.username not in str(r.json()).lower()

    def test_email_duplicado_400_mensaje_ambiguo(self, api_client, user):
        r = api_client.post(URL, {**VALID, 'email': user.email}, format='json')
        assert r.status_code == 400
        assert user.email not in str(r.json()).lower()
