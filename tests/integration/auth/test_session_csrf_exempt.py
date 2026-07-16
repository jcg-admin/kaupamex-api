"""Regresion — mutaciones autenticadas por sesion NO exigen token CSRF.

Este es el test que faltaba y que habria detectado el incidente de prod
(analisis-incidente-csrf-mutaciones): al anadir SessionAuthentication con
exigencia de token CSRF, un ``POST`` autenticado por la cookie de sesion
respondia 403 cuando el SPA no mandaba ``X-CSRFToken`` (tras recargar, sin el
JWT en memoria). Resultado: "agregar al carrito" fallaba y el 403 sacaba al
usuario.

Clave del test: ``APIClient(enforce_csrf_checks=True)``. El ``APIClient`` por
defecto **no** aplica CSRF, por eso los tests originales no vieron el fallo
(verificaban un GET, no la mutacion real). Aqui se fuerza la verificacion CSRF
para reproducir el viaje real del navegador.

Tras la migracion (ADR-018, Opcion 3): la auth por sesion esta **exenta** de
token CSRF (``CsrfExemptSessionAuthentication``); la defensa CSRF es
``SameSite=Strict`` + ``__Host-`` de la cookie. Por tanto el ``POST`` por sesion
debe pasar (200/201), nunca 403.
"""
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.modules.catalogue.models import Category, Product

pytestmark = pytest.mark.integration

ITEMS_URL = '/api/v2/cart/items/'
LOGIN_URL = '/api/v2/auth/login/'


@pytest.fixture
def producto(db):
    cat = Category.objects.create(name='Cat CSRF', slug='cat-csrf', is_active=True)
    p = Product.objects.create(
        name='Prod CSRF', slug='prod-csrf', sku='CSRF-001', description='',
        price=Decimal('500.00'), stock=10, is_active=True, is_published=True,
    )
    p.categories.add(cat)
    return p


@pytest.fixture
def csrf_client():
    """Cliente que SI aplica verificacion CSRF (como el navegador real)."""
    return APIClient(enforce_csrf_checks=True)


class TestMutacionPorSesionExentaDeCsrf:

    def test_post_carrito_por_sesion_no_da_403(self, csrf_client, user, producto):
        # Autenticacion por cookie de sesion (equivale a estar logueado tras
        # recargar: solo la cookie, sin token en memoria).
        csrf_client.force_login(user)

        res = csrf_client.post(
            ITEMS_URL,
            {'product_id': producto.pk, 'quantity': 1},
            format='json',
        )

        # El fallo del incidente era exactamente un 403 CSRF aqui.
        assert res.status_code != 403, (
            'Mutacion por sesion rechazada por CSRF: la exencion no esta activa '
            '(regresion del incidente de prod).'
        )
        assert res.status_code in (200, 201)

    def test_login_luego_recarga_luego_post_carrito(self, csrf_client, user, producto):
        # Viaje real end-to-end con CSRF activo:
        # 1) login -> setea la cookie de sesion.
        r = csrf_client.post(
            LOGIN_URL,
            {'email': user.email, 'password': 'TestPass123!'},
            format='json',
        )
        assert r.status_code == 200
        assert 'sessionid' in r.cookies

        # 2) "recarga": nueva request sin ningun header de auth, solo la cookie.
        csrf_client.credentials()

        # 3) agregar al carrito -> debe funcionar (no 403, no logout).
        res = csrf_client.post(
            ITEMS_URL,
            {'product_id': producto.pk, 'quantity': 2},
            format='json',
        )
        assert res.status_code in (200, 201), (
            f'POST carrito tras recarga fallo con {res.status_code}: '
            'regresion del incidente (sesion + CSRF).'
        )
