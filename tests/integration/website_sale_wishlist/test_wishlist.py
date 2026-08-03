"""
Tests — Wishlist (UC-WISH-01/02/03)

UC-WISH-01: Agregar producto a wishlist
UC-WISH-02: Ver lista de deseos (paginada, con filtro availability)
UC-WISH-03: Mover item al carrito — keep_in_wishlist + respuesta compacta

T-104 fixes:
  D-01 UC-WISH-03 (CRITICA) — keep_in_wishlist (positive semantics)
  D-05 UC-WISH-02 (ALTA)    — paginacion + filtro availability
  D-06 UC-WISH-01 (MEDIA)   — 200 → 409 PRODUCT_ALREADY_IN_WISHLIST
  D-06 UC-WISH-03 (MEDIA)   — respuesta {wishlist_item_id, cart_item_id, moved_at}
  D-07 UC-WISH-01 (MEDIA)   — price_at_add = product.lst_price
  D-09 UC-WISH-02 (MEDIA)   — nested product + availability string + price_dropped

Nota (disolución de ``chartsize``, H-API-250): se retiraron el fixture
``variant_s14`` y los dos casos que lo consumían (``test_add_with_variant``,
``test_price_at_add_uses_product_base_price``). El addon de variantes ya no
existe (``ls src/addons/chartsize`` → *No such file*): en la referencia el
producto **es** la variante (``product.product``), así que el eje
``variant_id`` del wishlist no tiene sujeto construido. Mismo criterio que
``TestProteccionVariantesOrdenes`` en ``sale/test_order_management.py``.
"""
import pytest
from decimal import Decimal
from tests.factories.product_factory import make_category, make_product, set_stock
from addons.base.models.ir_http import IrHttp
from addons.website_sale_wishlist.models import WishlistItem
from django.contrib.auth import get_user_model

pytestmark = pytest.mark.integration

WISH_URL = '/api/v2/wishlist/'


class TestWishlistCapabilityGate:
    """Enforcement (ADR-020, DEC-ENF-01): la lista de favoritos propia exige
    ``account.wishlist``. Autenticado sin la capacidad → 403."""

    def test_requires_account_wishlist(self, api_client, db):
        u = get_user_model().objects.create_user(
            login='norole-wishlist@practicayoruba.mx', password='TestPass123!')
        api_client.force_login(u)
        assert api_client.get(WISH_URL).status_code == 403


@pytest.fixture
def cat_s14(db):
    return make_category('Cat S14')


@pytest.fixture
def prod_s14(db, cat_s14):
    return make_product(
        name='Prod S14', default_code='S14-001',
        price=Decimal('750.00'), stock=5, categ=cat_s14,
    )


