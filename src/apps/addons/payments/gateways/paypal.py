"""
PayPalGateway — implementación concreta del Strategy Pattern para PayPal.

Usa la API REST de PayPal v2 directamente con requests (sin SDK).
H-PAY-001: paypalcheckoutsdk no disponible — requests es suficiente.
BR-009: credenciales solo en el servidor.

Flujo de dos pasos (H-PAY-006):
  1. create_preference() → crea la orden en PayPal (CREATED)
  2. capture_payment()   → captura el dinero (llamado desde el webhook)
"""
import json
import logging
from decimal import Decimal, Decimal as Dec
from typing import Optional
from .base import BaseGateway, PreferenceResult, InstallmentPlan, PaymentVerification, RefundResult
from apps.addons.settings_app.models import PaymentGateway

import requests


logger = logging.getLogger('apps')

PAYPAL_API_BASE    = 'https://api.paypal.com'
PAYPAL_API_SANDBOX = 'https://api.sandbox.paypal.com'


def _get_credentials() -> dict:
    """
    Obtiene las credenciales de PayPal desde PaymentGateway (Fernet).
    BR-009: descifrado solo en el servidor.
    Retorna: {'client_id': '...', 'client_secret': '...', 'env': 'sandbox'|'live'}
    """
    try:
        gw = PaymentGateway.objects.get(
            gateway=PaymentGateway.GATEWAY_PAYPAL,
            is_active=True,
        )
        creds = gw.get_credentials()
        if not creds.get('client_id') or not creds.get('client_secret'):
            raise ValueError('client_id y client_secret requeridos para PayPal.')
        return creds
    except PaymentGateway.DoesNotExist:
        raise ValueError(
            'No existe un PaymentGateway activo para PAYPAL. '
            'Configúralo en UC-CFG-01 antes de iniciar pagos.'
        )


def _get_access_token(creds: dict) -> str:
    """
    Obtiene el Bearer token de PayPal via client_credentials.
    FR-PAY-02.01: el sistema renueva el token automáticamente.
    """
    env       = creds.get('env', 'sandbox')
    base_url  = PAYPAL_API_BASE if env == 'live' else PAYPAL_API_SANDBOX
    resp = requests.post(
        f'{base_url}/v1/oauth2/token',
        auth=(creds['client_id'], creds['client_secret']),
        data={'grant_type': 'client_credentials'},
        timeout=15,
    )
    if resp.status_code != 200:
        raise RuntimeError(f'Error obteniendo token de PayPal: {resp.text}')
    return resp.json()['access_token']


