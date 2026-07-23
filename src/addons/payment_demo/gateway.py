"""Provider payment_demo — Demo (pruebas).

Scaffold fiel al patrón provider de Odoo (payment_demo en
odoo/addons): el módulo registra el provider en el framework
payment implementando el contrato BaseGateway. La integración con
el servicio externo está pendiente; cada operación falla explícito con
NotImplementedError (provider registrado, sin credenciales ni flujo
cableado) — nunca simula un resultado.
"""
from decimal import Decimal

from addons.payment.gateways.base import (
    BaseGateway,
    InstallmentPlan,
    PaymentVerification,
    PreferenceResult,
    RefundResult,
)

_PENDING = (
    'Provider Demo (pruebas) registrado en el framework payment; '
    'integración pendiente (sin credenciales ni flujo cableado).'
)


class DemoGateway(BaseGateway):
    """Provider Demo (pruebas) — contrato registrado, integración pendiente."""

    def refund(self, gateway_payment_id: str, amount: Decimal) -> RefundResult:
        raise NotImplementedError(_PENDING)

    def create_preference(self, order, back_urls: dict,
                          installments: int = 1) -> PreferenceResult:
        raise NotImplementedError(_PENDING)

    def get_installment_plans(self, amount: Decimal) -> list[InstallmentPlan]:
        raise NotImplementedError(_PENDING)

    def verify_payment(self, payment_id: str) -> PaymentVerification:
        raise NotImplementedError(_PENDING)
