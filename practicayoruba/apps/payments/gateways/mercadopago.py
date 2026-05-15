"""
MercadoPagoGateway — implementación concreta del Strategy Pattern.

Usa el SDK oficial mercadopago>=2.2.0.
Las credenciales se obtienen desde PaymentGateway.credentials (Fernet).
BR-009: las credenciales NUNCA pasan al frontend.
"""
import json
import logging
from decimal import Decimal

import mercadopago

from .base import BaseGateway, PreferenceResult, InstallmentPlan, PaymentVerification

logger = logging.getLogger('apps')

# Mapeo de estados de MP al vocabulario interno
MP_STATUS_MAP = {
    'approved':   'approved',
    'rejected':   'rejected',
    'in_process': 'in_process',
    'pending':    'pending',
    'cancelled':  'rejected',
    'refunded':   'approved',   # se maneja vía webhook de reembolso
}


def _get_sdk() -> mercadopago.SDK:
    """
    Instancia el SDK de MP con el access_token descifrado en memoria.
    BR-009: las credenciales se descifran solo en el servidor.
    H-S15-004: las credenciales están en PaymentGateway.credentials (Fernet).
    """
    from apps.settings_app.models import PaymentGateway
    try:
        gateway = PaymentGateway.objects.get(
            gateway=PaymentGateway.GATEWAY_MERCADOPAGO,
            is_active=True,
        )
        creds       = gateway.get_credentials()
        access_token = creds.get('access_token', '')
        if not access_token:
            raise ValueError('access_token no configurado en PaymentGateway MERCADOPAGO')
        return mercadopago.SDK(access_token)
    except PaymentGateway.DoesNotExist:
        raise ValueError(
            'No existe un PaymentGateway activo para MERCADOPAGO. '
            'Configúralo en UC-CFG-01 antes de iniciar pagos.'
        )


class MercadoPagoGateway(BaseGateway):
    """
    Implementación del gateway de pago MercadoPago.
    Cubre UC-PAY-01 y UC-PAY-01-EXT (cuotas MSI).
    """

    def create_preference(
        self,
        order,
        back_urls: dict,
        installments: int = 1,
    ) -> PreferenceResult:
        """
        Crea una preferencia de pago en MercadoPago.
        FR-PAY-01.01, FR-PAY-01.02.

        El payload incluye:
        - items: OrderItems con nombre, cantidad y precio unitario del snapshot BR-005
        - payer: email del comprador o guest_email
        - back_urls: success, failure, pending
        - auto_return: 'approved'
        - external_reference: order.order_number para correlacionar el webhook
        - installments (solo si > 1): configuración de cuotas MSI
        """
        sdk = _get_sdk()

        # Construir items desde el snapshot BR-005
        items = [
            {
                'id':          str(item.pk),
                'title':       item.product_name,
                'description': f'{item.variant_label}' if item.variant_label else '',
                'quantity':    item.quantity,
                'unit_price':  float(item.unit_price),
                'currency_id': 'MXN',
            }
            for item in order.items.all()
        ]

        # Email del comprador (autenticado o invitado)
        payer_email = (
            order.user.email if order.user
            else order.guest_email or 'guest@practicayoruba.mx'
        )

        preference_data = {
            'items':              items,
            'payer':              {'email': payer_email},
            'back_urls':          back_urls,
            'auto_return':        'approved',
            'external_reference': order.order_number,
        }

        # UC-PAY-01-EXT: agregar configuración de cuotas si se pidió MSI
        if installments > 1:
            preference_data['payment_methods'] = {
                'installments':     installments,
                'default_installments': installments,
            }

        response = sdk.preference().create(preference_data)

        if response['status'] != 201:
            body = response.get('response', {})
            msg  = body.get('message', str(response))
            logger.error('MercadoPago preference error: %s', msg)
            raise RuntimeError(f'Error al crear preferencia en MercadoPago: {msg}')

        result = response['response']
        return PreferenceResult(
            preference_id = result['id'],
            checkout_url  = result['init_point'],
        )

    def get_installment_plans(self, amount: Decimal) -> list[InstallmentPlan]:
        """
        Consulta los planes de cuotas MSI disponibles en MP.
        FR-PAY-01-EXT.01.
        Solo retorna planes sin interés (installment_rate = 0).
        """
        sdk  = _get_sdk()
        resp = sdk.payment_methods().list_all()

        if resp.get('status') != 200:
            logger.warning('MercadoPago installments error: %s', resp)
            return []

        plans = []
        for method in resp.get('response', []):
            payer_costs = method.get('payer_costs', [])
            for cost in payer_costs:
                if cost.get('installment_rate', 1) == 0:
                    n = cost.get('installments', 1)
                    if n > 1:
                        amount_per = (amount / n).quantize(Decimal('0.01'))
                        plans.append(InstallmentPlan(
                            installments=n,
                            amount_per_installment=amount_per,
                            total_amount=amount,
                            interest_rate=Decimal('0.00'),
                        ))

        # Deduplicar y ordenar por número de cuotas
        seen = set()
        unique = []
        for p in sorted(plans, key=lambda x: x.installments):
            if p.installments not in seen:
                seen.add(p.installments)
                unique.append(p)
        return unique

    def verify_payment(self, payment_id: str) -> PaymentVerification:
        """
        Verifica el estado de un pago en MP.
        Se usa en el retorno del comprador y en el webhook (Sprint 16).
        """
        sdk  = _get_sdk()
        resp = sdk.payment().get(payment_id)

        if resp.get('status') != 200:
            logger.error('MercadoPago verify payment error: %s', resp)
            return PaymentVerification(
                gateway_payment_id=payment_id,
                status='pending',
                amount=None,
            )

        data = resp['response']
        return PaymentVerification(
            gateway_payment_id=str(data.get('id', payment_id)),
            status=MP_STATUS_MAP.get(data.get('status', 'pending'), 'pending'),
            amount=Decimal(str(data.get('transaction_amount', 0))),
            installments=data.get('installments', 1),
        )


    def refund(self, gateway_payment_id: str, amount) -> 'RefundResult':
        """
        Ejecuta un reembolso en MercadoPago. UC-PAY-07 (FR-PAY-07.02).
        H-REF-002: usa sdk.refund().create() del SDK oficial.

        MercadoPago acepta reembolso total (sin monto) o parcial (con monto).
        Retorna el refund_id de MP para guardarlo en Refund.gateway_refund_id.
        """
        from decimal import Decimal as Dec
        from .base import RefundResult

        sdk = _get_sdk()
        payload = {}
        if amount is not None:
            payload['amount'] = float(amount)

        response = sdk.refund().create(gateway_payment_id, payload)

        if response.get('status') not in (200, 201):
            body = response.get('response', {})
            msg  = body.get('message', str(response))
            logger.error('MercadoPago refund error: %s', msg)
            raise RuntimeError(f'Error al reembolsar en MercadoPago: {msg}')

        data = response['response']
        return RefundResult(
            refund_id=str(data.get('id', '')),
            status='approved',
            amount=Dec(str(data.get('amount', amount or 0))),
        )
