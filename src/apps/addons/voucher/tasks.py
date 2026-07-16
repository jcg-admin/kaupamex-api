"""
Tareas periodicas de sistema — apps.addons.voucher (UC-SYS-02).

expire_vouchers: desactiva vouchers cuya valid_until < now y que
estan activos. Registra el cambio en VoucherChangeLog con fuente
AUTOMATIC_EXPIRATION.
Invocada por management command expire_vouchers (cron cada hora).
"""
import logging

from django.db import transaction
from django.utils import timezone

from .models import Voucher, VoucherChangeLog

logger = logging.getLogger('apps')


def expire_vouchers():
    """UC-SYS-02: desactiva vouchers vencidos y registra el cambio."""
    now = timezone.now()
    # H-VOUCHER-01: skip_locked evita que dos crons concurrentes procesen
    # el mismo voucher y creen entradas duplicadas en VoucherChangeLog.
    expired_ids = list(
        Voucher.objects.filter(
            is_active=True,
            valid_until__lt=now,
        ).values_list('id', flat=True)
    )
    count = 0
    for voucher_id in expired_ids:
        with transaction.atomic():
            # H-CICLO125-02: re-check valid_until__lt=now inside the lock.
            # The initial list is fetched without locking; if an admin
            # extends valid_until between the list fetch and this lock
            # acquisition, the voucher would be wrongly expired. Adding
            # the date guard here closes the TOCTOU window.
            updated = Voucher.objects.filter(
                pk=voucher_id, is_active=True, valid_until__lt=now
            ).select_for_update(skip_locked=True).first()
            if updated is None:
                continue
            updated.is_active = False
            updated.deactivated_at = now
            updated.save(update_fields=['is_active', 'deactivated_at', 'updated_at'])
            VoucherChangeLog.objects.create(
                voucher=updated,
                changed_by=None,
                changes={
                    'is_active':      {'before': True, 'after': False},
                    'source':         'AUTOMATIC_EXPIRATION',
                    'deactivated_at': str(now),
                },
            )
            count += 1
    if count:
        logger.info('expire_vouchers: %d vouchers expirados.', count)
    return count
