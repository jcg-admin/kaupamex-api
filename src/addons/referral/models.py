"""
Models — addons.referral (UC-PRO-05: programa de referidos)

ReferralCode: codigo referral unico por usuario (1:1 con User). El codigo se
    respalda como un ``Voucher`` de tipo REFERRAL para reutilizar la validacion
    de vigencia/estado existente (UC-PRO-05 Subflujo A, paso 2).
Referral: relacion referidor-referido con estado PENDING/COMPLETED
    (UC-PRO-05 POST-03).
"""
import secrets
import string
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from addons.base.models import TimeStampedModel
from addons.loyalty.models import Voucher

_ALPHABET = string.ascii_uppercase + string.digits


def generate_suffix(length: int = 6) -> str:
    """Genera un sufijo aleatorio de ``length`` caracteres en mayusculas."""
    return ''.join(secrets.choice(_ALPHABET) for _ in range(length))


class ReferralCode(TimeStampedModel):
    """Codigo referral unico de un comprador. UC-PRO-05 Subflujo A."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_code',
    )
    code = models.CharField(
        max_length=50, unique=True,
        verbose_name='Codigo referral',
        help_text='Formato REF-{user.id}-{6 chars}. Siempre en mayusculas.',
    )

    class Meta:
        db_table     = 'referral_code'
        verbose_name = 'Codigo referral'

    def __str__(self):
        return self.code

    @classmethod
    def get_or_create_for_user(cls, user) -> 'ReferralCode':
        """
        Devuelve el codigo referral del usuario, generandolo si no existe.

        Idempotente: una segunda llamada devuelve el mismo ``ReferralCode``.
        El codigo se respalda como un ``Voucher`` de tipo REFERRAL para que la
        validacion de estado en el redeem reutilice la logica del voucher.
        """
        existing = cls.objects.filter(user=user).first()
        if existing is not None:
            return existing
        with transaction.atomic():
            code = cls._build_unique_code(user)
            Voucher.objects.get_or_create(
                code=code,
                defaults={
                    'voucher_type': Voucher.TYPE_REFERRAL,
                    'valid_from': timezone.now(),
                    'is_active': True,
                    'created_by': user,
                },
            )
            return cls.objects.create(user=user, code=code)

    @classmethod
    def _build_unique_code(cls, user) -> str:
        while True:
            candidate = f'REF-{user.id}-{generate_suffix()}'
            if not cls.objects.filter(code=candidate).exists() \
                    and not Voucher.objects.filter(code=candidate).exists():
                return candidate


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
