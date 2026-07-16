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

    def test_email_es_el_identificador(self, api_client, db):
        # Party (T-201): ya no hay username autogenerado; el email ES el
        # identificador (USERNAME_FIELD). El registro previo (username=email[:150])
        # confirmaba que username era una copia del email — por eso el swap a
        # email como identificador único es semánticamente equivalente.
        api_client.post(URL, VALID, format='json')
        User = get_user_model()
        user = User.objects.get(email=VALID['email'])
        assert User.USERNAME_FIELD == 'email'
        assert User.objects.get_by_natural_key(VALID['email']).pk == user.pk

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


# =============================================================================
# H-CART-01 — Registro fusiona el carrito anónimo en la cuenta nueva
# =============================================================================

import uuid as _uuid
from decimal import Decimal
from apps.addons.cart.models import Cart, CartItem
from apps.addons.catalogue.models import Product


class TestRegisterMergesAnonCart:
    def _anon_cart_con_item(self, email_slug='mrg'):
        p = Product.objects.create(
            name=f'Elekes {email_slug}', slug=f'elekes-{email_slug}',
            sku=f'ELE-{email_slug.upper()}-1', description='x',
            price=Decimal('100.00'), stock=5, is_active=True, is_published=True,
        )
        anon = Cart.objects.create(cart_token=_uuid.uuid4())
        CartItem.objects.create(cart=anon, product=p, quantity=2, unit_price=Decimal('100.00'))
        return anon

    def test_registro_fusiona_el_carrito_anonimo(self, api_client, db):
        anon = self._anon_cart_con_item()
        res = api_client.post(URL, {**VALID, 'cart_token': str(anon.cart_token)}, format='json')
        assert res.status_code == 201
        user = get_user_model().objects.get(email=VALID['email'])
        user_cart = Cart.objects.get(user=user)
        assert user_cart.items.count() == 1
        # el carrito anónimo se consumió al fusionarse
        assert not Cart.objects.filter(cart_token=anon.cart_token).exists()

    def test_registro_sin_cart_token_sigue_funcionando(self, api_client, db):
        assert api_client.post(URL, VALID, format='json').status_code == 201

    def test_registro_con_cart_token_invalido_no_rompe(self, api_client, db):
        assert api_client.post(URL, {**VALID, 'cart_token': 'no-es-uuid'}, format='json').status_code == 201

    def test_cart_token_de_otro_usuario_no_se_secuestra(self, api_client, db):
        # Un carrito ya asociado a un usuario no debe fusionarse por token.
        other = get_user_model().objects.create_user(
            email='dueno@x.mx', password='Yoruba2026!', is_active=True)
        owned = Cart.objects.create(user=other, cart_token=_uuid.uuid4())
        res = api_client.post(URL, {**VALID, 'cart_token': str(owned.cart_token)}, format='json')
        assert res.status_code == 201
        # el carrito del otro usuario sigue intacto
        assert Cart.objects.filter(pk=owned.pk, user=other).exists()
