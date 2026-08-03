"""``ReferralCode`` — código de referidos del usuario."""
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from addons.base.models import TimeStampedModel
from addons.loyalty.models.voucher import Voucher, generate_suffix


class ReferralCode(TimeStampedModel):
    """Codigo referral unico de un comprador. UC-PRO-05 Subflujo A.

    Homed en ``loyalty`` (2026-07-20): el programa de referidos es la capa de
    referral del framework de fidelidad de Odoo — respalda cada codigo como un
    ``Voucher`` de tipo REFERRAL para reutilizar la validacion de vigencia.
    """
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
