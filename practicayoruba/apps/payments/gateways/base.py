"""
BaseGateway — Strategy Pattern para gateways de pago (BR-008).

Permite incorporar Stripe u otros gateways sin cambiar el servicio de pagos.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass
class PreferenceResult:
    """Resultado de crear una preferencia de pago en el gateway."""
    preference_id: str
    checkout_url:  str   # URL a la que redirigir al comprador


@dataclass
class InstallmentPlan:
    """Plan de cuotas disponible para un monto dado."""
    installments:       int
    amount_per_installment: Decimal
    total_amount:       Decimal
    interest_rate:      Decimal  # 0.00 = sin intereses (MSI)


@dataclass
class PaymentVerification:
    """Resultado de verificar el estado de un pago en el gateway."""
    gateway_payment_id: Optional[str]
    status:             str   # 'approved' | 'rejected' | 'pending' | 'in_process'
    amount:             Optional[Decimal]
    installments:       int = 1


class BaseGateway(ABC):
    """
    Interfaz abstracta del Strategy Pattern para gateways de pago.
    Todas las implementaciones deben respetar esta firma.
    """

    @abstractmethod
    def create_preference(
        self,
        order,
        back_urls: dict,
        installments: int = 1,
    ) -> PreferenceResult:
        """
        Crea una preferencia/intención de pago en el gateway.

        :param order: instancia de apps.orders.models.Order
        :param back_urls: dict con claves 'success', 'failure', 'pending'
        :param installments: número de cuotas (1 = contado)
        :returns: PreferenceResult con preference_id y checkout_url
        """

    @abstractmethod
    def get_installment_plans(
        self,
        amount: Decimal,
    ) -> list[InstallmentPlan]:
        """
        Consulta los planes de cuotas MSI disponibles para un monto.
        Solo retorna planes sin interés (installment_rate = 0).

        :param amount: monto de la orden
        :returns: lista de InstallmentPlan (vacía si no hay planes)
        """

    @abstractmethod
    def verify_payment(
        self,
        payment_id: str,
    ) -> PaymentVerification:
        """
        Verifica el estado de un pago en el gateway (polling).
        Usado en el retorno del comprador y en reintentos.

        :param payment_id: ID del pago en el gateway externo
        :returns: PaymentVerification con status e importes
        """
