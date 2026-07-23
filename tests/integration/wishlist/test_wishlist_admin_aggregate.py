"""
Tests — UC-WISH-04 (H-08): agregado de wishlist para marketing (admin).

GET /api/v2/admin/wishlist/aggregate/ — solo staff; agregados anonimos.
"""
import pytest
from decimal import Decimal

from addons.catalogue.models import Product
from addons.website_sale_wishlist.models import WishlistItem

pytestmark = pytest.mark.integration

AGG_URL = '/api/v2/admin/wishlist/aggregate/'


@pytest.fixture
def product(db):
    return Product.objects.create(
        name='Elekes de Yemayá', slug='elekes-yemaya-agg', sku='AGG-1',
        description='', price=Decimal('500.00'), stock=10,
        is_active=True, is_published=True,
    )


class TestWishlistAggregate:
    def test_requires_admin(self, auth_client, db):
        assert auth_client.get(AGG_URL).status_code == 403

    def test_anon_denied(self, api_client, db):
        assert api_client.get(AGG_URL).status_code in (401, 403)

    def test_aggregates_by_product_anonymously(
        self, admin_client, admin_user, user, product, db
    ):
        WishlistItem.objects.create(
            user=user, product=product, price_at_add=Decimal('500.00'))
        WishlistItem.objects.create(
            user=admin_user, product=product, price_at_add=Decimal('500.00'))

        res = admin_client.get(AGG_URL)
        assert res.status_code == 200
        row = next(
            r for r in res.json()['results'] if r['product_id'] == product.pk
        )
        assert row['times_wishlisted'] == 2
        assert row['distinct_users'] == 2
        assert row['name'] == 'Elekes de Yemayá'
        # BR-013: no expone identidad de compradores.
        assert 'user' not in row and 'users' not in row
