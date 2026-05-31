"""
Soft-delete contract tests for apps.questions.ProductQuestion (P-05).
DEC-DOC-007.
"""
from decimal import Decimal
from apps.catalogue.models import Category, Product
from apps.questions.models import ProductQuestion
from apps.core.models import SoftDeleteModel

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def question(db):
    cat = Category.objects.create(name='Cat Q', slug='cat-q')
    product = Product.objects.create(
        name='Q Product', slug='q-product',
        sku='Q-001', price=Decimal('10.00'), stock=1,
        is_active=True, is_published=True,
    )
    product.categories.add(cat)
    product.categories.add(cat)
    return ProductQuestion.objects.create(
        product=product,
        asker_name='Anon',
        asker_email='anon@example.com',
        body='Is this product available?',
    )


class TestProductQuestionSoftDelete:

    @pytest.mark.django_db
    def test_inherits_softdeletemodel(self):
        assert issubclass(ProductQuestion, SoftDeleteModel)
        assert hasattr(ProductQuestion, 'all_objects')

    @pytest.mark.django_db
    def test_delete_hides_from_default_manager(self, question):
        pk = question.pk
        question.delete()
        assert not ProductQuestion.objects.filter(pk=pk).exists()
        ghost = ProductQuestion.all_objects.get(pk=pk)
        assert ghost.is_deleted is True
        assert ghost.deleted_at is not None

    @pytest.mark.django_db
    def test_restore(self, question):
        question.delete()
        ProductQuestion.all_objects.get(pk=question.pk).restore()
        assert ProductQuestion.objects.filter(pk=question.pk).exists()

    @pytest.mark.django_db
    def test_hard_delete_removes(self, question):
        pk = question.pk
        question.hard_delete()
        assert not ProductQuestion.all_objects.filter(pk=pk).exists()
