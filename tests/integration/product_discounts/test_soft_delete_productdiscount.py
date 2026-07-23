"""
Soft-delete contract tests for addons.catalogue.ProductDiscount (P-06).
DEC-DOC-007: el descuento de producto coexiste con la semantica
``is_active`` / ``deactivated_at`` (NEGOCIO).
"""
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from addons.catalogue.models import Category, Product, ProductDiscount
from addons.base.models import SoftDeleteModel

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def discount(db, admin_user):
    cat = Category.objects.create(name='Cat PD', slug='cat-pd')
    product = Product.objects.create(
        name='PD Prod', slug='pd-prod',
        sku='PD-001', price=Decimal('100.00'), stock=1,
        is_active=True, is_published=True,
    )
    product.categories.add(cat)
    product.categories.add(cat)
    return ProductDiscount.objects.create(
        product=product,
        discount_pct=Decimal('10.00'),
        valid_from=timezone.now() - timedelta(days=1),
        is_active=True,
        created_by=admin_user,
    )


class TestProductDiscountSoftDelete:

    @pytest.mark.django_db
    def test_inherits_softdeletemodel(self):
        assert issubclass(ProductDiscount, SoftDeleteModel)
        assert hasattr(ProductDiscount, 'all_objects')

    @pytest.mark.django_db
    def test_delete_hides_from_default_manager(self, discount):
        pk = discount.pk
        discount.delete()
        assert not ProductDiscount.objects.filter(pk=pk).exists()
        ghost = ProductDiscount.all_objects.get(pk=pk)
        assert ghost.is_deleted is True
        assert ghost.deleted_at is not None

    @pytest.mark.django_db
    def test_restore(self, discount):
        discount.delete()
        ProductDiscount.all_objects.get(pk=discount.pk).restore()
        assert ProductDiscount.objects.filter(pk=discount.pk).exists()

    @pytest.mark.django_db
    def test_hard_delete_removes(self, discount):
        pk = discount.pk
        discount.hard_delete()
        assert not ProductDiscount.all_objects.filter(pk=pk).exists()
