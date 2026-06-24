"""
Tests de integracion — API v2 F2: cart, wishlist, referral, notifications

Verifica que los endpoints /api/v2/ para el bloque F2 son funcionales:
  - cart:          snapshots (save) y merges (merge)
  - wishlist:      cart-transfers (move-to-cart)
  - referral:      redemptions (redeem) — Tier A
  - notifications: PATCH lista (bulk read) y PATCH <pk>/ (mark read)

F2 no elimina v1; verifica coexistencia (doble-corrida).
"""
import uuid
import pytest
from decimal import Decimal

from apps.catalogue.models import Category, Product
from apps.cart.models import Cart, CartItem
from apps.notifications.models import Notification
from apps.wishlist.models import WishlistItem

pytestmark = pytest.mark.integration

# ─── URLs v2 ────────────────────────────────────────────────────────────────
V2_CART_URL        = '/api/v2/cart/'
V2_CART_ITEMS_URL  = '/api/v2/cart/items/'
V2_SNAPSHOTS_URL   = '/api/v2/cart/snapshots/'
V2_MERGES_URL      = '/api/v2/cart/merges/'
V2_WISHLIST_URL    = '/api/v2/wishlist/'
V2_REFERRAL_URL    = '/api/v2/account/referral/'
V2_REDEMPTIONS_URL = '/api/v2/account/referral/redemptions/'
V2_NOTIF_URL       = '/api/v2/notifications/'

# ─── URLs v1 (dual-run) ──────────────────────────────────────────────────────
V1_CART_SAVE_URL       = '/api/v1/cart/save/'
V1_CART_MERGE_URL      = '/api/v1/cart/merge/'
V1_WISH_MOVE_URL       = '/api/v1/wishlist/{pk}/move-to-cart/'
V1_REFERRAL_REDEEM_URL = '/api/v1/account/referral/redeem/'
V1_NOTIF_READ_ALL_URL  = '/api/v1/notifications/read-all/'
V1_NOTIF_READ_URL      = '/api/v1/notifications/{pk}/read/'


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def category_f2(db):
    return Category.objects.create(name='Cat F2', slug='cat-f2', is_active=True)


@pytest.fixture
def product_f2(db, category_f2):
    p = Product.objects.create(
        name='Prod F2',
        slug='prod-f2',
        sku='F2-001',
        description='',
        price=Decimal('500.00'),
        stock=10,
        is_active=True,
        is_published=True,
    )
    p.categories.add(category_f2)
    return p


@pytest.fixture
def cart_with_item(db, user, product_f2):
    cart, _ = Cart.objects.get_or_create(user=user)
    CartItem.objects.create(
        cart=cart,
        product=product_f2,
        quantity=1,
        unit_price=product_f2.price,
    )
    return cart


@pytest.fixture
def wishlist_item(db, user, product_f2):
    return WishlistItem.objects.create(
        user=user,
        product=product_f2,
        price_at_add=product_f2.price,
    )


def _make_notification(user, **kwargs):
    defaults = {
        'user': user,
        'type': 'SYSTEM',
        'subject': 'Asunto F2',
        'body': 'Cuerpo',
        'read': False,
    }
    defaults.update(kwargs)
    return Notification.objects.create(**defaults)


# ─── Cart snapshots (v2) ─────────────────────────────────────────────────────

class TestCartSnapshotsV2:

    def test_requires_auth(self, api_client, db):
        res = api_client.post(V2_SNAPSHOTS_URL)
        assert res.status_code == 401

    def test_empty_cart_returns_400(self, auth_client, user, db):
        Cart.objects.get_or_create(user=user)
        res = auth_client.post(V2_SNAPSHOTS_URL)
        assert res.status_code == 400

    def test_saves_cart_and_returns_200(self, auth_client, user, product_f2, cart_with_item, db):
        res = auth_client.post(V2_SNAPSHOTS_URL)
        assert res.status_code == 200
        body = res.json()
        assert body['saved_count'] == 1
        assert 'detail' in body

    def test_v1_save_still_works(self, auth_client, user, product_f2, cart_with_item, db):
        res = auth_client.post(V1_CART_SAVE_URL)
        assert res.status_code == 200


# ─── Cart merges (v2) ────────────────────────────────────────────────────────

class TestCartMergesV2:

    def test_requires_auth(self, api_client, db):
        res = api_client.post(V2_MERGES_URL, {}, format='json')
        assert res.status_code == 401

    def test_missing_cart_token_returns_400(self, auth_client, db):
        res = auth_client.post(V2_MERGES_URL, {}, format='json')
        assert res.status_code == 400

    def test_nonexistent_token_returns_user_cart(self, auth_client, db):
        token = str(uuid.uuid4())
        res = auth_client.post(V2_MERGES_URL, {'cart_token': token}, format='json')
        assert res.status_code == 200

    def test_v1_merge_still_works(self, auth_client, db):
        token = str(uuid.uuid4())
        res = auth_client.post(V1_CART_MERGE_URL, {'cart_token': token}, format='json')
        assert res.status_code == 200


