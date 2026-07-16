"""
Tests — Cookie httpOnly del carrito anónimo (H-CART-01 Fase 2).

La Fase 2 hace durable el carrito anónimo fijando el ``cart_token`` en una
cookie httpOnly (en vez de sólo el header X-Cart-Token memory-only, DEC-BC-07).
Así el carrito sobrevive recargas y pestañas nuevas, no sólo el registro.

Se verifica:
  - Una respuesta de carrito anónimo fija la cookie ``cart_token`` httpOnly.
  - Un cliente que sólo lleva la cookie (sin header) resuelve EL MISMO carrito
    → durabilidad entre "recargas".
  - Un usuario autenticado NO recibe la cookie (su carrito se resuelve por user).
  - La cookie está registrada como necessary → CookieGovernanceMiddleware no la
    suprime (queda en la respuesta).
"""
import uuid
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.modules.catalogue.models import Category, Product

pytestmark = pytest.mark.integration

ITEMS_URL = '/api/v2/cart/items/'
CART_URL  = '/api/v2/cart/'


@pytest.fixture
def product_cookie(db):
    cat = Category.objects.create(name='Cat Cookie', slug='cat-cookie', is_active=True)
    _p = Product.objects.create(
        name='Prod Cookie', slug='prod-cookie', sku='CK-001', description='',
        price=Decimal('500.00'), stock=10, is_active=True, is_published=True,
    )
    _p.categories.add(cat)
    return _p


class TestCookieCarritoAnonimo:

    def test_add_item_fija_cookie_httponly(self, api_client, product_cookie):
        """Al crear un carrito anónimo se fija la cookie httpOnly cart_token."""
        res = api_client.post(ITEMS_URL, {
            'product_id': product_cookie.pk, 'quantity': 1,
        }, format='json')
        assert res.status_code == 201
        assert 'cart_token' in res.cookies
        morsel = res.cookies['cart_token']
        # httpOnly no leíble por JS (espíritu anti-XSS de DEC-BC-07).
        assert morsel['httponly']
        assert morsel['samesite'].lower() == 'lax'
        assert morsel['max-age']  # tiene expiración (durable)
        # el valor de la cookie coincide con el token del header (back-compat)
        assert morsel.value == res['X-Cart-Token']

    def test_cookie_sola_resuelve_el_mismo_carrito(self, api_client, product_cookie):
        """Un cliente que sólo lleva la cookie (sin header) recupera su carrito.

        Simula la recarga de página: el header X-Cart-Token memory-only se
        pierde, pero la cookie httpOnly persiste y resuelve el mismo Cart.
        """
        res1 = api_client.post(ITEMS_URL, {
            'product_id': product_cookie.pk, 'quantity': 2,
        }, format='json')
        token = res1.cookies['cart_token'].value

        # Nuevo cliente: SIN header X-Cart-Token, SÓLO la cookie.
        fresh = APIClient()
        fresh.cookies['cart_token'] = token
        res2 = fresh.get(CART_URL)
        assert res2.status_code == 200
        body = res2.json()
        assert len(body['items']) == 1
        assert body['items'][0]['quantity'] == 2

    def test_usuario_autenticado_no_recibe_cookie(self, auth_client, product_cookie):
        """El carrito autenticado se resuelve por user → no se fija cart_token."""
        res = auth_client.post(ITEMS_URL, {
            'product_id': product_cookie.pk, 'quantity': 1,
        }, format='json')
        assert res.status_code == 201
        assert 'cart_token' not in res.cookies

    def test_cookie_no_es_suprimida_por_governance(self, api_client, product_cookie):
        """cart_token está registrada como necessary → sobrevive el governance."""
        res = api_client.post(ITEMS_URL, {
            'product_id': product_cookie.pk, 'quantity': 1,
        }, format='json')
        # Si el governance la borrase, no estaría en response.cookies.
        assert 'cart_token' in res.cookies
        assert res.cookies['cart_token'].value

    def test_cookie_preferida_sobre_header_divergente(self, api_client, product_cookie):
        """Si cookie y header divergen, gana la cookie (fuente durable)."""
        res1 = api_client.post(ITEMS_URL, {
            'product_id': product_cookie.pk, 'quantity': 1,
        }, format='json')
        cookie_token = res1.cookies['cart_token'].value

        fresh = APIClient()
        fresh.cookies['cart_token'] = cookie_token
        # header apunta a un token distinto (inexistente): la cookie debe ganar
        fresh.credentials(HTTP_X_CART_TOKEN=str(uuid.uuid4()))
        res2 = fresh.get(CART_URL)
        assert res2.status_code == 200
        assert len(res2.json()['items']) == 1
