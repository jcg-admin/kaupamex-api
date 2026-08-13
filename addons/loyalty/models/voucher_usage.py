"""``VoucherUsage`` — uso de un voucher por orden.

Se crea al confirmar la venta (``addons.sale``). UC-CART-04.
"""
from django.conf import settings
from django.db import models

from addons.loyalty.models.voucher import Voucher


class VoucherUsage(models.Model):
    """
    Registro de uso de voucher por usuario. DEC-BC-10.
    UNIQUE(user, voucher) garantiza single-use per user.
    """
    user    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='voucher_usages',
    )
    voucher = models.ForeignKey(
        Voucher,
        on_delete=models.CASCADE,
        related_name='usages',
    )
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table     = 'voucher_usage'
        constraints  = [
            models.UniqueConstraint(
                fields=['user', 'voucher'],
                name='unique_voucher_usage',
            )
        ]
        verbose_name = 'Voucher usage'

    def __str__(self):
        return f'{self.user_id} / {self.voucher.code}'
