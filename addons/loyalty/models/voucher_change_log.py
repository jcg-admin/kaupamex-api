"""``VoucherChangeLog`` — historial de cambios de admin (UC-PRO-02)."""
from django.conf import settings
from django.db import models

from addons.base.models import TimeStampedModel
from addons.loyalty.models.voucher import Voucher


class VoucherChangeLog(TimeStampedModel):
    """
    Historial de cambios de administrador en un Voucher. UC-PRO-02.
    Un registro por cada edicion con el snapshot de campos modificados.
    """
    voucher    = models.ForeignKey(
        Voucher, on_delete=models.CASCADE, related_name='change_log',
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
    )
    changes    = models.JSONField(
        help_text='Dict de {campo: {before, after}} con los cambios aplicados.')
    # created_at viene de TimeStampedModel (renombrado de changed_at en migración)

    class Meta:
        db_table     = 'voucher_change_log'
        ordering     = ['-created_at']
        verbose_name = 'Cambio de voucher'

    def __str__(self):
        return f'{self.voucher.code} — {self.created_at.date()}'
