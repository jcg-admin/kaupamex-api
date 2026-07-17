"""
Tests — UC-SYS-02: expire_vouchers task.

Verifica que vouchers con valid_until < now y is_active=True
son desactivados y se registra un VoucherChangeLog.
"""
import pytest
from datetime import timedelta
from django.utils import timezone
from addons.voucher.models import Voucher, VoucherChangeLog
from addons.voucher.tasks import expire_vouchers

pytestmark = pytest.mark.django_db

_VOU_COUNTER = 0


def _make_voucher(is_active=True, valid_until_hours=+24):
    global _VOU_COUNTER
    _VOU_COUNTER += 1
    return Voucher.objects.create(
        code=f'EXPTEST{_VOU_COUNTER:04}',
        voucher_type=Voucher.TYPE_FIXED,
        discount_value='10.00',
        valid_from=timezone.now() - timedelta(days=30),
        valid_until=timezone.now() + timedelta(hours=valid_until_hours),
        is_active=is_active,
    )


class TestExpireVouchers:

    def test_desactiva_voucher_expirado(self):
        voucher = _make_voucher(is_active=True, valid_until_hours=-1)
        count = expire_vouchers()
        voucher.refresh_from_db()
        assert voucher.is_active is False
        assert count >= 1

    def test_no_modifica_voucher_vigente(self):
        voucher = _make_voucher(is_active=True, valid_until_hours=+24)
        expire_vouchers()
        voucher.refresh_from_db()
        assert voucher.is_active is True

    def test_crea_changelog_con_source_expiration(self):
        voucher = _make_voucher(is_active=True, valid_until_hours=-1)
        expire_vouchers()
        log = VoucherChangeLog.objects.filter(voucher=voucher).last()
        assert log is not None
        assert log.changes['is_active']['before'] is True
        assert log.changes['is_active']['after'] is False
        assert log.changes['source'] == 'AUTOMATIC_EXPIRATION'
        assert log.changed_by is None

    def test_no_modifica_voucher_ya_inactivo(self):
        voucher = _make_voucher(is_active=False, valid_until_hours=-1)
        initial_count = VoucherChangeLog.objects.count()
        expire_vouchers()
        voucher.refresh_from_db()
        assert voucher.is_active is False
        assert VoucherChangeLog.objects.count() == initial_count
