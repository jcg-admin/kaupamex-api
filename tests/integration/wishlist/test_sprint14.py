"""Tests Sprint 14 — Wishlist (UC-WISH-01/02/03)."""
import pytest
from decimal import Decimal
pytestmark = pytest.mark.integration

WISH_URL = '/api/v1/wishlist/'


@pytest.fixture
def cat_s14(db):
    from apps.catalogue.models import Category
    return Category.objects.create(name='Cat S14', slug='cat-s14', is_active=True)


@pytest.fixture
def prod_s14(db, cat_s14):
    from apps.catalogue.models import Product
    return Product.objects.create(
        name='Prod S14', slug='prod-s14', sku='S14-001',
        description='', category=cat_s14,
        price=Decimal('750.00'), stock=5,
        is_active=True, is_published=True,
    )


@pytest.fixture
def variant_s14(db, prod_s14):
    from apps.chartsize.models import VariantType, VariantOption, ProductVariant
    vt = VariantType.objects.create(product=prod_s14, name='Talla', order=0)
    opt = VariantOption.objects.create(
        variant_type=vt, label='L', slug='l-s14', order=0)
    return ProductVariant.objects.create(
        product=prod_s14, option=opt, sku_suffix='L', stock=3, is_active=True)


class TestWishlist:
    def test_requiere_auth(self, api_client, db):
        assert api_client.get(WISH_URL).status_code == 401

    def test_agregar_producto_sin_variante(self, auth_client, prod_s14, db):
        res = auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        assert res.status_code == 201
        assert res.json()['price_at_add'] == '750.00'

    def test_agregar_idempotente(self, auth_client, prod_s14, db):
        auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        res = auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        assert res.status_code == 200  # ya existe → 200 en lugar de 201

    def test_agregar_con_variante(self, auth_client, prod_s14, variant_s14, db):
        res = auth_client.post(WISH_URL, {
            'product_id': prod_s14.pk, 'variant_id': variant_s14.pk
        }, format='json')
        assert res.status_code == 201
        assert res.json()['variant_label'] == 'L'

    def test_ver_lista(self, auth_client, prod_s14, db):
        auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        res = auth_client.get(WISH_URL)
        assert res.status_code == 200
        assert len(res.json()) == 1

    def test_eliminar_item(self, auth_client, prod_s14, db):
        res = auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        item_id = res.json()['id']
        del_res = auth_client.delete(f'{WISH_URL}{item_id}/')
        assert del_res.status_code == 204
        assert auth_client.get(WISH_URL).json() == []

    def test_mover_a_carrito(self, auth_client, prod_s14, db):
        res = auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        item_id = res.json()['id']
        move_res = auth_client.post(f'{WISH_URL}{item_id}/move-to-cart/', format='json')
        assert move_res.status_code == 200
        items = move_res.json()['items']
        assert len(items) == 1
        assert items[0]['quantity'] == 1
        # Por defecto se elimina de wishlist
        assert auth_client.get(WISH_URL).json() == []

    def test_mover_a_carrito_sin_eliminar(self, auth_client, prod_s14, db):
        res = auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        item_id = res.json()['id']
        auth_client.post(
            f'{WISH_URL}{item_id}/move-to-cart/',
            {'remove_from_wishlist': False}, format='json')
        assert len(auth_client.get(WISH_URL).json()) == 1  # sigue en wishlist

    def test_price_changed_detecta_cambio(self, auth_client, prod_s14, db):
        res = auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        prod_s14.price = Decimal('900.00')
        prod_s14.save()
        get_res = auth_client.get(WISH_URL)
        item = get_res.json()[0]
        assert item['price_changed'] is True
        assert item['current_price'] == '900.00'

    def test_mover_sin_stock_retorna_400(self, auth_client, prod_s14, db):
        prod_s14.stock = 0
        prod_s14.save()
        res = auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        item_id = res.json()['id']
        move_res = auth_client.post(f'{WISH_URL}{item_id}/move-to-cart/', format='json')
        assert move_res.status_code == 400
        assert move_res.json()['codigo_error'] == 'PRODUCTO_NO_DISPONIBLE'
