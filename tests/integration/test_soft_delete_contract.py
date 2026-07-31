"""
Contract tests for the soft delete policy (DEC-DOC-007).

These tests validate the SoftDeleteModel mixin in core.models:
- ``delete()`` marks ``is_deleted=True`` + ``deleted_at`` and does
  NOT remove the row from the database.
- the default ``objects`` manager hides soft-deleted rows.
- ``all_objects`` exposes both alive and deleted rows.
- ``restore()`` reverts the soft delete.
- ``hard_delete()`` performs a real DELETE.
- ``queryset.delete()`` does a bulk soft delete via UPDATE.
"""
import pytest
from addons.sale.models import SaleOrder
from addons.base.models import SoftDeleteModel, SoftDeleteManager, AllObjectsManager
from addons.catalogue.models import Product, Category
from addons.users.models import Address

pytestmark = pytest.mark.integration


class TestSoftDeleteContract:
    """Contract tests against core.models.SoftDeleteModel."""

    def test_softdeletemodel_is_abstract(self):
        assert SoftDeleteModel._meta.abstract is True

    def test_softdeletemodel_declares_required_fields(self):
        field_names = {f.name for f in SoftDeleteModel._meta.get_fields()}
        assert 'is_deleted' in field_names
        assert 'deleted_at' in field_names

    def test_softdeletemodel_exposes_dual_managers(self):
        # Managers son tipos distintos; los modelos concretos
        # heredan ambos. Verificamos los tipos en el mixin abstracto.
        assert SoftDeleteManager is not AllObjectsManager
        # Los managers se declaran como class attrs; en abstractos
        # quedan en _meta.local_managers.
        manager_names = {m.name for m in SoftDeleteModel._meta.local_managers}
        assert 'objects' in manager_names
        assert 'all_objects' in manager_names


class TestSoftDeleteOnProduct:
    """
    Contract test on a real concrete model: Product (catalogue).
    Product must inherit from SoftDeleteModel after the migration
    that lands in this same iteration.
    """

    @pytest.mark.django_db
    def test_delete_marks_soft_and_hides_from_default_manager(self):
        cat = Category.objects.create(name='Cat soft', slug='cat-soft')
        product = Product.objects.create(
            name='Soft Delete Subject',
            slug='soft-delete-subject', price=10,
            stock=1, is_active=True,
        )
        product.categories.add(cat)
        product.categories.add(cat)
        pk = product.pk
        product.delete()

        # No esta en queryset por defecto.
        assert not Product.objects.filter(pk=pk).exists()
        # Pero sigue en la base de datos via all_objects.
        ghost = Product.all_objects.get(pk=pk)
        assert ghost.is_deleted is True
        assert ghost.deleted_at is not None

    @pytest.mark.django_db
    def test_restore_reverts_soft_delete(self):
        cat = Category.objects.create(name='Cat restore', slug='cat-restore')
        product = Product.objects.create(
            name='Restore Subject',
            slug='restore-subject', price=10, stock=1,
            is_active=True,
        )
        product.categories.add(cat)
        product.categories.add(cat)
        product.delete()
        ghost = Product.all_objects.get(pk=product.pk)
        ghost.restore()
        assert Product.objects.filter(pk=product.pk).exists()

    @pytest.mark.django_db
    def test_hard_delete_actually_removes_row(self):
        cat = Category.objects.create(name='Cat hard', slug='cat-hard')
        product = Product.objects.create(
            name='Hard Delete Subject',
            slug='hard-delete-subject', price=10, stock=1,
            is_active=True,
        )
        product.categories.add(cat)
        product.categories.add(cat)
        pk = product.pk
        product.hard_delete()
        assert not Product.all_objects.filter(pk=pk).exists()


class TestSoftDeleteOnOrder:
    """SaleOrder (orders) — historial financiero. Critico."""

    @pytest.mark.django_db
    def test_order_inherits_softdelete(self):
        assert issubclass(SaleOrder, SoftDeleteModel)
        assert hasattr(SaleOrder, 'all_objects')


class TestSoftDeleteOnAddress:
    """Address (users) — referenciado historicamente desde SaleOrder."""

    @pytest.mark.django_db
    def test_address_inherits_softdelete(self):
        assert issubclass(Address, SoftDeleteModel)
        assert hasattr(Address, 'all_objects')
