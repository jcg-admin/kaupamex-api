"""
Services — addons.referral (UC-PRO-05)

Logica de negocio del programa de referidos, separada de las vistas:

- ``redeem_referral_code``: el referido canjea un codigo (Subflujo B).
- ``complete_referral_for_order``: al primer pedido pagado del referido,
  completa la relacion y emite el voucher de recompensa al referidor
  (Subflujo C).

Errores de negocio se senalan con ``ReferralError`` que transporta el
``codigo_error`` canonico del proyecto (clave ``codigo_error``, DEC-DOC-005).
"""
import secrets
import string
from django.db import transaction
from django.utils import timezone
from addons.orders.models import Order
from addons.sale.status_projection import (
    STATUS_DELIVERED,
    STATUS_PAID,
    order_status,
)
from addons.base.models import SiteSettings
from addons.loyalty.models import Voucher
from addons.loyalty.models import ReferralCode, Referral

_VOUCHER_CODE_ALPHABET = string.ascii_uppercase + string.digits

_REWARD_ORDER_STATES = (STATUS_PAID, STATUS_DELIVERED)


class ReferralError(Exception):
    """Error de negocio del programa de referidos con codigo_error canonico."""

    def __init__(self, codigo_error: str, detail: str, http_status: int):
        self.codigo_error = codigo_error
        self.detail = detail
        self.http_status = http_status
        super().__init__(detail)


def _emit_fixed_voucher(email: str, amount, created_by=None) -> Voucher:
    """Emite un voucher FIXED de un solo uso restringido a ``email``."""
    return Voucher.objects.create(
        code=_unique_voucher_code('WELCOME' if created_by is None else 'REWARD'),
        voucher_type=Voucher.TYPE_FIXED,
        discount_value=amount,
        valid_from=timezone.now(),
        is_active=True,
        restricted_to_email=email,
        max_uses=1,
        created_by=created_by,
    )


def _unique_voucher_code(prefix: str) -> str:
    while True:
        candidate = f'{prefix}-' + ''.join(
            secrets.choice(_VOUCHER_CODE_ALPHABET) for _ in range(8))
        if not Voucher.objects.filter(code=candidate).exists():
            return candidate


def redeem_referral_code(referee, code: str) -> Referral:
    """
    El referido canjea un codigo referral (UC-PRO-05 Subflujo B).

    Validaciones:
    - Programa activo (EX-01) — manejado por la vista (404).
    - Codigo existe como Voucher REFERRAL (Alt A -> NOT_FOUND 404).
    - Codigo activo (Alt A -> VOUCHER_INACTIVE 422).
    - No autorreferencia (Alt B -> SELF_REFERRAL_NOT_ALLOWED 422).
    - El referido no canjeo otro codigo antes (CONFLICT 409).

    Crea la relacion en estado PENDING y emite el voucher de bienvenida.
    """
    voucher = Voucher.objects.filter(
        code=code.upper(), voucher_type=Voucher.TYPE_REFERRAL,
    ).first()
    if voucher is None:
        raise ReferralError('NOT_FOUND', 'El codigo referral no existe.', 404)

    referral_code = ReferralCode.objects.filter(code=voucher.code).first()
    if referral_code is not None and referral_code.user_id == referee.id:
        raise ReferralError(
            'SELF_REFERRAL_NOT_ALLOWED',
            'No puedes usar tu propio codigo referral.', 422,
        )

    if not voucher.is_active:
        raise ReferralError('VOUCHER_INACTIVE', 'El codigo referral no esta activo.', 422)

    if Referral.objects.filter(referee=referee).exists():
        raise ReferralError(
            'CONFLICT', 'Este usuario ya canjeo un codigo referral.', 409,
        )

    referrer = referral_code.user if referral_code else None
    settings_obj = SiteSettings.get_current()
    with transaction.atomic():
        welcome = _emit_fixed_voucher(
            referee.email, settings_obj.referral_welcome_discount, created_by=None,
        )
        referral = Referral.objects.create(
            referrer=referrer, referee=referee, code=voucher.code,
            status=Referral.STATUS_PENDING,
        )
    return referral


def complete_referral_for_order(order) -> Referral | None:
    """
    Completa la relacion referidor-referido cuando el referido completa su
    primera compra (UC-PRO-05 Subflujo C).

    Solo actua si el pedido esta en un estado que cuenta como "primera compra
    completada" (PAID o DELIVERED). Idempotente: si la relacion ya esta
    COMPLETED no emite un segundo voucher.
    """
    if order.user_id is None or order_status(order) not in _REWARD_ORDER_STATES:
        return None

    referral = Referral.objects.filter(referee_id=order.user_id).first()
    if referral is None or referral.status == Referral.STATUS_COMPLETED:
        return referral

    settings_obj = SiteSettings.get_current()
    with transaction.atomic():
        reward = _emit_fixed_voucher(
            referral.referrer.email, settings_obj.referral_reward_discount,
            created_by=referral.referrer,
        )
        referral.status = Referral.STATUS_COMPLETED
        referral.reward_voucher = reward
        referral.completed_at = timezone.now()
        referral.save(update_fields=['status', 'reward_voucher', 'completed_at', 'updated_at'])
    return referral