class TestWishlist:

    # UC-WISH-01 ── Agregar ─────────────────────────────────────────────────────────

    def test_requires_auth(self, api_client, db):
        assert api_client.get(WISH_URL).status_code == 401

    def test_add_product_without_variant(self, auth_client, prod_s14, db):
        res = auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        assert res.status_code == 201
        assert res.json()['price_at_add'] == '750.00'

    def test_add_is_idempotent_returns_409(self, auth_client, prod_s14, db):
        """D-06 UC-WISH-01: producto ya activo → 409 PRODUCT_ALREADY_IN_WISHLIST (DEC-DOC-008)."""
        auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        res = auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        assert res.status_code == 409
        assert res.json().get('codigo_error') == 'PRODUCT_ALREADY_IN_WISHLIST'

    def test_view_list_returns_paginated(self, auth_client, prod_s14, db):
        """D-05 UC-WISH-02: GET retorna respuesta paginada con total_items y results."""
        auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        res = auth_client.get(WISH_URL)
        assert res.status_code == 200
        data = res.json()
        assert 'results' in data
        assert 'total_items' in data
        assert len(data['results']) == 1

    def test_view_list_item_has_nested_product(self, auth_client, prod_s14, db):
        """D-09 UC-WISH-02: item expone nested product con name/slug/base_price."""
        auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        item = auth_client.get(WISH_URL).json()['results'][0]
        assert 'product' in item
        assert item['product']['name'] == prod_s14.name
        # El slug no es columna: se computa como en la referencia
        # (``ir.http._slugify``), asi que el esperado se computa igual.
        assert item['product']['slug'] == IrHttp.slugify_one(prod_s14.name)
        assert item['product']['base_price'] == str(prod_s14.lst_price)

    def test_view_list_item_has_availability_string(self, auth_client, prod_s14, db):
        """D-09 UC-WISH-02: availability es string IN_STOCK/OUT_OF_STOCK."""
        auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        item = auth_client.get(WISH_URL).json()['results'][0]
        assert item['availability'] in ('IN_STOCK', 'OUT_OF_STOCK')

    def test_view_list_availability_filter_in_stock(self, auth_client, prod_s14, db):
        """D-05 UC-WISH-02: ?availability=IN_STOCK filtra correctamente."""
        auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        res = auth_client.get(WISH_URL + '?availability=IN_STOCK')
        assert res.status_code == 200
        assert len(res.json()['results']) == 1

    def test_view_list_availability_filter_out_of_stock(self, auth_client, prod_s14, db):
        """D-05 UC-WISH-02: ?availability=OUT_OF_STOCK filtra correctamente."""
        auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        res = auth_client.get(WISH_URL + '?availability=OUT_OF_STOCK')
        assert res.status_code == 200
        assert len(res.json()['results']) == 0

    def test_items_out_of_stock_count(self, auth_client, prod_s14, db):
        """D-05 UC-WISH-02: items_out_of_stock refleja items sin stock."""
        auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        data = auth_client.get(WISH_URL).json()
        assert data['items_out_of_stock'] == 0
        set_stock(prod_s14, 0)
        data2 = auth_client.get(WISH_URL).json()
        assert data2['items_out_of_stock'] == 1

    def test_price_drop_detected(self, auth_client, prod_s14, db):
        """D-09 UC-WISH-02: price_dropped=True y price_drop_percent calculado."""
        auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        # El precio vive en la ficha (lst_price = list_price + extra).
        prod_s14.product_tmpl.list_price = Decimal('600.00')
        prod_s14.product_tmpl.save()
        item = auth_client.get(WISH_URL).json()['results'][0]
        assert item['price_dropped'] is True
        assert item['price_drop_percent'] == 20  # (1 - 600/750) * 100 = 20%

    def test_price_increase_not_a_drop(self, auth_client, prod_s14, db):
        """precio subio → price_dropped False, current_price actualizado."""
        auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        prod_s14.product_tmpl.list_price = Decimal('900.00')
        prod_s14.product_tmpl.save()
        item = auth_client.get(WISH_URL).json()['results'][0]
        assert item['current_price'] == '900.00'
        assert item['price_dropped'] is False

    # UC-WISH-02 ── Eliminar ───────────────────────────────────────────────

    def test_delete_item(self, auth_client, prod_s14, db):
        res = auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        item_id = res.json()['id']
        del_res = auth_client.delete(f'{WISH_URL}{item_id}/')
        assert del_res.status_code == 204
        assert auth_client.get(WISH_URL).json()['results'] == []

    def test_delete_is_soft(self, auth_client, prod_s14, db):
        """DEC-DOC-007: delete marca is_deleted=True, no borra fisicamente."""
        res = auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        item_id = res.json()['id']
        auth_client.delete(f'{WISH_URL}{item_id}/')
        assert WishlistItem.objects.filter(pk=item_id).exists() is False
        item = WishlistItem.all_objects.get(pk=item_id)
        assert item.is_deleted is True
        assert item.deleted_at is not None

    def test_re_add_after_soft_delete_reactiva(self, auth_client, prod_s14, db):
        """Re-agregar producto eliminado reactiva la fila (201, mismo pk)."""
        res1 = auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        item_id = res1.json()['id']
        auth_client.delete(f'{WISH_URL}{item_id}/')
        res2 = auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        assert res2.status_code == 201
        assert res2.json()['id'] == item_id
        assert WishlistItem.all_objects.filter(pk=item_id).count() == 1
        assert WishlistItem.objects.filter(pk=item_id).exists() is True

    # UC-WISH-03 ── Mover al carrito ────────────────────────────────────

    def test_move_to_cart(self, auth_client, prod_s14, db):
        """D-06 UC-WISH-03: respuesta compacta {wishlist_item_id, cart_item_id, moved_at}."""
        res = auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        item_id = res.json()['id']
        move_res = auth_client.post(f'{WISH_URL}{item_id}/cart-transfers/', format='json')
        assert move_res.status_code == 200
        data = move_res.json()
        assert 'wishlist_item_id' in data
        assert 'cart_item_id' in data
        assert 'moved_at' in data
        assert data['wishlist_item_id'] == item_id
        # Por defecto (keep_in_wishlist=False) se elimina de wishlist
        assert auth_client.get(WISH_URL).json()['results'] == []

    def test_move_to_cart_keep_in_wishlist(self, auth_client, prod_s14, db):
        """D-01 UC-WISH-03: remove_from_wishlist=False conserva el item en la lista."""
        res = auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        item_id = res.json()['id']
        auth_client.post(
            f'{WISH_URL}{item_id}/cart-transfers/',
            {'remove_from_wishlist': False}, format='json')
        assert len(auth_client.get(WISH_URL).json()['results']) == 1

    def test_move_without_stock_returns_409(self, auth_client, prod_s14, db):
        """UC-WISH-03 EX-01 + PARTE 7.3: producto sin stock → 409 PRODUCT_OUT_OF_STOCK."""
        set_stock(prod_s14, 0)
        res = auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        item_id = res.json()['id']
        move_res = auth_client.post(f'{WISH_URL}{item_id}/cart-transfers/', format='json')
        assert move_res.status_code == 409
        assert move_res.json()['codigo_error'] == 'PRODUCT_OUT_OF_STOCK'

    def test_move_without_stock_preserves_item(self, auth_client, prod_s14, db):
        """H-004: tras el 409 por falta de stock el item sigue en la wishlist.

        El código falla antes de tocar el item; sin esta verificación el
        test previo sólo comprobaba el status, no el estado post-operación.
        """
        set_stock(prod_s14, 0)
        res = auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        item_id = res.json()['id']
        move_res = auth_client.post(f'{WISH_URL}{item_id}/cart-transfers/', format='json')
        assert move_res.status_code == 409
        listing = auth_client.get(WISH_URL).json()['results']
        assert len(listing) == 1
        assert listing[0]['id'] == item_id

    def test_re_add_after_move_to_cart(self, auth_client, prod_s14, db):
        """H-005: mover al carrito elimina el item; re-agregarlo vuelve a funcionar.

        Caso realista: el comprador mueve una pieza, se arrepiente y la
        vuelve a guardar. El move (keep_in_wishlist por defecto) la borra;
        el re-add debe reactivar la fila y dejar la lista con un item.
        """
        res1 = auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        item_id_1 = res1.json()['id']
        auth_client.post(f'{WISH_URL}{item_id_1}/cart-transfers/', format='json')
        assert auth_client.get(WISH_URL).json()['results'] == []

        res2 = auth_client.post(WISH_URL, {'product_id': prod_s14.pk}, format='json')
        assert res2.status_code == 201
        assert len(auth_client.get(WISH_URL).json()['results']) == 1
