"""Abstracción de providers del framework de pagos (``payment.provider`` de Odoo)."""
from .base import (
    BaseGateway,
    PreferenceResult,
    InstallmentPlan,
    PaymentVerification,
    RefundResult,
    PaymentResult,
)

__all__ = [
    'BaseGateway', 'PreferenceResult', 'InstallmentPlan',
    'PaymentVerification', 'RefundResult', 'PaymentResult',
]