class PayPalGateway(BaseGateway):
    """
    Gateway de pago PayPal. UC-PAY-02, UC-PAY-04.
    Usa la API REST v2 de PayPal directamente con requests.
    """

    def create_preference(
        self,
        order,
        back_urls: dict,
        installments: int = 1,
    ) -> PreferenceResult:
        """
        Crea una orden en PayPal y retorna la URL de aprobación.
        FR-PAY-02.01.

        PayPal usa 'purchase_units' en lugar de 'items' individuales.
        El 'external_reference' es order.order_number para correlacionar el webhook.
        """
        creds        = _get_credentials()
        access_token = _get_access_token(creds)
        env          = creds.get('env', 'sandbox')
        base_url     = PAYPAL_API_BASE if env == 'live' else PAYPAL_API_SANDBOX

        total = str(order.value.total)

        purchase_units = [{
            'reference_id':  order.order_number,
            'description':   f'Orden {order.order_number} — PracticaYoruba',
            'amount': {
                'currency_code': 'MXN',
                'value':         total,
                'breakdown': {
                    'item_total': {'currency_code': 'MXN', 'value': total},
                },
            },
            'items': [
                {
                    'name':        item.product_name,
                    'description': item.variant_label or '',
                    'unit_amount': {'currency_code': 'MXN', 'value': str(item.unit_price)},
                    'quantity':    str(item.quantity),
                }
                for item in order.items.all()
            ],
        }]

        payload = {
            'intent':         'CAPTURE',
            'purchase_units': purchase_units,
            'application_context': {
                'return_url': back_urls.get('success', ''),
                'cancel_url': back_urls.get('failure', ''),
                'brand_name': 'PracticaYoruba',
                'user_action': 'PAY_NOW',
            },
        }

        resp = requests.post(
            f'{base_url}/v2/checkout/orders',
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type':  'application/json',
            },
            json=payload,
            timeout=20,
        )

        if resp.status_code not in (200, 201):
            logger.error('PayPal create order error: %s', resp.text)
            raise RuntimeError(f'Error al crear orden en PayPal: {resp.text}')

        data        = resp.json()
        order_id    = data['id']
        approve_url = next(
            (link['href'] for link in data.get('links', []) if link['rel'] == 'approve'),
            None
        )
        if not approve_url:
            raise RuntimeError('PayPal no retornó URL de aprobación.')

        return PreferenceResult(
            preference_id=order_id,
            checkout_url=approve_url,
        )

    def get_installment_plans(self, amount: Decimal) -> list[InstallmentPlan]:
        """
        PayPal no tiene planes MSI como MercadoPago.
        Retorna lista vacía — el frontend no mostrará la opción de cuotas.
        """
        return []

    def verify_payment(self, payment_id: str) -> PaymentVerification:
        """
        Verifica el estado de un pago/captura en PayPal.
        payment_id puede ser un order_id o un capture_id de PayPal.
        """
        creds        = _get_credentials()
        access_token = _get_access_token(creds)
        env          = creds.get('env', 'sandbox')
        base_url     = PAYPAL_API_BASE if env == 'live' else PAYPAL_API_SANDBOX

        resp = requests.get(
            f'{base_url}/v2/checkout/orders/{payment_id}',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=15,
        )

        if resp.status_code != 200:
            return PaymentVerification(
                gateway_payment_id=payment_id,
                status='pending',
                amount=None,
            )

        data   = resp.json()
        status = data.get('status', 'PENDING')

        # Mapeo de estados PayPal al vocabulario interno
        status_map = {
            'COMPLETED': 'approved',
            'APPROVED':  'approved',
            'SAVED':     'pending',
            'PAYER_ACTION_REQUIRED': 'pending',
            'CREATED':   'pending',
            'VOIDED':    'rejected',
        }

        amount = None
        if data.get('purchase_units'):
            pu = data['purchase_units'][0]
            amount_str = pu.get('amount', {}).get('value')
            if amount_str:
                amount = Decimal(amount_str)

        return PaymentVerification(
            gateway_payment_id=payment_id,
            status=status_map.get(status, 'pending'),
            amount=amount,
        )

    def capture_order(self, paypal_order_id: str) -> dict:
        """
        Captura el pago de una orden aprobada en PayPal.
        Llamado desde el webhook handler (H-PAY-006).
        Retorna el capture_id del pago capturado.
        """
        creds        = _get_credentials()
        access_token = _get_access_token(creds)
        env          = creds.get('env', 'sandbox')
        base_url     = PAYPAL_API_BASE if env == 'live' else PAYPAL_API_SANDBOX

        resp = requests.post(
            f'{base_url}/v2/checkout/orders/{paypal_order_id}/capture',
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type':  'application/json',
            },
            timeout=20,
        )

        if resp.status_code not in (200, 201):
            logger.error('PayPal capture error: order=%s body=%s', paypal_order_id, resp.text)
            raise RuntimeError(f'Error al capturar pago PayPal: {resp.text}')

        data = resp.json()
        # Extraer el capture_id del primer purchase_unit
        try:
            capture = data['purchase_units'][0]['payments']['captures'][0]
            return {
                'capture_id': capture['id'],
                'status':     capture['status'],
                'amount':     capture['amount']['value'],
            }
        except (KeyError, IndexError) as exc:
            logger.error('PayPal capture response malformed: %s', data)
            raise RuntimeError(f'Respuesta de captura PayPal inesperada: {exc}')

    def verify_webhook_signature(
        self,
        webhook_id: str,
        headers: dict,
        raw_body: str,
    ) -> bool:
        """
        Verifica la firma del webhook de PayPal.
        FR-PAY-04.01 (H-PAY-003): usa la API REST de PayPal.
        POST https://api.paypal.com/v1/notifications/verify-webhook-signature
        """
        try:
            creds        = _get_credentials()
            access_token = _get_access_token(creds)
            env          = creds.get('env', 'sandbox')
            base_url     = PAYPAL_API_BASE if env == 'live' else PAYPAL_API_SANDBOX
            webhook_id   = creds.get('webhook_id', webhook_id)
        except Exception as exc:
            logger.warning('PayPal webhook verify: credenciales no disponibles: %s', exc)
            return False

        body = json.dumps({
            'webhook_id':             webhook_id,
            'webhook_event':          json.loads(raw_body),
            'cert_url':               headers.get('paypal-cert-url', ''),
            'auth_algo':              headers.get('paypal-auth-algo', ''),
            'transmission_id':        headers.get('paypal-transmission-id', ''),
            'transmission_sig':       headers.get('paypal-transmission-sig', ''),
            'transmission_time':      headers.get('paypal-transmission-time', ''),
        })

        resp = requests.post(
            f'{base_url}/v1/notifications/verify-webhook-signature',
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type':  'application/json',
            },
            data=body,
            timeout=15,
        )

        if resp.status_code != 200:
            logger.warning('PayPal webhook verify API error: %s', resp.text)
            return False

        return resp.json().get('verification_status') == 'SUCCESS'


    def refund(self, gateway_payment_id: str, amount) -> 'RefundResult':
        """
        Ejecuta un reembolso en PayPal. UC-PAY-07 (FR-PAY-07.02).
        H-REF-003: usa la API REST v2 directamente.

        gateway_payment_id es el capture_id de PayPal.
        Body vacío = reembolso total; con amount = reembolso parcial.
        """

        creds        = _get_credentials()
        access_token = _get_access_token(creds)
        env          = creds.get('env', 'sandbox')
        base_url     = PAYPAL_API_BASE if env == 'live' else PAYPAL_API_SANDBOX

        payload = {}
        if amount is not None:
            payload = {
                'amount': {
                    'currency_code': 'MXN',
                    'value': str(amount),
                }
            }

        resp = requests.post(
            f'{base_url}/v2/payments/captures/{gateway_payment_id}/refund',
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type':  'application/json',
            },
            json=payload,
            timeout=20,
        )

        if resp.status_code not in (200, 201):
            logger.error('PayPal refund error: %s', resp.text)
            raise RuntimeError(f'Error al reembolsar en PayPal: {resp.text}')

        data = resp.json()
        refunded_amount = (
            Dec(data.get('amount', {}).get('value', str(amount or 0)))
            if data.get('amount')
            else (amount or Dec('0'))
        )
        return RefundResult(
            refund_id=data.get('id', ''),
            status='approved',
            amount=refunded_amount,
        )
