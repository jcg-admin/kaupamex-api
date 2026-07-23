"""
Soft-delete contract tests for addons.loyalty.Voucher (P-01).

DEC-DOC-007: Voucher inherits from SoftDeleteModel. Cohabita con
la semantica de NEGOCIO (is_active + deactivated_at).
"""
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from addons.loyalty.models import Voucher
from addons.base.models import SoftDeleteModel

import pytest

pytestmark = pytest.mark.integration


def _past(**kw):
    return timezone.now() - timedelta(**kw)


@pytest.fixture
def voucher(db, admin_user):
    return Voucher.objects.create(
        code='SOFTDEL1', voucher_type='FIXED',
        discount_value=Decimal('25.00'),
        min_order_amount=Decimal('0.00'),
        valid_from=_past(days=1),
        is_active=True, created_by=admin_user,
    )


class TestVoucherSoftDelete:

    @pytest.mark.django_db
    def test_inherits_softdeletemodel(self):
        assert issubclass(Voucher, SoftDeleteModel)
        assert hasattr(Voucher, 'all_objects')

    @pytest.mark.django_db
    def test_delete_marks_soft_and_hides_default_manager(self, voucher):
        pk = voucher.pk
        voucher.delete()
        assert not Voucher.objects.filter(pk=pk).exists()
        ghost = Voucher.all_objects.get(pk=pk)
        assert ghost.is_deleted is True
        assert ghost.deleted_at is not None

    @pytest.mark.django_db
    def test_restore_brings_back(self, voucher):
        voucher.delete()
        ghost = Voucher.all_objects.get(pk=voucher.pk)
        ghost.restore()
        assert Voucher.objects.filter(pk=voucher.pk).exists()

    @pytest.mark.django_db
    def test_hard_delete_removes_row(self, voucher):
        pk = voucher.pk
        voucher.hard_delete()
        assert not Voucher.all_objects.filter(pk=pk).exists()

    @pytest.mark.django_db
    def test_business_deactivation_and_system_delete_coexist(self, voucher):
        """
        ``deactivated_at`` (NEGOCIO, UC-PRO-03) y ``deleted_at``
        (SISTEMA, DEC-DOC-007) son campos independientes y pueden
        convivir en la misma fila.
        """
        now = timezone.now()
        voucher.is_active = False
        voucher.deactivated_at = now
        voucher.is_deleted = True
        voucher.deleted_at = now
        voucher.save()
        ghost = Voucher.all_objects.get(pk=voucher.pk)
        assert ghost.is_active is False
        assert ghost.deactivated_at is not None
        assert ghost.is_deleted is True
        assert ghost.deleted_at is not None
