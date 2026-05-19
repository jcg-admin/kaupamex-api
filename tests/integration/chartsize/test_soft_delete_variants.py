"""
Soft-delete contract tests for apps.chartsize models (P-07):
- VariantType
- VariantOption
- ProductVariant

DEC-DOC-007: las variantes son referenciadas desde OrderItem/CartItem
y deben preservar historial.
"""
from decimal import Decimal

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def variant_chain(db):
    from apps.catalogue.models import Category, Product
    from apps.chartsize.models import ProductVariant, VariantOption, VariantType
    cat = Category.objects.create(name='Cat CHT', slug='cat-cht')
    product = Product.objects.create(
        category=cat, name='Variant Prod', slug='variant-prod',
        sku='VAR-001', price=Decimal('50.00'), stock=10,
        is_active=True, is_published=True,
    )
    vt = VariantType.objects.create(product=product, name='Tamaño', is_active=True)
    vo = VariantOption.objects.create(variant_type=vt, label='Grande', is_active=True)
    pv = ProductVariant.objects.create(
        product=product, option=vo, stock=5, is_active=True,
    )
    return {'type': vt, 'option': vo, 'variant': pv}


class TestVariantTypeSoftDelete:

    @pytest.mark.django_db
    def test_inherits_softdeletemodel(self):
        from apps.chartsize.models import VariantType
        from apps.core.models import SoftDeleteModel
        assert issubclass(VariantType, SoftDeleteModel)
        assert hasattr(VariantType, 'all_objects')


class TestVariantOptionSoftDelete:

    @pytest.mark.django_db
    def test_inherits_softdeletemodel(self):
        from apps.chartsize.models import VariantOption
        from apps.core.models import SoftDeleteModel
        assert issubclass(VariantOption, SoftDeleteModel)
        assert hasattr(VariantOption, 'all_objects')


class TestProductVariantSoftDelete:

    @pytest.mark.django_db
    def test_inherits_softdeletemodel(self):
        from apps.chartsize.models import ProductVariant
        from apps.core.models import SoftDeleteModel
        assert issubclass(ProductVariant, SoftDeleteModel)
        assert hasattr(ProductVariant, 'all_objects')

    @pytest.mark.django_db
    def test_delete_hides_from_default_manager(self, variant_chain):
        from apps.chartsize.models import ProductVariant
        pv = variant_chain['variant']
        pk = pv.pk
        pv.delete()
        assert not ProductVariant.objects.filter(pk=pk).exists()
        ghost = ProductVariant.all_objects.get(pk=pk)
        assert ghost.is_deleted is True
        assert ghost.deleted_at is not None

    @pytest.mark.django_db
    def test_restore(self, variant_chain):
        from apps.chartsize.models import ProductVariant
        pv = variant_chain['variant']
        pv.delete()
        ProductVariant.all_objects.get(pk=pv.pk).restore()
        assert ProductVariant.objects.filter(pk=pv.pk).exists()

    @pytest.mark.django_db
    def test_hard_delete_removes(self, variant_chain):
        from apps.chartsize.models import ProductVariant
        pv = variant_chain['variant']
        pk = pv.pk
        pv.hard_delete()
        assert not ProductVariant.all_objects.filter(pk=pk).exists()
