"""Registro de providers del framework de pagos.

En Odoo la resolución del provider es responsabilidad del framework
``payment`` (``payment.provider`` + su ``code``), no de la capa de API
que lo consume. Este módulo centraliza el mapeo ``gateway_type`` →
clase concreta de la familia ``payment_<provider>``; movido desde
``addons.payments.services`` (donde era un privado ``_GATEWAY_REGISTRY``).

Módulo aparte (no re-exportado en ``gateways/__init__``) a propósito:
los providers importan ``gateways.base``, así que anclar el registro en
el ``__init__`` del paquete invitaría un ciclo de import en tiempo de
carga. Importar siempre como ``from addons.payment.gateways.registry
import get_gateway``.
"""
from addons.payment.gateways.base import BaseGateway
from addons.payment_aps.gateway import ApsGateway
from addons.payment_authorize.gateway import AuthorizeGateway
from addons.payment_custom.gateway import CustomGateway
from addons.payment_demo.gateway import DemoGateway
from addons.payment_mercado_pago.gateway import MercadoPagoGateway
from addons.payment_paypal.gateway import PayPalGateway
from addons.payment_stripe.gateway import StripeGateway

# MP es el primario (BR-006) y PayPal el secundario (BR-007); el resto
# está registrado con integración pendiente (sus operaciones fallan explícito).
GATEWAY_REGISTRY: dict[str, type[BaseGateway]] = {
    'MERCADOPAGO': MercadoPagoGateway,
    'PAYPAL': PayPalGateway,
    'APS': ApsGateway,
    'AUTHORIZE': AuthorizeGateway,
    'CUSTOM': CustomGateway,
    'DEMO': DemoGateway,
    'STRIPE': StripeGateway,
}


def get_gateway(gateway_type: str = 'MERCADOPAGO') -> BaseGateway:
    """
    Retorna la instancia del gateway solicitado.
    BR-006: MP es el gateway primario.
    BR-007: PayPal es el secundario disponible desde MVP.
    Tipos desconocidos caen al primario (comportamiento histórico).
    """
    return GATEWAY_REGISTRY.get(gateway_type, MercadoPagoGateway)()


def get_default_gateway() -> BaseGateway:
    """Retorna el gateway activo por defecto (BR-006: MP es el primario)."""
    return MercadoPagoGateway()
