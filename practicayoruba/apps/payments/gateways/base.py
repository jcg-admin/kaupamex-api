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


@dataclass
class RefundResult:
    """Resultado de ejecutar un reembolso en el gateway."""
    refund_id: str
    status:    str    # 'approved' | 'failed'
    amount:    Decimal


@dataclass
class PaymentResult:
    """Resultado de crear un pago con Checkout API (respuesta síncrona).

    A diferencia de PreferenceResult (Checkout Pro), aquí el estado
    del pago se conoce de inmediato: no hay redirección ni webhook posterior.

    Campos para métodos no-tarjeta (OXXO, SPEI, cajero):
      external_resource_url — URL del voucher/barcode (OXXO, Paycash, cajeros)
      date_of_expiration    — fecha límite de pago ISO-8601 (OXXO, SPEI, cajeros)
      transaction_data      — dict con CLABE (SPEI) o datos de barcode (ATM/OXXO)
    """
    gateway_payment_id: str
    status:             str   # 'approved' | 'rejected' | 'pending' | 'in_process'
    status_detail:      str   # 'accredited' | 'cc_rejected_*' | etc.
    amount:             Decimal
    installments:       int = 1
    external_resource_url: str = ''
    date_of_expiration:    str = ''
    transaction_data:      dict = None


class BaseGateway(ABC):
    """
    Interfaz abstracta del Strategy Pattern para gateways de pago.
    Todas las implementaciones deben respetar esta firma.
    """

    @abstractmethod
    def refund(
        self,
        gateway_payment_id: str,
        amount: Decimal,
    ) -> RefundResult:
        """
        Ejecuta un reembolso en el gateway.

        :param gateway_payment_id: ID del pago en el gateway a reembolsar
        :param amount: importe a reembolsar (total o parcial)
        :returns: RefundResult con refund_id, status y amount
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

    def create_payment(
        self,
        order,
        token: str,
        installments: int = 1,
        payment_method_id: str = '',
        issuer_id: str = '',
        payer_email: str = '',
        payer_identification_type: str = '',
        payer_identification_number: str = '',
    ) -> 'PaymentResult':
        """
        Crea un pago con Checkout API (pago en sitio, sin redirección).
        ADR-018: solo MercadoPagoGateway implementa este método.
        PayPalGateway usa create_preference() (Checkout Pro con redirección).

        :param order: instancia Order en estado PENDING
        :param token: token de CardForm de MercadoPago.js (caduca en 7 min)
        :param installments: número de cuotas (1 = contado)
        :param payment_method_id: brand/tipo de tarjeta ('visa', 'master', …)
        :param issuer_id: ID del banco emisor (mejora tasa de aprobación)
        :param payer_email: email del pagador
        :param payer_identification_type: tipo de doc ('CURP', 'RFC', …)
        :param payer_identification_number: número de documento
        :raises NotImplementedError: si el gateway no soporta Checkout API
        """
        raise NotImplementedError(
            f'{self.__class__.__name__} no soporta Checkout API. '
            'Usa create_preference() para pagos con redirección (Checkout Pro).'
        )

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
