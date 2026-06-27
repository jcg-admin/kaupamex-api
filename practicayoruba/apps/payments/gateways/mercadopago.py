"""
MercadoPagoGateway — implementación concreta del Strategy Pattern.

Usa el SDK oficial mercadopago>=2.2.0.
Las credenciales se obtienen desde PaymentGateway.credentials (Fernet).
BR-009: las credenciales NUNCA pasan al frontend.
"""
import json
import logging
from decimal import Decimal, Decimal as Dec
from .base import BaseGateway, PreferenceResult, InstallmentPlan, PaymentVerification, RefundResult, PaymentResult
from apps.settings_app.models import PaymentGateway

import mercadopago


logger = logging.getLogger('apps')

# Métodos de pago que NO requieren token de tarjeta ni número de cuotas.
# Para estos la API de MP usa payer.email + monto + payment_method_id solamente.
NON_CARD_METHOD_IDS = frozenset({
    'oxxo', 'clabe', 'paycash', 'banamex', 'serfin', 'bancomer',
    'account_money', 'consumer_credits',
})

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


    def search_customer_by_email(self, email: str):
        """
        Busca un customer en MP por email.
        Retorna el customer_id string o None si no existe o hay error.
        """
        sdk = _get_sdk()
        response = sdk.customer().search({'email': email})
        if response.get('status') != 200:
            return None
        results = response['response'].get('results', [])
        if results:
            return results[0]['id']
        return None

    def create_customer(self, email: str, first_name: str = '', last_name: str = '') -> str:
        """
        Crea un customer en MP y retorna el customer_id.
        Raises RuntimeError si MP responde con error.
        """
        sdk = _get_sdk()
        payload = {
            'email':      email,
            'first_name': first_name,
            'last_name':  last_name,
        }
        response = sdk.customer().create(payload)
        if response.get('status') != 201:
            body = response.get('response', {})
            msg = body.get('message', str(response))
            raise RuntimeError(f'Error al crear customer en MercadoPago: {msg}')
        return response['response']['id']

    def get_or_create_customer(self, email: str, first_name: str = '', last_name: str = '') -> str:
        """
        Busca customer existente o crea uno nuevo. Evita el error 101 de MP
        (duplicado) buscando primero. Retorna el customer_id.
        """
        existing = self.search_customer_by_email(email)
        if existing:
            return existing
        return self.create_customer(email, first_name, last_name)

    def create_payment(
        self,
        order,
        token: str = '',
        installments: int = 1,
        payment_method_id: str = '',
        issuer_id: str = '',
        payer_email: str = '',
        payer_identification_type: str = '',
        payer_identification_number: str = '',
        customer_id: str = '',
    ) -> PaymentResult:
        """
        Crea un pago con Checkout API (pago en sitio, sin redirección).
        ADR-018: elegido sobre Checkout Pro para UX transparente.

        Para métodos de tarjeta: token (obligatorio) + installments.
        Para métodos no-tarjeta (OXXO, SPEI, cajero, etc.): solo email +
        payment_method_id. El token y cuotas se omiten del payload.
        """
        sdk = _get_sdk()

        payer_email_resolved = (
            payer_email
            or (order.user.email if order.user else None)
            or order.guest_email
            or 'guest@practicayoruba.mx'
        )

        is_non_card = payment_method_id in NON_CARD_METHOD_IDS

        payment_data = {
            'transaction_amount': float(order.value.total),
            'payment_method_id':  payment_method_id,
            'external_reference': order.order_number,
            'payer': {
                'email': payer_email_resolved,
            },
        }

        if not is_non_card:
            payment_data['token']        = token
            payment_data['installments'] = installments

        if customer_id:
            payment_data['payer']['id'] = customer_id

        if issuer_id and not is_non_card:
            payment_data['issuer_id'] = issuer_id

        if payer_identification_type and payer_identification_number:
            payment_data['payer']['identification'] = {
                'type':   payer_identification_type,
                'number': payer_identification_number,
            }

        response = sdk.payment().create(payment_data)

        if response['status'] not in (200, 201):
            body = response.get('response', {})
            msg  = body.get('message', str(response))
            logger.error('MercadoPago Checkout API error: %s', msg)
            raise RuntimeError(f'Error al procesar pago en MercadoPago: {msg}')

        data = response['response']

        # Extraer campos específicos de métodos no-tarjeta
        transaction_details = data.get('transaction_details') or {}
        transaction_data    = data.get('transaction_data') or {}

        external_resource_url = (
            transaction_details.get('external_resource_url', '')
            or data.get('external_resource_url', '')
        )
        date_of_expiration = data.get('date_of_expiration', '')

        return PaymentResult(
            gateway_payment_id    = str(data['id']),
            status                = MP_STATUS_MAP.get(data.get('status', 'pending'), 'pending'),
            status_detail         = data.get('status_detail', ''),
            amount                = Decimal(str(data.get('transaction_amount', order.value.total))),
            installments          = data.get('installments', installments),
            external_resource_url = external_resource_url,
            date_of_expiration    = date_of_expiration,
            transaction_data      = transaction_data if transaction_data else None,
        )

    # -------------------------------------------------------------------------
    # Card CRUD — Customer Cards API
    # -------------------------------------------------------------------------

    def save_card(self, customer_id: str, token: str) -> dict:
        """
        Guarda una tarjeta para un customer existente.
        POST /v1/customers/{customer_id}/cards
        Retorna el dict completo de la tarjeta creada.
        Raises RuntimeError si MP responde con error.
        """
        sdk = _get_sdk()
        response = sdk.card().create(customer_id, {'token': token})
        if response.get('status') not in (200, 201):
            body = response.get('response', {})
            msg  = body.get('message', str(response))
            logger.error('MP save_card error (customer=%s): %s', customer_id, msg)
            raise RuntimeError(f'Error al guardar tarjeta en MercadoPago: {msg}')
        return response['response']

    def get_customer_cards(self, customer_id: str) -> list:
        """
        Lista las tarjetas de un customer.
        GET /v1/customers/{customer_id}/cards
        Retorna lista de dicts de tarjeta (puede ser vacía).
        """
        sdk = _get_sdk()
        response = sdk.card().all(customer_id)
        if response.get('status') != 200:
            body = response.get('response', {})
            msg  = body.get('message', str(response))
            logger.error('MP get_customer_cards error (customer=%s): %s', customer_id, msg)
            raise RuntimeError(f'Error al obtener tarjetas de MercadoPago: {msg}')
        return response['response']

    def get_customer_card(self, customer_id: str, card_id: str) -> dict:
        """
        Obtiene una tarjeta específica de un customer.
        GET /v1/customers/{customer_id}/cards/{id}
        Raises RuntimeError si no se encuentra o hay error de MP.
        """
        sdk = _get_sdk()
        response = sdk.card().get(customer_id, card_id)
        if response.get('status') != 200:
            body = response.get('response', {})
            msg  = body.get('message', str(response))
            logger.error(
                'MP get_customer_card error (customer=%s, card=%s): %s',
                customer_id, card_id, msg,
            )
            raise RuntimeError(f'Error al obtener tarjeta de MercadoPago: {msg}')
        return response['response']

    def update_customer_card(self, customer_id: str, card_id: str, data: dict) -> dict:
        """
        Actualiza datos de una tarjeta (vencimiento, titular).
        PUT /v1/customers/{customer_id}/cards/{id}
        Raises RuntimeError si MP responde con error.
        """
        sdk = _get_sdk()
        response = sdk.card().update(customer_id, card_id, data)
        if response.get('status') not in (200, 201):
            body = response.get('response', {})
            msg  = body.get('message', str(response))
            logger.error(
                'MP update_customer_card error (customer=%s, card=%s): %s',
                customer_id, card_id, msg,
            )
            raise RuntimeError(f'Error al actualizar tarjeta en MercadoPago: {msg}')
        return response['response']

    def delete_customer_card(self, customer_id: str, card_id: str) -> dict:
        """
        Elimina una tarjeta de un customer.
        DELETE /v1/customers/{customer_id}/cards/{id}
        Retorna el dict de la tarjeta eliminada.
        Raises RuntimeError si MP responde con error.
        """
        sdk = _get_sdk()
        response = sdk.card().delete(customer_id, card_id)
        if response.get('status') != 200:
            body = response.get('response', {})
            msg  = body.get('message', str(response))
            logger.error(
                'MP delete_customer_card error (customer=%s, card=%s): %s',
                customer_id, card_id, msg,
            )
            raise RuntimeError(f'Error al eliminar tarjeta de MercadoPago: {msg}')
        return response['response']

    def get_payment_methods(self) -> list:
        """
        Lista los métodos de pago disponibles en MP.
        GET /v1/payment_methods
        Filtra a los tipos relevantes: credit_card, debit_card, ticket,
        bank_transfer, account_money.
        BR-009: no expone access_token — solo datos públicos del método.
        """
        sdk = _get_sdk()
        resp = sdk.payment_methods().list_all()

        if resp.get('status') != 200:
            logger.warning('MP get_payment_methods error: %s', resp)
            return []

        RELEVANT_TYPES = frozenset({
            'credit_card', 'debit_card', 'ticket', 'bank_transfer', 'account_money',
        })

        methods = []
        for m in resp.get('response', []):
            if m.get('payment_type_id') in RELEVANT_TYPES and m.get('status') == 'active':
                methods.append({
                    'id':                 m.get('id', ''),
                    'name':               m.get('name', ''),
                    'payment_type_id':    m.get('payment_type_id', ''),
                    'thumbnail':          m.get('thumbnail', ''),
                    'secure_thumbnail':   m.get('secure_thumbnail', ''),
                    'min_allowed_amount': m.get('min_allowed_amount', 0),
                    'max_allowed_amount': m.get('max_allowed_amount', 0),
                    'accreditation_time': m.get('accreditation_time', 0),
                })
        return methods

    def refund(self, gateway_payment_id: str, amount) -> 'RefundResult':
        """
        Ejecuta un reembolso en MercadoPago. UC-PAY-07 (FR-PAY-07.02).
        H-REF-002: usa sdk.refund().create() del SDK oficial.

        MercadoPago acepta reembolso total (sin monto) o parcial (con monto).
        Retorna el refund_id de MP para guardarlo en Refund.gateway_refund_id.
        """

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