# ─── Wishlist cart-transfers (v2) ────────────────────────────────────────────

class TestWishlistCartTransfersV2:

    def test_requires_auth(self, api_client, wishlist_item, db):
        url = f'/api/v2/wishlist/{wishlist_item.pk}/cart-transfers/'
        res = api_client.post(url)
        assert res.status_code == 401

    def test_move_to_cart_returns_200(self, auth_client, wishlist_item, db):
        url = f'/api/v2/wishlist/{wishlist_item.pk}/cart-transfers/'
        res = auth_client.post(url, {'remove_from_wishlist': False}, format='json')
        assert res.status_code == 200

    def test_unknown_item_returns_404(self, auth_client, db):
        url = '/api/v2/wishlist/999999/cart-transfers/'
        res = auth_client.post(url)
        assert res.status_code == 404

    def test_v1_move_to_cart_still_works(self, auth_client, wishlist_item, db):
        url = V1_WISH_MOVE_URL.format(pk=wishlist_item.pk)
        res = auth_client.post(url, {'remove_from_wishlist': False}, format='json')
        assert res.status_code == 200


# ─── Referral redemptions (v2) — Tier A ─────────────────────────────────────

class TestReferralRedemptionsV2:

    def test_requires_auth(self, api_client, db):
        res = api_client.post(V2_REDEMPTIONS_URL, {'code': 'X'}, format='json')
        assert res.status_code == 401

    def test_invalid_code_returns_error(self, auth_client, db):
        res = auth_client.post(V2_REDEMPTIONS_URL, {'code': 'BOGUS'}, format='json')
        assert res.status_code in (400, 404, 409, 422)

    def test_v1_redeem_still_works(self, auth_client, db):
        res = auth_client.post(V1_REFERRAL_REDEEM_URL, {'code': 'BOGUS'}, format='json')
        assert res.status_code in (400, 404, 409, 422)

    def test_v2_referral_view_resolves(self, api_client, db):
        # ReferralView returns 401 for unauth (program enabled or not).
        # Confirms URL resolution — if the path didn't exist, Django returns 404.
        res = api_client.get(V2_REFERRAL_URL)
        assert res.status_code == 401


# ─── Notifications PATCH (v2) ────────────────────────────────────────────────

class TestNotificationsBulkReadV2:

    def test_get_list_still_works(self, auth_client, user, db):
        _make_notification(user)
        res = auth_client.get(V2_NOTIF_URL)
        assert res.status_code == 200
        assert 'results' in res.json()

    def test_patch_requires_auth(self, api_client, db):
        res = api_client.patch(V2_NOTIF_URL)
        assert res.status_code == 401

    def test_patch_marks_all_unread_as_read(self, auth_client, user, db):
        n1 = _make_notification(user)
        n2 = _make_notification(user)
        res = auth_client.patch(V2_NOTIF_URL)
        assert res.status_code == 200
        assert res.json()['updated'] == 2
        n1.refresh_from_db()
        n2.refresh_from_db()
        assert n1.read is True
        assert n2.read is True

    def test_patch_with_no_unread_returns_zero(self, auth_client, user, db):
        _make_notification(user, read=True)
        res = auth_client.patch(V2_NOTIF_URL)
        assert res.status_code == 200
        assert res.json()['updated'] == 0

    def test_v1_read_all_still_works(self, auth_client, user, db):
        _make_notification(user)
        res = auth_client.post(V1_NOTIF_READ_ALL_URL)
        assert res.status_code == 200


class TestNotificationMarkReadV2:

    def test_requires_auth(self, api_client, user, db):
        notif = _make_notification(user)
        url = f'{V2_NOTIF_URL}{notif.pk}/'
        res = api_client.patch(url)
        assert res.status_code == 401

    def test_marks_notification_as_read(self, auth_client, user, db):
        notif = _make_notification(user)
        url = f'{V2_NOTIF_URL}{notif.pk}/'
        res = auth_client.patch(url)
        assert res.status_code == 200
        body = res.json()
        assert body['id'] == notif.pk
        assert body['read'] is True
        notif.refresh_from_db()
        assert notif.read is True

    def test_idempotent_on_already_read(self, auth_client, user, db):
        notif = _make_notification(user, read=True)
        url = f'{V2_NOTIF_URL}{notif.pk}/'
        res = auth_client.patch(url)
        assert res.status_code == 200
        assert res.json()['read'] is True

    def test_other_user_notification_returns_404(self, auth_client, admin_user, db):
        notif = _make_notification(admin_user)
        url = f'{V2_NOTIF_URL}{notif.pk}/'
        res = auth_client.patch(url)
        assert res.status_code == 404

    def test_v1_mark_read_still_works(self, auth_client, user, db):
        notif = _make_notification(user)
        url = V1_NOTIF_READ_URL.format(pk=notif.pk)
        res = auth_client.post(url)
        assert res.status_code == 200
