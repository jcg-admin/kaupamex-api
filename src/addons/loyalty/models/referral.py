"""``Referral`` — relación referente → referido y su recompensa."""
from django.conf import settings
from django.db import models

from addons.base.models import TimeStampedModel
from addons.loyalty.models.voucher import Voucher


class Referral(TimeStampedModel):
    """Relacion referidor-referido. UC-PRO-05 POST-03."""
    STATUS_PENDING   = 'PENDING'
    STATUS_COMPLETED = 'COMPLETED'
    STATUSES = [
        (STATUS_PENDING,   'Pendiente'),
        (STATUS_COMPLETED, 'Completado'),
    ]

    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referrals_made',
    )
    referee = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_received',
    )
    code   = models.CharField(max_length=50, db_index=True)
    status = models.CharField(
        max_length=20, choices=STATUSES,
        default=STATUS_PENDING, db_index=True,
    )
    reward_voucher = models.ForeignKey(
        Voucher,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='referral_rewards',
        help_text='Voucher de recompensa emitido al referidor (Subflujo C).',
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table     = 'referral_referral'
        ordering     = ['-created_at']
        verbose_name = 'Referido'

    def __str__(self):
        return f'{self.referrer_id} -> {self.referee_id} ({self.status})'
