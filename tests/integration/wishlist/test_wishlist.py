"""
Tests — Wishlist (UC-WISH-01/02/03)

UC-WISH-01: Add product to wishlist
UC-WISH-02: View wishlist
UC-WISH-03: Move wishlist item to cart
"""
import pytest
from decimal import Decimal
from apps.catalogue.models import Category, Product
from apps.chartsize.models import VariantType, VariantOption, ProductVariant
from apps.wishlist.models import WishlistItem
pytestmark = pytest.mark.integration

WISH_URL = '/api/v1/wishlist/'


@pytest.fixture
def cat_s14(db):
    return Category.objects.create(name='Cat S14', slug='cat-s14', is_active=True)


@pytest.fixture
def prod_s14(db, cat_s14):
    return Product.objects.create(
        name='Prod S14', slug='prod-s14', sku='S14-001',
        description='', category=cat_s14,
        price=Decimal('750.00'), stock=5,
        is_active=True, is_published=True,
    )


@pytest.fixture
def variant_s14(db, prod_s14):
    vt = VariantType.objects.create(product=prod_s14, name='Talla', order=0)
    opt = VariantOption.objects.create(
        variant_type=vt, label='L', slug='l-s14', order=0)
    return ProductVariant.objects.create(
        product=prod_s14, option=opt, sku_suffix='L', stock=3, is_active=True)


class TestWishlist:
    def test_requires_auth(self, api_client, db):
        assert api_client.get(WISH_URL).status_code == 401

    def test_add_product_without_variant(self, auth_client, prod_s14, db):
        res = auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        assert res.status_code == 201
        assert res.json()['price_at_add'] == '750.00'

    def test_add_is_idempotent(self, auth_client, prod_s14, db):
        auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        res = auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        assert res.status_code == 200  # ya existe → 200 en lugar de 201

    def test_add_with_variant(self, auth_client, prod_s14, variant_s14, db):
        res = auth_client.post(WISH_URL, {
            'product_id': prod_s14.pk, 'variant_id': variant_s14.pk
        }, format='json')
        assert res.status_code == 201
        assert res.json()['variant_label'] == 'L'

    def test_view_list(self, auth_client, prod_s14, db):
        auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        res = auth_client.get(WISH_URL)
        assert res.status_code == 200
        assert len(res.json()) == 1

    def test_delete_item(self, auth_client, prod_s14, db):
        res = auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        item_id = res.json()['id']
        del_res = auth_client.delete(f'{WISH_URL}{item_id}/')
        assert del_res.status_code == 204
        assert auth_client.get(WISH_URL).json() == []

    def test_move_to_cart(self, auth_client, prod_s14, db):
        res = auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        item_id = res.json()['id']
        move_res = auth_client.post(f'{WISH_URL}{item_id}/move-to-cart/', format='json')
        assert move_res.status_code == 200
        items = move_res.json()['items']
        assert len(items) == 1
        assert items[0]['quantity'] == 1
        # Por defecto se elimina de wishlist
        assert auth_client.get(WISH_URL).json() == []

    def test_move_to_cart_without_removing(self, auth_client, prod_s14, db):
        res = auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        item_id = res.json()['id']
        auth_client.post(
            f'{WISH_URL}{item_id}/move-to-cart/',
            {'remove_from_wishlist': False}, format='json')
        assert len(auth_client.get(WISH_URL).json()) == 1  # sigue en wishlist

    def test_price_changed_detects_change(self, auth_client, prod_s14, db):
        res = auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        prod_s14.price = Decimal('900.00')
        prod_s14.save()
        get_res = auth_client.get(WISH_URL)
        item = get_res.json()[0]
        assert item['price_changed'] is True
        assert item['current_price'] == '900.00'

    def test_move_without_stock_returns_400(self, auth_client, prod_s14, db):
        prod_s14.stock = 0
        prod_s14.save()
        res = auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        item_id = res.json()['id']
        move_res = auth_client.post(f'{WISH_URL}{item_id}/move-to-cart/', format='json')
        assert move_res.status_code == 400
        assert move_res.json()['codigo_error'] == 'PRODUCTO_NO_DISPONIBLE'

    def test_delete_is_soft(self, auth_client, prod_s14, db):
        """DEC-DOC-007: delete marca is_deleted=True, no borra fisicamente."""
        res = auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        item_id = res.json()['id']
        auth_client.delete(f'{WISH_URL}{item_id}/')
        # Filtrado por default manager: ya no aparece
        assert WishlistItem.objects.filter(pk=item_id).exists() is False
        # Pero la fila persiste para auditoria
        item = WishlistItem.all_objects.get(pk=item_id)
        assert item.is_deleted is True
        assert item.deleted_at is not None

    def test_re_add_after_soft_delete_reactiva(self, auth_client, prod_s14, db):
        """Re-agregar un producto previamente borrado reactiva la fila."""
        res1 = auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        item_id = res1.json()['id']
        auth_client.delete(f'{WISH_URL}{item_id}/')
        res2 = auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        assert res2.status_code == 201
        # Mismo pk, ahora no eliminado
        assert res2.json()['id'] == item_id
        assert WishlistItem.all_objects.filter(pk=item_id).count() == 1
        assert WishlistItem.objects.filter(pk=item_id).exists() is True
