"""
Tests de integración — UC-AUTH-01: Registrar Cuenta

POST /api/v2/auth/register/
Request:  { first_name, last_name, email, password, password_confirm, terms_accepted }
Response 201: { message, user_id }
Response 400: errores de validacion (formato, contrasena, terms_accepted)
Response 409: email de cuenta activa ya registrado (D-06)

FR-AUTH-01.02 — validar formato
FR-AUTH-01.03 — unicidad con mensaje ambiguo
FR-AUTH-01.04 — is_active=False al crear
D-07 — schema alineado: first_name, last_name, terms_accepted (sin username)
D-06 — cuenta activa retorna 409, no 400
"""
import pytest
from django.contrib.auth import get_user_model

pytestmark = pytest.mark.api

URL = '/api/v2/auth/register/'

VALID = {
    'first_name':     'Comprador',
    'last_name':      'Uno',
    'email':          'comprador1@practicayoruba.mx',
    'password':       'Yoruba2026!',
    'password_confirm': 'Yoruba2026!',
    'terms_accepted': True,
}


class TestRegisterHappyPath:

    def test_registro_exitoso_devuelve_201(self, api_client, db):
        assert api_client.post(URL, VALID, format='json').status_code == 201

    def test_respuesta_contiene_message(self, api_client, db):
        data = api_client.post(URL, VALID, format='json').json()
        assert 'message' in data

    def test_cuenta_creada_con_is_active_false(self, api_client, db):
        api_client.post(URL, VALID, format='json')
        user = get_user_model().objects.get(email=VALID['email'])
        assert user.is_active is False

    def test_email_normalizado_a_minusculas(self, api_client, db):
        d = {**VALID, 'email': 'COMPRADOR@PRACTICAYORUBA.MX'}
        api_client.post(URL, d, format='json')
        user = get_user_model().objects.get(email='comprador@practicayoruba.mx')
        assert user.email == 'comprador@practicayoruba.mx'

    def test_username_autogenerado_desde_email(self, api_client, db):
        api_client.post(URL, VALID, format='json')
        user = get_user_model().objects.get(email=VALID['email'])
        assert user.username == VALID['email'][:150]

    def test_first_name_guardado(self, api_client, db):
        api_client.post(URL, VALID, format='json')
        user = get_user_model().objects.get(email=VALID['email'])
        assert user.first_name == 'Comprador'

    def test_registro_sin_nombre_es_valido(self, api_client, db):
        d = {**VALID, 'first_name': '', 'last_name': ''}
        assert api_client.post(URL, d, format='json').status_code == 201


class TestRegisterValidacion:

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

    def test_terms_accepted_falso_retorna_400(self, api_client, db):
        r = api_client.post(URL, {**VALID, 'terms_accepted': False}, format='json')
        assert r.status_code == 400
        assert 'terms_accepted' in r.json()

    def test_terms_accepted_ausente_retorna_400(self, api_client, db):
        d = {k: v for k, v in VALID.items() if k != 'terms_accepted'}
        r = api_client.post(URL, d, format='json')
        assert r.status_code == 400


class TestRegisterUnicidad:

    def test_email_cuenta_activa_retorna_409(self, api_client, user):
        r = api_client.post(URL, {**VALID, 'email': user.email}, format='json')
        assert r.status_code == 409
        assert user.email not in str(r.json()).lower()
