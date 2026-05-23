"""
Tareas periodicas de sistema — apps.voucher (UC-SYS-02).

expire_vouchers: desactiva vouchers cuya valid_until < now y que
estan activos. Registra el cambio en VoucherChangeLog con fuente
AUTOMATIC_EXPIRATION.
Invocada por management command expire_vouchers (cron cada hora).
"""
import logging

from django.utils import timezone

from .models import Voucher, VoucherChangeLog

logger = logging.getLogger('apps')


def expire_vouchers():
    """UC-SYS-02: desactiva vouchers vencidos y registra el cambio."""
    now = timezone.now()
    expired = Voucher.objects.filter(
        is_active=True,
        valid_until__lt=now,
    )
    count = 0
    for voucher in expired.iterator():
        Voucher.objects.filter(pk=voucher.pk).update(
            is_active=False,
            deactivated_at=now,
        )
        VoucherChangeLog.objects.create(
            voucher=voucher,
            changed_by=None,
            changes={
                'is_active':     {'before': True, 'after': False},
                'source':        'AUTOMATIC_EXPIRATION',
                'deactivated_at': str(now),
            },
        )
        count += 1
    if count:
        logger.info('expire_vouchers: %d vouchers expirados.', count)
    return count
