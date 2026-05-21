"""
Tests de la politica de limpieza en self-delete (FU-4 cierre).

UC-AUTH-16 ahora elimina fisicamente los datos volatiles del usuario:
- cart_cart + cart_cart_item
- cart_saved_cart + cart_saved_cart_item
- wishlist_item (hard_delete, no soft)
- search_history_entry
- notifications_preference

Conserva:
- orders_order y relacionados (fiscal)
- payments_*
- users_address (referenciado por orders snapshot)
- users_deactivation_event (audit log)
"""
import pytest
from decimal import Decimal
from apps.catalogue.models import Category, Product
from apps.cart.models import Cart, SavedCart
from apps.wishlist.models import WishlistItem
from apps.search_history.models import SearchEntry
from apps.notifications.models import NotificationPreference
from apps.users.models import Address, UserDeactivationEvent

pytestmark = pytest.mark.api

URL = '/api/v1/auth/me/deactivate/'


@pytest.fixture
def product(db):
    """Producto + variante mínimos para wishlist/cart tests."""
    cat = Category.objects.create(name='Test', slug='test')
    return Product.objects.create(
        name='Test Product', slug='test-p',
        price=Decimal('100'), category=cat,
        is_active=True,
    )


class TestSelfDeleteEliminaCartActivo:

    def test_cart_se_elimina(self, auth_client, user, db):
        Cart.objects.create(user=user)
        auth_client.post(URL, {'password': 'TestPass123!'}, format='json')
        assert Cart.objects.filter(user=user).count() == 0


class TestSelfDeleteEliminaSavedCarts:

    def test_saved_cart_se_elimina(self, auth_client, user, db):
        # T-103 iter 16: SavedCart model nunca tuvo campo `name`
        # (apps/cart/models.py:158-173 declara solo OneToOneField user).
        # Test outlier: kwarg name removido (anti-soft).
        SavedCart.objects.create(user=user)
        auth_client.post(URL, {'password': 'TestPass123!'}, format='json')
        assert SavedCart.objects.filter(user=user).count() == 0


class TestSelfDeleteEliminaWishlist:

    def test_wishlist_hard_delete(self, auth_client, user, product, db):
        WishlistItem.objects.create(
            user=user, product=product, price_at_add=Decimal('100'),
        )
        auth_client.post(URL, {'password': 'TestPass123!'}, format='json')
        # Verifica que NO queda ni siquiera como soft-deleted
        # (all_objects bypassa el filter de soft).
        assert WishlistItem.all_objects.filter(user=user).count() == 0


class TestSelfDeleteEliminaSearchHistory:

    def test_search_entries_se_eliminan(self, auth_client, user, db):
        SearchEntry.objects.create(
            user=user, query='oshun', normalized_query='oshun',
        )
        auth_client.post(URL, {'password': 'TestPass123!'}, format='json')
        assert SearchEntry.objects.filter(user=user).count() == 0


class TestSelfDeleteEliminaNotificationPreferences:

    def test_preferences_se_eliminan(self, auth_client, user, db):
        NotificationPreference.objects.create(
            user=user, type='order_confirmed', enabled=True,
        )
        auth_client.post(URL, {'password': 'TestPass123!'}, format='json')
        assert NotificationPreference.objects.filter(user=user).count() == 0


class TestSelfDeleteConservaTransaccionales:

    def test_address_se_conserva(self, auth_client, user, db):
        a = Address.objects.create(
            user=user, alias='Casa', recipient_name='X',
            street='S', city='C', state='S', zip_code='00000',
            phone='1', country='MX',
        )
        auth_client.post(URL, {'password': 'TestPass123!'}, format='json')
        # all_objects incluye soft-deleted; address es soft pero el
        # user_id sigue ahi.
        assert Address.all_objects.filter(pk=a.pk, user=user).exists()

    def test_deactivation_event_se_conserva(self, auth_client, user, db):
        auth_client.post(URL, {'password': 'TestPass123!'}, format='json')
        # El evento del self-delete debe persistir.
        assert UserDeactivationEvent.objects.filter(
            user=user, source='self',
        ).exists()
